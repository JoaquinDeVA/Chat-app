#include "tui.h"

#include <string.h>

#define ESCAPE 27
#define INPUT_X 9 /* column where the text of the input bar starts, after "Message: " */

void tui_init(TUI *t)
{
    initscr();
    cbreak();
    noecho();
    keypad(stdscr, TRUE);
    set_escdelay(25); /* make the Esc key react at once */
    curs_set(0);

    if (has_colors()) {
        start_color();
        use_default_colors();
        init_pair(1, COLOR_RED, -1);
    }

    t->chat_selection = 0;
    t->status[0] = '\0';
    getmaxyx(stdscr, t->height, t->width);
}

void tui_cleanup(void)
{
    endwin();
}

void tui_set_status(TUI *t, const char *msg)
{
    snprintf(t->status, sizeof(t->status), "%s", msg);
}

/* ── main screen ─────────────────────────────────────────────────────────────────────────── */

static void draw_chat_list(const TUI *t, const Session *s, int chat_width)
{
    attron(A_BOLD);
    mvaddstr(0, 0, "CHATS");
    attroff(A_BOLD);

    if (s->nchats == 0) {
        attron(A_DIM);
        mvaddstr(1, 0, "(no chats)");
        attroff(A_DIM);
        return;
    }

    for (int i = 0; i < s->nchats && i < t->height - 4; i++) {
        int active = (i == s->active_chat), selected = (i == t->chat_selection);
        int attr = (active && selected) ? (A_REVERSE | A_BOLD) : active ? A_BOLD : selected ? A_REVERSE : 0;

        attron(attr);
        mvprintw(i + 1, 0, "%c %-*.*s", active ? '>' : ' ', chat_width - 3, chat_width - 3, s->chats[i].name);
        attroff(attr);
    }
}

static void draw_messages(const TUI *t, const Session *s, int x, int width)
{
    const Chat *chat;
    int rows = t->height - 5, first;

    if (s->active_chat < 0 || s->active_chat >= s->nchats)
        return;
    chat = &s->chats[s->active_chat];
    first = chat->nmsg > rows ? chat->nmsg - rows : 0;

    for (int i = first; i < chat->nmsg; i++) {
        const Message *m = &chat->msgs[i];
        int failed = m->failed && has_colors();

        if (failed)
            attron(COLOR_PAIR(1) | A_BOLD);
        mvprintw(1 + i - first, x, "%s%s: %.*s", m->failed ? "[FAILED] " : "", m->author, width, m->content);
        if (failed)
            attroff(COLOR_PAIR(1) | A_BOLD);
    }
}

void tui_draw(TUI *t, const Session *s)
{
    int chat_width, message_x, message_width;
    const char *title = "(no chat selected)";

    getmaxyx(stdscr, t->height, t->width);
    erase(); /* erase(), not clear(): clear() repaints the whole terminal and makes it flicker */

    chat_width = t->width / 4 < 20 ? 20 : t->width / 4;
    draw_chat_list(t, s, chat_width);
    for (int row = 0; row < t->height - 1; row++)
        mvaddch(row, chat_width, ACS_VLINE);

    message_x = chat_width + 2;
    message_width = t->width - message_x - 1;
    if (s->active_chat >= 0 && s->active_chat < s->nchats)
        title = s->chats[s->active_chat].name;
    attron(A_BOLD);
    mvprintw(0, message_x, "== %.*s ==", message_width - 6, title);
    attroff(A_BOLD);
    draw_messages(t, s, message_x, message_width);

    move(t->height - 3, 0);
    hline(ACS_HLINE, t->width - 1);
    mvaddstr(t->height - 2, 0, "Message: ");
    attron(A_DIM);
    mvprintw(t->height - 1, 0, "%.*s", t->width - 1, t->status);
    attroff(A_DIM);
    refresh();
}

/* ── line editor ─────────────────────────────────────────────────────────────────────────── */

