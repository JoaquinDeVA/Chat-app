/*
 * tui.h - ncurses presentation: the main screen, the forms and the line editor.
 *
 * ASCII only: the screen is drawn with plain characters and the user can type printable ASCII.
 * Nothing here decides anything: the screen is drawn from the session handed over and the text
 * typed by the user is returned.
 */
#ifndef TUI_H
#define TUI_H

#include <ncurses.h>

#include "session.h"

typedef struct {
    int height;
    int width;
    int chat_selection;
    char status[256];
} TUI;

void tui_init(TUI *t);
void tui_cleanup(void);
void tui_set_status(TUI *t, const char *msg);

/* Repaints the main screen: chat list, messages of the active chat, input bar, status line. */
void tui_draw(TUI *t, const Session *s);

/*
 * Reads a line at (y, x), at most `width` characters. Backspace edits, Tab shows or hides a
 * hidden field, Esc cancels. Returns 1 if the user pressed Enter, 0 if Esc.
 */
int tui_read_line(char *out, size_t size, int y, int x, int width, int hidden);

/* Reads a message in the input bar of the main screen (Esc cancels, returning 0). */
int tui_read_message(TUI *t, char *out, size_t size);

void tui_draw_auth_menu(int connected, const char *error);

/* Forms: return 1 when submitted, 0 when cancelled with Esc. */
int tui_credentials_form(const char *title, char *user, size_t user_size, char *pass, size_t pass_size);
int tui_newchat_form(char *name, size_t name_size, char *participants, size_t participants_size);

/* Shows an error and waits for a key. */
void tui_show_error(const char *msg);

#endif
