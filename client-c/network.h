/*
 * network.h - TCP connection with a background receiver.
 *
 * The receiver thread reads bytes, cuts them into messages at the EOT byte and queues them;
 * net_recv / net_try_recv take them from the queue so the interface never blocks on the socket.
 */
#ifndef NETWORK_H
#define NETWORK_H

#include <pthread.h>
#include <stdatomic.h>
#include <stddef.h>

#define QUEUE_SIZE 128
/* A message larger than this closes the connection. */
#define MAX_MESSAGE_BYTES (32u * 1024u * 1024u)

typedef struct {
    char *items[QUEUE_SIZE];
    int head;
    int tail;
    int count;
    pthread_mutex_t lock;
    pthread_cond_t cond;
} MsgQueue;

typedef struct {
    int sockfd;
    atomic_int running;
    MsgQueue queue;
    pthread_t recv_thread;
} NetworkClient;

/* Connects to host:port (name or address) and starts the receiver. 0 on success, -1 on failure. */
int net_connect(NetworkClient *nc, const char *host, int port);

/* Sends msg followed by EOT, however many writes that takes. 0 on success, -1 on failure. */
int net_send(NetworkClient *nc, const char *msg);

/* Next message, waiting up to timeout_ms (-1: forever). malloc'd: the caller frees. NULL on timeout. */
char *net_recv(NetworkClient *nc, int timeout_ms);

/* Next message if there is one, NULL otherwise. malloc'd: the caller frees. */
char *net_try_recv(NetworkClient *nc);

/* 1 while the connection is up. */
int net_alive(NetworkClient *nc);

/* Closes the connection and releases everything. */
void net_close(NetworkClient *nc);

#endif