int tui_read_line(char *out, size_t size, int y, int x, int width, int hidden)
{
    int reveal = 0, result = -1;
    size_t length = 0;

    out[0] = '\0';
    curs_set(1);
    nodelay(stdscr, FALSE);

    while (result < 0) {
        mvhline(y, x, ' ', width);
        if (hidden && !reveal) {
            for (size_t i = 0; i < length && (int)i < width; i++)
                mvaddch(y, x + (int)i, '*');
        } else {
            mvprintw(y, x, "%.*s", width, out);
        }
        move(y, x + ((int)length < width ? (int)length : width));
        refresh();

        int ch = getch();

        if (ch == '\n' || ch == '\r' || ch == KEY_ENTER) {
            result = 1;
        } else if (ch == ESCAPE) {
            result = 0;
        } else if (ch == '\t' && hidden) {
            reveal = !reveal;
        } else if (ch == KEY_BACKSPACE || ch == 127 || ch == 8) {
            if (length > 0)
                out[--length] = '\0';
        } else if (ch >= 32 && ch < 127 && length + 1 < size && (int)length < width) {
            out[length++] = (char)ch;
            out[length] = '\0';
        }
    }

    curs_set(0);
    return result;
}

int tui_read_message(TUI *t, char *out, size_t size)
{
    return tui_read_line(out, size, t->height - 2, INPUT_X, t->width - INPUT_X - 2, 0);
}

/* ── menu and forms ──────────────────────────────────────────────────────────────────────── */

void tui_draw_auth_menu(int connected, const char *error)
{
    nodelay(stdscr, FALSE);
    erase();
    attron(A_BOLD);
    mvaddstr(2, 2, "CHAT");
    attroff(A_BOLD);

    if (connected) {
        attron(A_DIM);
        mvaddstr(3, 2, "Connected");
        attroff(A_DIM);
    } else {
        if (has_colors())
            attron(COLOR_PAIR(1) | A_BOLD);
        mvprintw(3, 2, "No connection: %s", error);
        if (has_colors())
            attroff(COLOR_PAIR(1) | A_BOLD);
    }

    mvaddstr(5, 2, "Choose an option:");
    mvaddstr(6, 4, "(l) Log in");
    mvaddstr(7, 4, "(r) Register");
    mvaddstr(8, 4, "(q) Quit");
    mvaddstr(10, 2, "Option: ");
    refresh();
}

int tui_credentials_form(const char *title, char *user, size_t user_size, char *pass, size_t pass_size)
{
    erase();
    attron(A_BOLD);
    mvaddstr(2, 2, title);
    attroff(A_BOLD);
    attron(A_DIM);
    mvaddstr(7, 2, "Tab shows/hides the password, Esc cancels");
    mvaddstr(8, 2, "Names: letters, digits, '_', '-' and '.'");
    attroff(A_DIM);

    mvaddstr(4, 2, "Username: ");
    if (!tui_read_line(user, user_size, 4, 12, MAX_NAME - 1, 0))
        return 0;
    mvaddstr(5, 2, "Password: ");
    return tui_read_line(pass, pass_size, 5, 12, MAX_NAME - 1, 1);
}

int tui_newchat_form(char *name, size_t name_size, char *participants, size_t participants_size)
{
    erase();
    attron(A_BOLD);
    mvaddstr(2, 2, "NEW CHAT");
    attroff(A_BOLD);
    attron(A_DIM);
    mvaddstr(7, 2, "Esc cancels");
    attroff(A_DIM);

    mvaddstr(4, 2, "Name: ");
    if (!tui_read_line(name, name_size, 4, 8, MAX_NAME - 1, 0))
        return 0;
    mvaddstr(5, 2, "Participants (comma-separated): ");
    return tui_read_line(participants, participants_size, 5, 34, 100, 0);
}

void tui_show_error(const char *msg)
{
    erase();
    attron(A_BOLD);
    mvaddstr(2, 2, "ERROR");
    attroff(A_BOLD);
    mvaddstr(4, 2, msg);
    mvaddstr(6, 2, "Press any key...");
    refresh();
    nodelay(stdscr, FALSE);
    getch();
}
