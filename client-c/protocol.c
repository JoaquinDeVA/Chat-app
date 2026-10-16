#include "protocol.h"

#include <stdio.h>
#include <string.h>

#include "json.h"

/* Escapes text into a stack buffer sized for the worst case of the field. */
#define ESCAPED(name, size, text)                       \
    char name[size];                                    \
    if (json_escape((text), name, sizeof(name)) < 0)    \
        return -1

static int finish(int written, size_t size)
{
    return (written < 0 || (size_t)written >= size) ? -1 : 0;
}

static int credentials(char *buf, size_t size, const char *action, const char *user, const char *pass)
{
    ESCAPED(u, MAX_NAME * 6, user);
    ESCAPED(p, MAX_NAME * 6, pass);
    return finish(snprintf(buf, size, "{\"action\":\"%s\",\"username\":\"%s\",\"password\":\"%s\"}", action, u, p), size);
}

int proto_hello(char *buf, size_t size)
{
    return finish(snprintf(buf, size, "{\"action\":\"hello\",\"version\":%d}", PROTOCOL_VERSION), size);
}

int proto_login(char *buf, size_t size, const char *user, const char *pass)
{
    return credentials(buf, size, "login", user, pass);
}

int proto_create_user(char *buf, size_t size, const char *user, const char *pass)
{
    return credentials(buf, size, "create_user", user, pass);
}

int proto_create_chat(char *buf, size_t size, const char *name, const char **participants, int count)
{
    ESCAPED(n, MAX_NAME * 6, name);
    size_t used = (size_t)snprintf(buf, size, "{\"action\":\"create_chat\",\"chat_name\":\"%s\",\"participants\":[", n);

    for (int i = 0; i < count; i++) {
        ESCAPED(p, MAX_NAME * 6, participants[i]);
        if (used >= size)
            return -1;
        used += (size_t)snprintf(buf + used, size - used, "%s\"%s\"", i ? "," : "", p);
    }
    if (used >= size)
        return -1;
    return finish(snprintf(buf + used, size - used, "]}"), size - used);
}

int proto_send_msg(char *buf, size_t size, const char *chat, const char *msg)
{
    char text[BUF_SIZE];
    ESCAPED(c, MAX_NAME * 6, chat);
    if (json_escape(msg, text, sizeof(text)) < 0)
        return -1;
    return finish(snprintf(buf, size, "{\"action\":\"send_msg\",\"chat\":\"%s\",\"msg\":\"%s\"}", c, text), size);
}

int proto_load_delta(char *buf, size_t size, const char *since)
{
    ESCAPED(s, DATE_LEN * 6, since);
    return finish(snprintf(buf, size, "{\"action\":\"load_message_delta\",\"since\":\"%s\"}", s), size);
}

int proto_logout(char *buf, size_t size)
{
    return finish(snprintf(buf, size, "{\"action\":\"logout\"}"), size);
}

int proto_reply_ok(const char *json)
{
    long value;

    if (!json)
        return 0;
    if (json_object_get_long(json, "processed", &value) && value == 1)
        return 1;
    if (json_object_get_long(json, "code", &value) && value == 1)
        return 1;
    return 0;
}

void proto_reply_message(const char *json, char *out, size_t size, const char *fallback)
{
    if (!json || !json_object_get_string(json, "msg", out, size) || out[0] == '\0') {
        snprintf(out, size, "%s", fallback);
    }
}
