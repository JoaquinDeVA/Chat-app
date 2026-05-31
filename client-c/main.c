#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <ncurses.h>
#include "protocol.h"
#include "network.h"
#include "app_state.h"
#include "tui.h"

#define CONFIG_FILE "config.txt"

// Lee ip y puerto del config.txt
// Formato: "ip = x.x.x.x" y "puerto = XXXX"
//prueba de comentarios
static int load_config(char *ip, size_t ip_sz, int *port)
{
    FILE *f = fopen(CONFIG_FILE, "r");
    if (!f) {
        fprintf(stderr, "No se encontro %s\n", CONFIG_FILE);
        return -1;
    }

    char line[256];
    while (fgets(line, sizeof(line), f)) {
        if (line[0] == '#' || line[0] == '\n') continue;

        char key[64], val[128];
        if (sscanf(line, " %63[^=] = %127s", key, val) != 2) continue;

        char *end = key + strlen(key) - 1;
        while (end > key && *end == ' ') *end-- = '\0';

        if (strcmp(key, "ip") == 0)
            strncpy(ip, val, ip_sz - 1);
        else if (strcmp(key, "puerto") == 0)
            *port = atoi(val);
    }

    fclose(f);
    return 0;
}

// Estado global. En heap porque es demasiado grande para el stack.
typedef struct {
    NetworkClient net;
    AppSession    session;
    TUI           tui;
    AppState      state;
    AuthMode      auth_mode;
    LiveMode      live_mode;
    int           connected;
    char          connect_err[256];
    int           needs_redraw;
    char          ip[64];
    int           port;
} App;

static int app_connect(App *a)
{
    if (net_connect(&a->net, a->ip, a->port) < 0) {
        snprintf(a->connect_err, sizeof(a->connect_err),
                 "No se pudo conectar a %s:%d", a->ip, a->port);
        a->connected = 0;
        return -1;
    }
    a->connected      = 1;
    a->connect_err[0] = '\0';
    return 0;
}

// Manda JSON y espera respuesta. Loguea a stderr para debug.
static char *send_recv(App *a, const char *msg)
{
    fprintf(stderr, "[SEND] %s\n", msg);
    net_send(&a->net, msg);
    char *resp = net_recv(&a->net, 5000);
    fprintf(stderr, "[RECV] %s\n", resp ? resp : "NULL");
    return resp;
}

// El servidor usa "processed":1 para operaciones normales
// y "code":1 para login. Ambos significan OK.
static int resp_ok(const char *json)
{
    if (!json) return 0;

    const char *p = strstr(json, "\"processed\"");
    if (p) {
        p += strlen("\"processed\"");
        while (*p == ' ' || *p == ':' || *p == '\n' || *p == '\r') p++;
        if (*p == '1' || strncmp(p, "true", 4) == 0)
            return 1;
    }

    const char *c = strstr(json, "\"code\"");
    if (c) {
        c += strlen("\"code\"");
        while (*c == ' ' || *c == ':' || *c == '\n' || *c == '\r') c++;
        if (*c == '1') return 1;
    }

    return 0;
}

// Procesa un mensaje que llega del servidor en tiempo real
// y lo mete en la sesion local.
static void apply_push(App *a, const char *json)
{
    char chatname[MAX_NAME]   = "";
    char author[MAX_NAME]     = "";
    char content[MAX_MSG_LEN] = "";
    char date[32]             = "";

    parse_str(json, "chatname",  chatname, sizeof(chatname));
    parse_str(json, "author",    author,   sizeof(author));
    parse_str(json, "contents",  content,  sizeof(content));
    parse_str(json, "sent",      date,     sizeof(date));

    if (!chatname[0]) return;

    int idx = session_find_chat(&a->session, chatname);
    if (idx < 0) {
        idx = session_add_chat(&a->session, chatname);
        a->tui.chat_selection = idx;
    }

    if (author[0])
        session_add_message(&a->session, idx, author, content, date);

    a->needs_redraw = 1;
}

// -- AUTH --

static void handle_auth_menu(App *a)
{
    tui_draw_auth_menu(a->connect_err);
    int key = getch();

    if (key == 'l')      a->auth_mode = AUTH_LOGIN;
    else if (key == 'r') a->auth_mode = AUTH_REGISTER;
    else if (key == 'q') a->state     = STATE_EXIT;

    usleep(50000);
}

