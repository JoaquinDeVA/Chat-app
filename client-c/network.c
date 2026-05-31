#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/time.h>
#include "network.h"
#include "protocol.h"

/* ── Cola de mensajes ── */

static void queue_init(MsgQueue *q)
{
    q->head  = 0;
    q->tail  = 0;
    q->count = 0;
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
        free(msg); /* cola llena, descartamos */
    }
    pthread_mutex_unlock(&q->lock);
}

static char *queue_pop_timed(MsgQueue *q, int timeout_ms)
{
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_sec  += timeout_ms / 1000;
    ts.tv_nsec += (timeout_ms % 1000) * 1000000L;
    if (ts.tv_nsec >= 1000000000L) {
        ts.tv_sec++;
        ts.tv_nsec -= 1000000000L;
    }

    pthread_mutex_lock(&q->lock);
    while (q->count == 0) {
        if (timeout_ms < 0) {
            pthread_cond_wait(&q->cond, &q->lock);
        } else {
            int rc = pthread_cond_timedwait(&q->cond, &q->lock, &ts);
            if (rc != 0) {
                pthread_mutex_unlock(&q->lock);
                return NULL;
            }
        }
    }
    char *msg   = q->items[q->head];
    q->head     = (q->head + 1) % QUEUE_SIZE;
    q->count--;
    pthread_mutex_unlock(&q->lock);
    return msg;
}

static char *queue_pop_nowait(MsgQueue *q)
{
    pthread_mutex_lock(&q->lock);
    if (q->count == 0) {
        pthread_mutex_unlock(&q->lock);
        return NULL;
    }
    char *msg = q->items[q->head];
    q->head   = (q->head + 1) % QUEUE_SIZE;
    q->count--;
    pthread_mutex_unlock(&q->lock);
    return msg;
}

/* ── Hilo receptor ── */

static void *recv_thread_fn(void *arg)
{
    NetworkClient *nc  = (NetworkClient *)arg;
    char           raw[BUF_SIZE * 4];
    size_t         raw_len = 0;

    while (nc->running) {
        char   chunk[4096];
        ssize_t n = recv(nc->sockfd, chunk, sizeof(chunk), 0);
        if (n <= 0) {
            nc->running = 0;
            break;
        }

        /* Acumular en buffer */
        if (raw_len + n < sizeof(raw)) {
            memcpy(raw + raw_len, chunk, n);
            raw_len += n;
        }

        /* Partir por EOT */
        while (1) {
            char *eot = memchr(raw, EOT, raw_len);
            if (!eot)
                break;

            size_t msg_len = eot - raw;
            char  *msg     = malloc(msg_len + 1);
            if (msg) {
                memcpy(msg, raw, msg_len);
                msg[msg_len] = '\0';
                queue_push(&nc->queue, msg);
            }

            /* Desplazar buffer */
            size_t remaining = raw_len - msg_len - 1;
            memmove(raw, eot + 1, remaining);
            raw_len = remaining;
        }
    }

    return NULL;
}

/* ── API pública ── */

int net_connect(NetworkClient *nc, const char *ip, int port)
{
    memset(nc, 0, sizeof(*nc));
    queue_init(&nc->queue);

    nc->sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (nc->sockfd < 0)
        return -1;

    struct sockaddr_in serv = {
        .sin_family = AF_INET,
        .sin_port   = htons(port)
    };
    if (inet_pton(AF_INET, ip, &serv.sin_addr) <= 0) {
        close(nc->sockfd);
        return -1;
    }
    if (connect(nc->sockfd, (struct sockaddr *)&serv, sizeof(serv)) < 0) {
        close(nc->sockfd);
        return -1;
    }

    nc->running = 1;
    pthread_create(&nc->recv_thread, NULL, recv_thread_fn, nc);
    return 0;
}

void net_send(NetworkClient *nc, const char *msg)
{
    size_t  len = strlen(msg);
    char   *buf = malloc(len + 1);
    if (!buf)
        return;

    memcpy(buf, msg, len);
    buf[len] = EOT;
    send(nc->sockfd, buf, len + 1, 0);
    free(buf);
}

char *net_recv(NetworkClient *nc, int timeout_ms)
{
    return queue_pop_timed(&nc->queue, timeout_ms);
}

char *net_try_recv(NetworkClient *nc)
{
    return queue_pop_nowait(&nc->queue);
}

void net_close(NetworkClient *nc)
{
    nc->running = 0;
    if (nc->sockfd >= 0) {
        shutdown(nc->sockfd, SHUT_RDWR);
        close(nc->sockfd);
        nc->sockfd = -1;
    }
    pthread_join(nc->recv_thread, NULL);

    /* Vaciar cola */
    char *msg;
    while ((msg = queue_pop_nowait(&nc->queue)) != NULL)
        free(msg);

    pthread_mutex_destroy(&nc->queue.lock);
    pthread_cond_destroy(&nc->queue.cond);
}
