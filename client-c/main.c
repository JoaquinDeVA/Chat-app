/*
 * main.c - the chat client: screens and key handling on top of the network, protocol and
 * session modules.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "config.h"
#include "json.h"
#include "network.h"
#include "protocol.h"
#include "session.h"
#include "tui.h"

#define REPLY_TIMEOUT_MS 5000
#define DELTA_TIMEOUT_MS 10000
#define POLL_INTERVAL_MS 100

static const char *environment(const char *name)
{
    return getenv(name);
}

typedef enum { STATE_AUTH, STATE_LIVE, STATE_EXIT } AppState;
typedef enum { AUTH_MENU, AUTH_LOGIN, AUTH_REGISTER } AuthMode;
typedef enum { LIVE_NAVIGATION, LIVE_INPUT, LIVE_NEWCHAT } LiveMode;

/* Too big for the stack, so it lives on the heap. */
typedef struct {
    NetworkClient net;
    Session session;
    TUI tui;
    ServerAddress address;
    AppState state;
    AuthMode auth_mode;
    LiveMode live_mode;
    int connected;
    char connect_error[256];
    int needs_redraw;
} App;

/* Connects and opens the conversation with the protocol version this client speaks. */
static int app_connect(App *a)
{
    char buf[BUF_SIZE], reason[200];
    char *reply;

    a->connected = 0;
    if (net_connect(&a->net, a->address.host, a->address.port) < 0) {
        snprintf(a->connect_error, sizeof(a->connect_error), "cannot reach %s:%d", a->address.host,
                 a->address.port);
        return -1;
    }
    if (proto_hello(buf, sizeof(buf)) < 0 || net_send(&a->net, buf) < 0 ||
        (reply = net_recv(&a->net, REPLY_TIMEOUT_MS)) == NULL) {
        snprintf(a->connect_error, sizeof(a->connect_error), "the server did not answer hello");
        net_close(&a->net);
        return -1;
    }
    if (!proto_reply_ok(reply)) {
        proto_reply_message(reply, reason, sizeof(reason), "hello refused");
        snprintf(a->connect_error, sizeof(a->connect_error), "%s (this client speaks protocol v%d)", reason,
                 PROTOCOL_VERSION);
        free(reply);
        net_close(&a->net);
        return -1;
    }
    free(reply);
    a->connected = 1;
    a->connect_error[0] = '\0';
    return 0;
}

/* Sends a request and waits for the reply; malloc'd, NULL on timeout or if it cannot be sent. */
static char *request(App *a, const char *json, int timeout_ms)
{
    if (net_send(&a->net, json) < 0)
        return NULL;
    return net_recv(&a->net, timeout_ms);
}

/* ── authentication ──────────────────────────────────────────────────────────────────────── */

static void load_history(App *a)
{
    char buf[BUF_SIZE];
    char *reply;
    char *stale;

    while ((stale = net_try_recv(&a->net)) != NULL) /* nothing received so far answers the request */
        free(stale);
    if (proto_load_delta(buf, sizeof(buf), EPOCH) < 0)
        return;
    reply = request(a, buf, DELTA_TIMEOUT_MS);
    if (reply) {
        session_apply_delta(&a->session, reply);
        free(reply);
    }
}

static void authenticate(App *a, int registering)
{
    char user[MAX_NAME] = "", pass[MAX_NAME] = "", buf[BUF_SIZE], message[256];
    char *reply;

    a->auth_mode = AUTH_MENU;
    if (!a->connected && app_connect(a) < 0) {
        tui_show_error(a->connect_error);
        return;
    }
    if (!tui_credentials_form(registering ? "REGISTER" : "LOG IN", user, sizeof(user), pass, sizeof(pass)))
        return;
    if (!user[0] || !pass[0]) {
        tui_show_error("Username and password are required");
        return;
    }

    if ((registering ? proto_create_user(buf, sizeof(buf), user, pass)
                     : proto_login(buf, sizeof(buf), user, pass)) < 0) {
        tui_show_error("Username or password too long");
        return;
    }
    reply = request(a, buf, REPLY_TIMEOUT_MS);
    if (!reply) {
        tui_show_error("No reply from the server");
        return;
    }
    if (!proto_reply_ok(reply)) {
        proto_reply_message(reply, message, sizeof(message), "Authentication failed");
        tui_show_error(message);
        free(reply);
        return;
    }
    free(reply);

    /* In protocol v1 a successful registration is a single reply that already means logged in. */
    snprintf(a->session.username, sizeof(a->session.username), "%s", user);
    a->session.authenticated = 1;
    load_history(a);
    a->state = STATE_LIVE;
    a->needs_redraw = 1;
}

static void handle_auth_menu(App *a)
{
    int key;

    tui_draw_auth_menu(a->connected, a->connect_error);
    key = getch(); /* blocks: the menu is drawn once, so it never flickers */
    if (key == 'l')
        a->auth_mode = AUTH_LOGIN;
    else if (key == 'r')
        a->auth_mode = AUTH_REGISTER;
    else if (key == 'q')
        a->state = STATE_EXIT;
}

/* ── chat screen ─────────────────────────────────────────────────────────────────────────── */