static void handle_login(App *a)
{
    if (!a->connected) {
        if (app_connect(a) < 0) {
            tui_draw_error(a->connect_err);
            a->auth_mode = AUTH_MENU;
            return;
        }
    }

    char user[MAX_NAME] = "";
    char pass[MAX_NAME] = "";
    tui_draw_login_form(user, pass);

    if (!user[0] || !pass[0]) {
        tui_draw_error("Usuario y contrasena obligatorios");
        a->auth_mode = AUTH_MENU;
        return;
    }

    char  buf[BUF_SIZE];
    proto_login(buf, sizeof(buf), user, pass);
    char *resp = send_recv(a, buf);

    if (!resp) {
        tui_draw_error("Sin respuesta del servidor");
        a->auth_mode = AUTH_MENU;
        return;
    }

    if (!resp_ok(resp)) {
        char errmsg[256] = "Error de autenticacion";
        parse_str(resp, "msg", errmsg, sizeof(errmsg));
        tui_draw_error(errmsg);
        free(resp);
        a->auth_mode = AUTH_MENU;
        return;
    }

    strncpy(a->session.username, user, MAX_NAME - 1);
    a->session.authenticated = 1;

    if (json_has_key(resp, "conversations"))
        session_parse_convs(&a->session, resp);

    free(resp);

    // Pedir historial de conversaciones desde el principio.
    // Timeout corto (2s) por si el servidor aun no lo implementa.
    proto_load_delta(buf, sizeof(buf), user, "1970-01-01");
    fprintf(stderr, "[SEND] %s\n", buf);
    net_send(&a->net, buf);
    char *delta = net_recv(&a->net, 10000);
    fprintf(stderr, "[RECV delta] %s\n", delta ? delta : "NULL");
    if (delta) {
        if (json_has_key(delta, "conversations"))
            session_parse_convs(&a->session, delta);
        free(delta);
    }

    a->state        = STATE_LIVE;
    a->needs_redraw = 1;
    nodelay(stdscr, TRUE);
    curs_set(0);
}

// El servidor manda 2 mensajes tras el registro:
//   1. confirmacion del registro
//   2. auto-login con conversaciones
static void handle_register(App *a)
{
    if (!a->connected) {
        if (app_connect(a) < 0) {
            tui_draw_error(a->connect_err);
            a->auth_mode = AUTH_MENU;
            return;
        }
    }

    char user[MAX_NAME] = "";
    char pass[MAX_NAME] = "";
    tui_draw_register_form(user, pass);

    if (!user[0] || !pass[0]) {
        tui_draw_error("Usuario y contrasena obligatorios");
        a->auth_mode = AUTH_MENU;
        return;
    }

    char buf[BUF_SIZE];
    proto_create_user(buf, sizeof(buf), user, pass);
    net_send(&a->net, buf);

    char *resp1 = net_recv(&a->net, 5000);
    fprintf(stderr, "[RECV register msg1] %s\n", resp1 ? resp1 : "NULL");
    if (!resp1 || !resp_ok(resp1)) {
        if (resp1) free(resp1);
        tui_draw_error("Error en el registro");
        a->auth_mode = AUTH_MENU;
        return;
    }
    free(resp1);

    char *resp2 = net_recv(&a->net, 5000);
    fprintf(stderr, "[RECV register msg2] %s\n", resp2 ? resp2 : "NULL");

    strncpy(a->session.username, user, MAX_NAME - 1);
    a->session.authenticated = 1;

    if (resp2) {
        if (json_has_key(resp2, "conversations"))
            session_parse_convs(&a->session, resp2);
        free(resp2);
    }

    a->state        = STATE_LIVE;
    a->needs_redraw = 1;
    nodelay(stdscr, TRUE);
    curs_set(0);
}

static void handle_auth(App *a)
{
    if (a->auth_mode == AUTH_MENU)         handle_auth_menu(a);
    else if (a->auth_mode == AUTH_LOGIN)   handle_login(a);
    else if (a->auth_mode == AUTH_REGISTER) handle_register(a);
}

// -- LIVE --

// Navega por chats con flechas y drena mensajes push del servidor.
static void handle_navigation(App *a)
{
    nodelay(stdscr, TRUE);
    int key = getch();

    char *push;
    while ((push = net_try_recv(&a->net)) != NULL) {
        apply_push(a, push);
        free(push);
    }

    if (key == -1) { usleep(50000); return; }

    if (key == 'q') {
        a->state = STATE_EXIT;

    } else if (key == KEY_UP) {
        if (a->session.active_chat > 0) {
            a->session.active_chat--;
            a->tui.chat_selection = a->session.active_chat;
            a->needs_redraw = 1;
        }

    } else if (key == KEY_DOWN) {
        if (a->session.active_chat < a->session.nchats - 1) {
            a->session.active_chat++;
            a->tui.chat_selection = a->session.active_chat;
            a->needs_redraw = 1;
        }

    } else if (key == '\n' || key == ' ') {
        if (a->session.active_chat >= 0) {
            a->live_mode    = LIVE_INPUT;
            a->needs_redraw = 1;
        }

    } else if (key == 'n') {
        a->live_mode    = LIVE_NEWCHAT;
        a->needs_redraw = 1;
    }
}

