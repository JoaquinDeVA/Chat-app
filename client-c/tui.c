#define _XOPEN_SOURCE_EXTENDED 1
#include <string.h>
#include <stdlib.h>
#include "tui.h"

void tui_init(TUI *t)
{
    initscr();
    cbreak();
    noecho();
    keypad(stdscr, TRUE);
    curs_set(0);
    nodelay(stdscr, TRUE);

    if (has_colors()) {
        start_color();
        use_default_colors();
        init_pair(1, COLOR_RED,   -1);
        init_pair(2, COLOR_GREEN, -1);
        init_pair(3, COLOR_CYAN,  -1);
    }

    t->win            = stdscr;
    t->chat_selection = 0;
    t->scroll         = 0;
    t->input[0]       = '\0';
    t->status[0]      = '\0';

    getmaxyx(stdscr, t->height, t->width);
}

void tui_cleanup(void)
{
    endwin();
}

void tui_set_status(TUI *t, const char *msg)
{
    strncpy(t->status, msg, sizeof(t->status) - 1);
}

/* ── Pantalla principal de chat ── */

void tui_draw(TUI *t, AppSession *s)
{
    getmaxyx(stdscr, t->height, t->width);
    clear();

    int chat_w = t->width / 4;
    if (chat_w < 20) chat_w = 20;

    /* ── Panel izquierdo: lista de chats ── */
    attron(A_BOLD);
    mvaddstr(0, 0, "CHATS");
    attroff(A_BOLD);

    if (s->nchats == 0) {
        attron(A_DIM);
        mvaddstr(1, 0, "(sin chats)");
        attroff(A_DIM);
    } else {
        for (int i = 0; i < s->nchats && i < t->height - 4; i++) {
            int is_active   = (i == s->active_chat);
            int is_selected = (i == t->chat_selection);
            int attr        = 0;
            const char *prefix;

            if (is_active && is_selected) {
                attr   = A_REVERSE | A_BOLD;
                prefix = "► ";
            } else if (is_active) {
                attr   = A_BOLD;
                prefix = "● ";
            } else if (is_selected) {
                attr   = A_REVERSE;
                prefix = "  ";
            } else {
                attr   = 0;
                prefix = "  ";
            }

            char display[MAX_NAME + 4];
            snprintf(display, sizeof(display), "%s%s", prefix, s->chats[i].name);

            if (attr) attron(attr);
            /* Rellenar hasta chat_w para que el reverse se vea bien */
            mvprintw(i + 1, 0, "%-*.*s", chat_w - 1, chat_w - 1, display);
            if (attr) attroff(attr);
        }
    }

    /* ── Divisor vertical ── */
    for (int row = 0; row < t->height - 1; row++) {
        mvaddch(row, chat_w, ACS_VLINE);
    }

    /* ── Panel derecho: mensajes ── */
    int msg_x = chat_w + 2;
    int msg_w = t->width - msg_x - 1;
    int msg_h = t->height - 5;

    const char *chat_name = "(ningún chat)";
    if (s->active_chat >= 0 && s->active_chat < s->nchats)
        chat_name = s->chats[s->active_chat].name;

    attron(A_BOLD);
    mvprintw(0, msg_x, "╔ %.*s ╗", msg_w - 4, chat_name);
    attroff(A_BOLD);

    /* Mensajes visibles */
    if (s->active_chat >= 0 && s->active_chat < s->nchats) {
        Chat *c    = &s->chats[s->active_chat];
        int   start = c->nmsg - msg_h - t->scroll;
        if (start < 0) start = 0;
        int   end   = c->nmsg - t->scroll;
        if (end > c->nmsg) end = c->nmsg;

        for (int i = start; i < end; i++) {
            Message *m   = &c->msgs[i];
            int      row = 1 + (i - start);

            int is_failed = strncmp(m->content, "[FALLIDO]", 9) == 0;
            if (is_failed && has_colors())
                attron(COLOR_PAIR(1) | A_BOLD);

            int author_w  = (int)strnlen(m->author, MAX_NAME - 1);
            int content_w = msg_w - author_w - 2; /* ": " = 2 chars */
            if (content_w < 1) content_w = 1;

            mvprintw(row, msg_x, "%.*s: %.*s",
                     MAX_NAME - 1, m->author,
                     content_w, m->content);

            if (is_failed && has_colors())
                attroff(COLOR_PAIR(1) | A_BOLD);
        }
    }

    /* ── Separador antes del input ── */
    move(t->height - 3, 0);
    hline(ACS_HLINE, t->width - 1);

    /* ── Línea de input ── */
    mvaddstr(t->height - 2, 0, "Mensaje: ");
    mvprintw(t->height - 2, 9, "%.*s", t->width - 10, t->input);

    /* ── Status ── */
    attron(A_DIM);
    mvprintw(t->height - 1, 0, "%.*s", t->width - 1, t->status);
    attroff(A_DIM);

    refresh();
}

