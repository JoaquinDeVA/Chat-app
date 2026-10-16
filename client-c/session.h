/*
 * session.h - the conversations held in memory by the client.
 */
#ifndef SESSION_H
#define SESSION_H

#include "protocol.h"

#define MAX_CHATS 64
#define MAX_MSGS 256

typedef struct {
    char author[MAX_NAME];
    char content[MAX_MSG_LEN];
    char date[DATE_LEN];
    int failed; /* the server rejected it: shown, never counted as delivered */
} Message;

typedef struct {
    char name[MAX_NAME];
    Message msgs[MAX_MSGS]; /* the newest MAX_MSGS; older ones are dropped */
    int nmsg;
} Chat;

typedef struct {
    char username[MAX_NAME];
    int authenticated;
    Chat chats[MAX_CHATS];
    int nchats;
    int active_chat; /* index into chats[], -1 if none */
} Session;

void session_init(Session *s);

/* Index of the chat called `name`, or -1. */
int session_find_chat(const Session *s, const char *name);

/* Adds an empty chat (or returns the existing one). Returns its index, or -1 if full. */
int session_add_chat(Session *s, const char *name);

/* Appends a message to a chat, dropping the oldest one if it is full. Text that is too long is
 * cut. */
void session_add_message(Session *s, int chat, const char *author, const char *content, const char *date,
                         int failed);

/*
 * Applies the reply of load_message_delta, {"conversations": {"chat": [message, ...], ...}}.
 * Returns the number of messages added, or -1 if the reply is malformed.
 */
int session_apply_delta(Session *s, const char *json);

/*
 * Applies something the server pushed: a message ({"chatname", "author", "contents", "sent"})
 * or the notice of a new chat ({"chatname"}). Returns 1 if the session changed.
 */
int session_apply_push(Session *s, const char *json);

#endif
