#ifndef NETWORK_H
#define NETWORK_H

#include <stddef.h>
#include <pthread.h>

#define QUEUE_SIZE 128

typedef struct {
    char  *items[QUEUE_SIZE];
    int    head;
    int    tail;
    int    count;
    pthread_mutex_t lock;
    pthread_cond_t  cond;
} MsgQueue;

typedef struct {
    int       sockfd;
    int       running;
    MsgQueue  queue;
    pthread_t recv_thread;
} NetworkClient;

int  net_connect   (NetworkClient *nc, const char *ip, int port);
void net_send      (NetworkClient *nc, const char *msg);
char *net_recv     (NetworkClient *nc, int timeout_ms); /* malloc'd, caller frees */
char *net_try_recv (NetworkClient *nc);                 /* non-blocking, malloc'd */
void net_close     (NetworkClient *nc);

#endif