/* ── Leer texto del usuario ── */

void tui_get_input(TUI *t)
{
    int  input_y = t->height - 2;
    int  start_x = 9;

    curs_set(1);
    nodelay(stdscr, FALSE);
    t->input[0] = '\0';
    int len     = 0;

    while (1) {
        move(input_y, start_x);
        clrtoeol();
        mvaddnstr(input_y, start_x, t->input, t->width - 10);
        refresh();

        int ch = getch();

        if (ch == '\n' || ch == '\r') {
            break;
        } else if (ch == KEY_BACKSPACE || ch == 127 || ch == 8) {
            if (len > 0)
                t->input[--len] = '\0';
        } else if (ch >= 32 && ch < 127 && len < BUF_SIZE - 2) {
            t->input[len++] = (char)ch;
            t->input[len]   = '\0';
        }
    }

    curs_set(0);
    nodelay(stdscr, TRUE);
}

/* ── Pantallas de autenticación ── */

static void wait_key(void)
{
    nodelay(stdscr, FALSE);
    getch();
    nodelay(stdscr, TRUE);
}

static void read_field(int y, int x, char *out, int max)
{
    echo();
    curs_set(1);
    move(y, x);
    clrtoeol();
    getnstr(out, max);
    noecho();
    curs_set(0);

    /* Quitar \n */
    int len = strlen(out);
    if (len > 0 && out[len - 1] == '\n')
        out[len - 1] = '\0';
}

void tui_draw_auth_menu(const char *connect_err)
{
    nodelay(stdscr, FALSE);
    clear();
    attron(A_BOLD);
    mvaddstr(2, 2, "MENSAJERIA");
    attroff(A_BOLD);

    if (!connect_err || connect_err[0] == '\0') {
        attron(A_DIM);
        mvaddstr(3, 2, "Conectado");
        attroff(A_DIM);
    } else {
        if (has_colors()) attron(COLOR_PAIR(1) | A_BOLD);
        mvprintw(3, 2, "Sin conexion: %s", connect_err);
        if (has_colors()) attroff(COLOR_PAIR(1) | A_BOLD);
    }

    mvaddstr(5, 2, "Elige una opcion:");
    mvaddstr(6, 4, "(l) Login");
    mvaddstr(7, 4, "(r) Registrarse");
    mvaddstr(8, 4, "(q) Salir");
    mvaddstr(10, 2, "Opcion: ");
    refresh();
}

void tui_draw_login_form(char *user_out, char *pass_out)
{
    nodelay(stdscr, FALSE);
    clear();
    attron(A_BOLD);
    mvaddstr(2, 2, "LOGIN");
    attroff(A_BOLD);

    mvaddstr(4, 2, "Usuario:  ");
    read_field(4, 12, user_out, MAX_NAME - 1);

    mvaddstr(5, 2, "Password: ");
    read_field(5, 12, pass_out, MAX_NAME - 1);
}

void tui_draw_register_form(char *user_out, char *pass_out)
{
    nodelay(stdscr, FALSE);
    clear();
    attron(A_BOLD);
    mvaddstr(2, 2, "REGISTRO");
    attroff(A_BOLD);

    mvaddstr(4, 2, "Usuario:  ");
    read_field(4, 12, user_out, MAX_NAME - 1);

    mvaddstr(5, 2, "Password: ");
    read_field(5, 12, pass_out, MAX_NAME - 1);
}

void tui_draw_newchat_form(char *name_out, char *parts_out)
{
    nodelay(stdscr, FALSE);
    clear();
    attron(A_BOLD);
    mvaddstr(2, 2, "CREAR NUEVO CHAT");
    attroff(A_BOLD);

    mvaddstr(4, 2, "Nombre: ");
    read_field(4, 10, name_out, MAX_NAME - 1);

    mvaddstr(5, 2, "Participantes (separados por comas): ");
    read_field(5, 38, parts_out, BUF_SIZE - 1);
}

void tui_draw_error(const char *msg)
{
    clear();
    attron(A_BOLD);
    mvaddstr(2, 2, "ERROR");
    attroff(A_BOLD);
    mvaddstr(4, 2, msg);
    mvaddstr(6, 2, "Presiona cualquier tecla...");
    refresh();
    wait_key();
}

void tui_draw_info(const char *msg)
{
    mvaddstr(8, 2, msg);
    refresh();
}
