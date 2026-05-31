#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "protocol.h"

void proto_login(char *buf, size_t sz, const char *user, const char *pass)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"login\",\n"
             "    \"username\": \"%s\",\n"
             "    \"password\": \"%s\"\n"
             "}",
             user, pass);
}

void proto_create_user(char *buf, size_t sz, const char *user, const char *pass)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"create_user\",\n"
             "    \"username\": \"%s\",\n"
             "    \"password\": \"%s\"\n"
             "}",
             user, pass);
}

void proto_create_chat(char *buf, size_t sz,
                       const char *name, const char **parts, int nparts)
{
    char participants[BUF_SIZE] = "[";
    for (int i = 0; i < nparts; i++) {
        char tmp[MAX_NAME + 4];
        snprintf(tmp, sizeof(tmp), "\"%s\"%s", parts[i], i < nparts - 1 ? ", " : "");
        strncat(participants, tmp, sizeof(participants) - strlen(participants) - 1);
    }
    strncat(participants, "]", sizeof(participants) - strlen(participants) - 1);

    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"create_chat\",\n"
             "    \"chat_name\": \"%s\",\n"
             "    \"participants\": %s\n"
             "}",
             name, participants);
}

void proto_send_msg(char *buf, size_t sz,
                    const char *chat, const char *msg, const char *user)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"send_msg\",\n"
             "    \"username\": \"%s\",\n"
             "    \"chat\": \"%s\",\n"
             "    \"msg\": \"%s\"\n"
             "}",
             user, chat, msg);
}

void proto_load_convs(char *buf, size_t sz, const char *user)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"load_conversations\",\n"
             "    \"username\": \"%s\"\n"
             "}",
             user);
}

void proto_load_delta(char *buf, size_t sz, const char *user, const char *since)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"load_message_delta\",\n"
             "    \"username\": \"%s\",\n"
             "    \"since\": \"%s\"\n"
             "}",
             user, since);
}

void proto_logout(char *buf, size_t sz)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"logout\"\n"
             "}");
}

/* ── Parseo ── */

int parse_code(const char *json)
{
    const char *p = strstr(json, "\"code\"");
    if (!p)
        return -1;
    p += strlen("\"code\"");
    while (*p == ' ' || *p == ':' || *p == '\n' || *p == '\r') p++;
    return atoi(p);
}

int parse_str(const char *json, const char *key, char *out, size_t out_sz)
{
    char        search[128];
    const char *p;
    size_t      i = 0;

    snprintf(search, sizeof(search), "\"%s\"", key);
    p = strstr(json, search);
    if (!p)
        return 0;

    p += strlen(search);
    while (*p == ' ' || *p == ':' || *p == '\n' || *p == '\r') p++;
    if (*p != '"')
        return 0;
    p++;

    while (*p && *p != '"' && i < out_sz - 1)
        out[i++] = *p++;
    out[i] = '\0';
    return 1;
}

int json_has_key(const char *json, const char *key)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\"", key);
    return strstr(json, search) != NULL;
}
