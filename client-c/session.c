#include "session.h"

#include <stdio.h>
#include <string.h>

#include "json.h"

void session_init(Session *s)
{
    memset(s, 0, sizeof(*s));
    s->active_chat = -1;
}

int session_find_chat(const Session *s, const char *name)
{
    for (int i = 0; i < s->nchats; i++)
        if (strcmp(s->chats[i].name, name) == 0)
            return i;
    return -1;
}

int session_add_chat(Session *s, const char *name)
{
    int index = session_find_chat(s, name);

    if (index >= 0)
        return index;
    if (s->nchats >= MAX_CHATS || name[0] == '\0')
        return -1;

    index = s->nchats++;
    snprintf(s->chats[index].name, sizeof(s->chats[index].name), "%s", name);
    s->chats[index].nmsg = 0;
    if (s->active_chat < 0)
        s->active_chat = index;
    return index;
}

void session_add_message(Session *s, int chat, const char *author, const char *content, const char *date,
                         int failed)
{
    Chat *c;
    Message *m;

    if (chat < 0 || chat >= s->nchats)
        return;
    c = &s->chats[chat];
    if (c->nmsg >= MAX_MSGS) {
        memmove(&c->msgs[0], &c->msgs[1], sizeof(Message) * (MAX_MSGS - 1));
        c->nmsg = MAX_MSGS - 1;
    }

    m = &c->msgs[c->nmsg++];
    snprintf(m->author, sizeof(m->author), "%s", author);
    snprintf(m->content, sizeof(m->content), "%s", content);
    snprintf(m->date, sizeof(m->date), "%s", date);
    m->failed = failed;
}

/* Adds the message object `object` to `chat`. */
static void add_message_object(Session *s, int chat, const char *object)
{
    char author[MAX_NAME] = "?";
    char content[MAX_MSG_LEN + 1] = "";
    char sent[DATE_LEN] = "";

    json_object_get_string(object, "author", author, sizeof(author));
    json_object_get_string(object, "contents", content, sizeof(content));
    json_object_get_string(object, "sent", sent, sizeof(sent));
    session_add_message(s, chat, author, content, sent, 0);
}

struct delta {
    Session *session;
    int added;
    int chat;
};

static int delta_message(const char *element, void *ctx)
{
    struct delta *d = ctx;

    if (*element == '{') {
        add_message_object(d->session, d->chat, element);
        d->added++;
    }
    return 0;
}

static int delta_chat(const char *key, const char *value, void *ctx)
{
    struct delta *d = ctx;

    d->chat = session_add_chat(d->session, key);
    if (d->chat >= 0)
        json_each_element(value, delta_message, d);
    return 0;
}

int session_apply_delta(Session *s, const char *json)
{
    struct delta d = { s, 0, -1 };
    const char *conversations = json_object_get(json, "conversations");

    if (!conversations || json_each_member(conversations, delta_chat, &d) < 0)
        return -1;
    return d.added;
}

int session_apply_push(Session *s, const char *json)
{
    char chatname[MAX_NAME] = "";
    int before = s->nchats;
    int chat;

    if (!json_object_get_string(json, "chatname", chatname, sizeof(chatname)) || chatname[0] == '\0')
        return 0;
    chat = session_add_chat(s, chatname);
    if (chat < 0)
        return 0;

    if (json_object_has(json, "author")) {
        add_message_object(s, chat, json);
        return 1;
    }
    return s->nchats != before; /* a notice only matters if the chat is new */
}
