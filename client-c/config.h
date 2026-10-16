/* config.h - where the server is: command line, then environment, then defaults. */
#ifndef CONFIG_H
#define CONFIG_H

#include <stddef.h>

#define DEFAULT_HOST "127.0.0.1"
#define DEFAULT_PORT 6969

typedef struct {
    char host[128];
    int port;
} ServerAddress;

/*
 * Fills `out` from --host / --port, then CHAT_SERVER_HOST / CHAT_SERVER_PORT, then the defaults.
 * `getenv_fn` is getenv in production and a stub in tests. Returns 0 on success, -1 on an
 * invalid argument (the reason is written to error).
 */
int config_resolve(ServerAddress *out, int argc, char **argv, const char *(*getenv_fn)(const char *),
                   char *error, size_t error_size);

#endif
