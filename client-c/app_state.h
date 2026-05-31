#ifndef APP_STATE_H
#define APP_STATE_H

#include <stddef.h>
#include "protocol.h"

#define MAX_CHATS    64
#define MAX_MSGS     512
#define MAX_MSG_LEN  512

typedef enum { STATE_AUTH, STATE_LIVE, STATE_EXIT } AppState;
typedef enum { AUTH_MENU, AUTH_LOGIN, AUTH_REGISTER   } AuthMode;
typedef enum { LIVE_NAVIGATION, LIVE_INPUT, LIVE_NEWCHAT } LiveMode;

typedef struct {
    char author[MAX_NAME];
    char content[MAX_MSG_LEN];
    char date[32];
} Message;

typedef struct {
    char     name[MAX_NAME];
    Message  msgs[MAX_MSGS];
    int      nmsg;
} Chat;

typedef struct {
    char     username[MAX_NAME];
    int      authenticated;
    Chat     chats[MAX_CHATS];
    int      nchats;
    int      active_chat;   /* índice en chats[] */
} AppSession;

void session_init         (AppSession *s);
int  session_find_chat    (AppSession *s, const char *name);
int  session_add_chat     (AppSession *s, const char *name);
void session_add_message  (AppSession *s, int chat_idx, const char *author,
                           const char *content, const char *date);
void session_parse_convs  (AppSession *s, const char *json);

#endif
