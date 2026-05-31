#ifndef TUI_H
#define TUI_H

#define _XOPEN_SOURCE_EXTENDED 1
#include <ncurses.h>
#include "app_state.h"

typedef struct {
    WINDOW *win;
    int     height;
    int     width;
    int     chat_selection;
    int     scroll;
    char    input[BUF_SIZE];
    char    status[256];
} TUI;

void tui_init       (TUI *t);
void tui_draw       (TUI *t, AppSession *s);
void tui_get_input  (TUI *t);
void tui_set_status (TUI *t, const char *msg);
void tui_cleanup    (void);

/* Pantallas de auth */
void tui_draw_auth_menu    (const char *connect_err);
void tui_draw_login_form   (char *user_out, char *pass_out);
void tui_draw_register_form(char *user_out, char *pass_out);
void tui_draw_newchat_form (char *name_out, char *parts_out);
void tui_draw_error        (const char *msg);
void tui_draw_info         (const char *msg);

#endif
