#define _POSIX_C_SOURCE 200809L
#include "network.h"

#include <errno.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include "protocol.h"

/* ── message queue ───────────────────────────────────────────────────────────────────────── */

static void queue_init(MsgQueue *q)
{
    q->head = q->tail = q->count = 0;
    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->cond, NULL);
}

static void queue_push(MsgQueue *q, char *msg)
{
    pthread_mutex_lock(&q->lock);
    if (q->count < QUEUE_SIZE) {
        q->items[q->tail] = msg;
        q->tail = (q->tail + 1) % QUEUE_SIZE;
        q->count++;
        pthread_cond_signal(&q->cond);
    } else {
        free(msg); /* queue full: the interface is not keeping up, drop the newest */
    }
    pthread_mutex_unlock(&q->lock);
}

static char *queue_take(MsgQueue *q)
{
    char *msg = q->items[q->head];

    q->head = (q->head + 1) % QUEUE_SIZE;
    q->count--;
    return msg;
}

static char *queue_pop(MsgQueue *q, int timeout_ms)
{
    struct timespec deadline;
    char *msg = NULL;

    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += timeout_ms / 1000;
    deadline.tv_nsec += (long)(timeout_ms % 1000) * 1000000L;
    if (deadline.tv_nsec >= 1000000000L) {
        deadline.tv_sec++;
        deadline.tv_nsec -= 1000000000L;
    }

    pthread_mutex_lock(&q->lock);
    while (q->count == 0) {
        if (timeout_ms == 0)
            break;
        if (timeout_ms < 0)
            pthread_cond_wait(&q->cond, &q->lock);
        else if (pthread_cond_timedwait(&q->cond, &q->lock, &deadline) != 0)
            break;
    }
    if (q->count > 0)
        msg = queue_take(q);
    pthread_mutex_unlock(&q->lock);
    return msg;
}

/* ── receiver thread ─────────────────────────────────────────────────────────────────────── */

static void *receive_loop(void *arg)
{
    NetworkClient *nc = arg;
    char *buffer = NULL;
    size_t length = 0, capacity = 0;
    char chunk[4096];

    while (atomic_load(&nc->running)) {
        ssize_t n = recv(nc->sockfd, chunk, sizeof(chunk), 0);

        if (n <= 0)
            break;
        if (length + (size_t)n > MAX_MESSAGE_BYTES)
            break; /* absurdly large message: give up on this connection */
        if (length + (size_t)n > capacity) {
            size_t wanted = capacity ? capacity * 2 : 8192;
            char *grown;

            while (wanted < length + (size_t)n)
                wanted *= 2;
            grown = realloc(buffer, wanted);
            if (!grown)
                break;
            buffer = grown;
            capacity = wanted;
        }
        memcpy(buffer + length, chunk, (size_t)n);
        length += (size_t)n;

        for (;;) {
            char *end = memchr(buffer, EOT, length);
            size_t message_length;
            char *message;

            if (!end)
                break;
            message_length = (size_t)(end - buffer);
            message = malloc(message_length + 1);
            if (message) {
                memcpy(message, buffer, message_length);
                message[message_length] = '\0';
                queue_push(&nc->queue, message);
            }
            length -= message_length + 1;
            memmove(buffer, end + 1, length);
        }
    }

    free(buffer);
    atomic_store(&nc->running, 0);
    pthread_cond_broadcast(&nc->queue.cond);
    return NULL;
}

/* ── public interface ────────────────────────────────────────────────────────────────────── */

int net_connect(NetworkClient *nc, const char *host, int port)
{
    struct addrinfo hints, *results, *candidate;
    char service[16];

    memset(nc, 0, sizeof(*nc));
    queue_init(&nc->queue);
    nc->sockfd = -1;

    memset(&hints, 0, sizeof(hints));
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_family = AF_UNSPEC;
    snprintf(service, sizeof(service), "%d", port);
    if (getaddrinfo(host, service, &hints, &results) != 0)
        return -1;

    for (candidate = results; candidate; candidate = candidate->ai_next) {
        nc->sockfd = socket(candidate->ai_family, candidate->ai_socktype, candidate->ai_protocol);
        if (nc->sockfd < 0)
            continue;
        if (connect(nc->sockfd, candidate->ai_addr, candidate->ai_addrlen) == 0)
            break;
        close(nc->sockfd);
        nc->sockfd = -1;
    }
    freeaddrinfo(results);
    if (nc->sockfd < 0)
        return -1;

    atomic_store(&nc->running, 1);
    if (pthread_create(&nc->recv_thread, NULL, receive_loop, nc) != 0) {
        close(nc->sockfd);
        nc->sockfd = -1;
        atomic_store(&nc->running, 0);
        return -1;
    }
    return 0;
}

int net_send(NetworkClient *nc, const char *msg)
{
    size_t length = strlen(msg), sent = 0;
    char *buffer;

    if (nc->sockfd < 0)
        return -1;
    buffer = malloc(length + 1);
    if (!buffer)
        return -1;
    memcpy(buffer, msg, length);
    buffer[length] = EOT;

    while (sent < length + 1) {
        ssize_t n = send(nc->sockfd, buffer + sent, length + 1 - sent, MSG_NOSIGNAL);

        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0) {
            free(buffer);
            return -1;
        }
        sent += (size_t)n;
    }
    free(buffer);
    return 0;
}

char *net_recv(NetworkClient *nc, int timeout_ms)
{
    return queue_pop(&nc->queue, timeout_ms);
}

char *net_try_recv(NetworkClient *nc)
{
    return queue_pop(&nc->queue, 0);
}

int net_alive(NetworkClient *nc)
{
    return atomic_load(&nc->running);
}

void net_close(NetworkClient *nc)
{
    char *msg;

    atomic_store(&nc->running, 0);
    if (nc->sockfd >= 0) {
        shutdown(nc->sockfd, SHUT_RDWR);
        pthread_join(nc->recv_thread, NULL);
        close(nc->sockfd);
        nc->sockfd = -1;
    }
    while ((msg = net_try_recv(nc)) != NULL)
        free(msg);
    pthread_mutex_destroy(&nc->queue.lock);
    pthread_cond_destroy(&nc->queue.cond);
}