static void handle_navigation(App *a)
{
    char *push;
    int key;

    timeout(POLL_INTERVAL_MS);
    key = getch();

    while ((push = net_try_recv(&a->net)) != NULL) {
        if (session_apply_push(&a->session, push))
            a->needs_redraw = 1;
        free(push);
    }
    if (!net_alive(&a->net)) {
        tui_set_status(&a->tui, "Connection to the server lost (q to quit)");
        a->needs_redraw = 1;
    }
    if (key == ERR)
        return;

    if (key == 'q') {
        a->state = STATE_EXIT;
    } else if (key == KEY_UP && a->session.active_chat > 0) {
        a->tui.chat_selection = --a->session.active_chat;
        a->needs_redraw = 1;
    } else if (key == KEY_DOWN && a->session.active_chat < a->session.nchats - 1) {
        a->tui.chat_selection = ++a->session.active_chat;
        a->needs_redraw = 1;
    } else if ((key == '\n' || key == ' ') && a->session.active_chat >= 0) {
        a->live_mode = LIVE_INPUT;
    } else if (key == 'n') {
        a->live_mode = LIVE_NEWCHAT;
    }
}

static void trim(char *text)
{
    char *start = text;
    size_t length;

    while (*start == ' ')
        start++;
    memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && text[length - 1] == ' ')
        text[--length] = '\0';
}

static void handle_message_input(App *a)
{
    char text[BUF_SIZE / 2] = "", buf[BUF_SIZE], sent[DATE_LEN] = "";
    const char *chat = a->session.chats[a->session.active_chat].name;
    char *reply;
    int submitted;

    timeout(-1);
    tui_set_status(&a->tui, "Writing... (Enter sends, Esc cancels)");
    tui_draw(&a->tui, &a->session);
    submitted = tui_read_message(&a->tui, text, sizeof(text));
    trim(text);

    a->live_mode = LIVE_NAVIGATION;
    a->needs_redraw = 1;
    tui_set_status(&a->tui, "");
    if (!submitted || !text[0])
        return;

    if (proto_send_msg(buf, sizeof(buf), chat, text) < 0) {
        tui_set_status(&a->tui, "Message too long");
        return;
    }
    reply = request(a, buf, REPLY_TIMEOUT_MS);
    if (proto_reply_ok(reply)) {
        json_object_get_string(reply, "sent", sent, sizeof(sent));
        session_add_message(&a->session, a->session.active_chat, a->session.username, text, sent, 0);
        tui_set_status(&a->tui, "Sent");
    } else {
        session_add_message(&a->session, a->session.active_chat, a->session.username, text, "", 1);
        tui_set_status(&a->tui, "Could not send the message");
    }
    free(reply);
}

static void handle_newchat(App *a)
{
    char name[MAX_NAME] = "", list[BUF_SIZE / 2] = "", buf[BUF_SIZE];
    const char *participants[MAX_CHATS + 1];
    char *reply, *saveptr = NULL, *token;
    int count = 0;

    timeout(-1);
    a->live_mode = LIVE_NAVIGATION;
    a->needs_redraw = 1;
    tui_set_status(&a->tui, "");
    if (!tui_newchat_form(name, sizeof(name), list, sizeof(list)))
        return;
    trim(name);
    if (!name[0] || !list[0]) {
        tui_set_status(&a->tui, "A name and at least one participant are required");
        return;
    }

    participants[count++] = a->session.username; /* the creator is always a member */
    for (token = strtok_r(list, ",", &saveptr); token && count < MAX_CHATS; token = strtok_r(NULL, ",", &saveptr)) {
        trim(token);
        if (token[0] && strcmp(token, a->session.username) != 0)
            participants[count++] = token;
    }

    if (proto_create_chat(buf, sizeof(buf), name, participants, count) < 0) {
        tui_set_status(&a->tui, "Chat name or participant list too long");
        return;
    }
    reply = request(a, buf, REPLY_TIMEOUT_MS);
    if (proto_reply_ok(reply)) {
        a->session.active_chat = session_add_chat(&a->session, name);
        a->tui.chat_selection = a->session.active_chat;
        tui_set_status(&a->tui, "Chat created");
    } else {
        char message[256];

        proto_reply_message(reply, message, sizeof(message), "Could not create the chat");
        tui_set_status(&a->tui, message);
    }
    free(reply);
}

static void handle_live(App *a)
{
    if (a->needs_redraw) {
        if (!a->tui.status[0]) {
            char status[256];

            snprintf(status, sizeof(status), "%s | Up/Down: chats | Enter: write | n: new chat | q: quit",
                     a->session.username);
            tui_set_status(&a->tui, status);
        }
        tui_draw(&a->tui, &a->session);
        a->needs_redraw = 0;
    }

    if (a->live_mode == LIVE_NAVIGATION)
        handle_navigation(a);
    else if (a->live_mode == LIVE_INPUT)
        handle_message_input(a);
    else
        handle_newchat(a);
}

int main(int argc, char **argv)
{
    App *a = calloc(1, sizeof(App));
    char error[256], buf[BUF_SIZE];

    if (!a) {
        fprintf(stderr, "out of memory\n");
        return 1;
    }
    if (config_resolve(&a->address, argc, argv, environment, error, sizeof(error)) < 0) {
        fprintf(stderr, "%s\n", error);
        free(a);
        return 2;
    }

    session_init(&a->session);
    a->state = STATE_AUTH;
    a->auth_mode = AUTH_MENU;
    a->live_mode = LIVE_NAVIGATION;
    a->needs_redraw = 1;

    tui_init(&a->tui);
    app_connect(a);

    while (a->state != STATE_EXIT) {
        if (a->state == STATE_AUTH) {
            if (a->auth_mode == AUTH_MENU)
                handle_auth_menu(a);
            else
                authenticate(a, a->auth_mode == AUTH_REGISTER);
        } else {
            handle_live(a);
        }
    }

    if (a->session.authenticated && a->connected && proto_logout(buf, sizeof(buf)) == 0)
        net_send(&a->net, buf);
    if (a->connected)
        net_close(&a->net);
    tui_cleanup();
    free(a);
    return 0;
}
