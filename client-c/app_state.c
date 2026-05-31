#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "app_state.h"

void session_init(AppSession *s)
{
    memset(s, 0, sizeof(*s));
    s->active_chat = -1;
}

int session_find_chat(AppSession *s, const char *name)
{
    for (int i = 0; i < s->nchats; i++)
        if (strcmp(s->chats[i].name, name) == 0)
            return i;
    return -1;
}

int session_add_chat(AppSession *s, const char *name)
{
    if (s->nchats >= MAX_CHATS)
        return -1;
    int idx = s->nchats++;
    strncpy(s->chats[idx].name, name, MAX_NAME - 1);
    s->chats[idx].nmsg = 0;
    if (s->active_chat < 0)
        s->active_chat = idx;
    return idx;
}

void session_add_message(AppSession *s, int chat_idx,
                          const char *author, const char *content, const char *date)
{
    if (chat_idx < 0 || chat_idx >= s->nchats)
        return;
    Chat *c = &s->chats[chat_idx];
    if (c->nmsg >= MAX_MSGS)
        return;
    Message *m = &c->msgs[c->nmsg++];
    strncpy(m->author,  author,  sizeof(m->author)  - 1);
    strncpy(m->content, content, sizeof(m->content) - 1);
    strncpy(m->date,    date,    sizeof(m->date)    - 1);
}

/*
 * Parsea el JSON de load_conversations.
 * Formato esperado:
 * {
 *   "conversations": {
 *     "bob": [{"author":"x","content":"z","date":"..."}],
 *     ...
 *   }
 * }
 *
 * Parseo manual sin librerías externas.
 */
void session_parse_convs(AppSession *s, const char *json)
{
    const char *p = strstr(json, "\"conversations\"");
    if (!p)
        return;
    p = strchr(p, '{');
    if (!p)
        return;
    p++; /* saltar '{' del objeto conversations */

    while (*p) {
        /* Saltar espacios */
        while (*p == ' ' || *p == '\n' || *p == '\r' || *p == '\t') p++;
        if (*p == '}')
            break;
        if (*p != '"') { p++; continue; }

        /* Leer nombre del chat */
        p++;
        char chat_name[MAX_NAME] = "";
        int  i = 0;
        while (*p && *p != '"' && i < MAX_NAME - 1)
            chat_name[i++] = *p++;
        chat_name[i] = '\0';
        if (*p == '"') p++;

        /* Saltar hasta '[' */
        while (*p && *p != '[') p++;
        if (!*p) break;
        p++; /* saltar '[' */

        int chat_idx = session_find_chat(s, chat_name);
        if (chat_idx < 0)
            chat_idx = session_add_chat(s, chat_name);

        /* Leer mensajes del array */
        while (*p) {
            while (*p == ' ' || *p == '\n' || *p == '\r' || *p == '\t') p++;
            if (*p == ']') { p++; break; }
            if (*p != '{') { p++; continue; }

            /* Buscar campos dentro del objeto mensaje */
            const char *obj_start = p;
            /* Encontrar el cierre del objeto */
            int depth = 0;
            const char *obj_end = p;
            while (*obj_end) {
                if (*obj_end == '{') depth++;
                else if (*obj_end == '}') { depth--; if (depth == 0) { obj_end++; break; } }
                obj_end++;
            }

            /* Copiar el objeto para parsearlo */
            size_t obj_len = obj_end - obj_start;
            char *obj = malloc(obj_len + 1);
            if (obj) {
                memcpy(obj, obj_start, obj_len);
                obj[obj_len] = '\0';

                char author[MAX_NAME]    = "";
                char content[MAX_MSG_LEN] = "";
                char date[32]            = "";

                /* Buscar "author" */
                const char *f = strstr(obj, "\"author\"");
                if (f) {
                    f += strlen("\"author\"");
                    while (*f == ' ' || *f == ':') f++;
                    if (*f == '"') { f++; int j = 0; while (*f && *f != '"' && j < (int)sizeof(author)-1) author[j++] = *f++; author[j]='\0'; }
                }
                /* Buscar "content" o "contents" */
                f = strstr(obj, "\"content\"");
                if (!f) f = strstr(obj, "\"contents\"");
                if (f) {
                    while (*f && *f != ':') f++;
                    if (*f) f++;
                    while (*f == ' ') f++;
                    if (*f == '"') { f++; int j = 0; while (*f && *f != '"' && j < (int)sizeof(content)-1) content[j++] = *f++; content[j]='\0'; }
                }
                /* Buscar "date" o "sent" */
                f = strstr(obj, "\"date\"");
                if (!f) f = strstr(obj, "\"sent\"");
                if (f) {
                    while (*f && *f != ':') f++;
                    if (*f) f++;
                    while (*f == ' ') f++;
                    if (*f == '"') { f++; int j = 0; while (*f && *f != '"' && j < (int)sizeof(date)-1) date[j++] = *f++; date[j]='\0'; }
                }

                session_add_message(s, chat_idx, author, content, date);
                free(obj);
            }

            p = obj_end;
            while (*p == ',' || *p == ' ' || *p == '\n') p++;
        }

        while (*p == ',' || *p == ' ' || *p == '\n') p++;
    }
}