// Lee un mensaje y lo manda. Si falla lo marca como [FALLIDO].
static void handle_message_input(App *a)
{
    curs_set(1);
    nodelay(stdscr, FALSE);

    tui_set_status(&a->tui, "Escribiendo... (ENTER para enviar)");
    tui_draw(&a->tui, &a->session);
    tui_get_input(&a->tui);

    char *msg = a->tui.input;
    while (*msg == ' ') msg++;
    int len = strlen(msg);
    while (len > 0 && msg[len - 1] == ' ') msg[--len] = '\0';

    if (len > 0 && a->session.active_chat >= 0) {
        char *chat = a->session.chats[a->session.active_chat].name;
        char  buf[BUF_SIZE];
        proto_send_msg(buf, sizeof(buf), chat, msg, a->session.username);
        char *resp = send_recv(a, buf);

        if (resp_ok(resp)) {
            session_add_message(&a->session, a->session.active_chat,
                                a->session.username, msg, "");
            tui_set_status(&a->tui, "Mensaje enviado");
        } else {
            char failed[MAX_MSG_LEN];
            snprintf(failed, sizeof(failed), "[FALLIDO] %s", msg);
            session_add_message(&a->session, a->session.active_chat,
                                a->session.username, failed, "");
            tui_set_status(&a->tui, "Error enviando mensaje");
        }

        if (resp) free(resp);
    }

    a->live_mode    = LIVE_NAVIGATION;
    a->needs_redraw = 1;
    curs_set(0);
    nodelay(stdscr, TRUE);
}

// Crea un chat nuevo. El creador se añade automaticamente.
static void handle_newchat(App *a)
{
    char name[MAX_NAME]  = "";
    char parts[BUF_SIZE] = "";
    tui_draw_newchat_form(name, parts);

    if (!name[0] || !parts[0]) {
        a->live_mode    = LIVE_NAVIGATION;
        a->needs_redraw = 1;
        return;
    }

    const char *participants[MAX_CHATS + 1];
    char        parts_copy[BUF_SIZE];
    strncpy(parts_copy, parts, sizeof(parts_copy) - 1);

    int   nparts = 0;
    char *tok    = strtok(parts_copy, ",");
    participants[nparts++] = a->session.username;
    while (tok && nparts < MAX_CHATS) {
        while (*tok == ' ') tok++;
        if (strcmp(tok, a->session.username) != 0)
            participants[nparts++] = tok;
        tok = strtok(NULL, ",");
    }

    char buf[BUF_SIZE];
    proto_create_chat(buf, sizeof(buf), name, participants, nparts);
    char *resp = send_recv(a, buf);

    if (resp_ok(resp)) {
        int idx = session_find_chat(&a->session, name);
        if (idx < 0)
            idx = session_add_chat(&a->session, name);
        a->session.active_chat = idx;
        a->tui.chat_selection  = idx;
        tui_set_status(&a->tui, "Chat creado");
    } else {
        tui_set_status(&a->tui, "Error creando chat");
    }

    if (resp) free(resp);
    a->live_mode    = LIVE_NAVIGATION;
    a->needs_redraw = 1;
    nodelay(stdscr, TRUE);
}

static void handle_live(App *a)
{
    if (a->needs_redraw) {
        char status[256];
        snprintf(status, sizeof(status),
                 "Conectado como %s | UP/DOWN: navegar | ENTER: escribir | n: nuevo chat | q: salir",
                 a->session.username);
        tui_set_status(&a->tui, status);
        tui_draw(&a->tui, &a->session);
        a->needs_redraw = 0;
    }

    if (a->live_mode == LIVE_NAVIGATION)    handle_navigation(a);
    else if (a->live_mode == LIVE_INPUT)    handle_message_input(a);
    else if (a->live_mode == LIVE_NEWCHAT)  handle_newchat(a);
}

int main(void)
{
    App *a = calloc(1, sizeof(App));
    if (!a) {
        fprintf(stderr, "Error de memoria\n");
        return 1;
    }

    a->state        = STATE_AUTH;
    a->auth_mode    = AUTH_MENU;
    a->live_mode    = LIVE_NAVIGATION;
    a->needs_redraw = 1;

    if (load_config(a->ip, sizeof(a->ip), &a->port) < 0) {
        free(a);
        return 1;
    }

    session_init(&a->session);
    tui_init(&a->tui);
    app_connect(a);

    while (a->state != STATE_EXIT) {
        if (a->state == STATE_AUTH)         handle_auth(a);
        else if (a->state == STATE_LIVE)    handle_live(a);
    }

    if (a->session.authenticated && a->connected) {
        char buf[BUF_SIZE];
        proto_logout(buf, sizeof(buf));
        net_send(&a->net, buf);
    }

    net_close(&a->net);
    tui_cleanup();
    free(a);
    return 0;
}
