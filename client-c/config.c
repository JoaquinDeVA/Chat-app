#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int parse_port(const char *text, int *port)
{
    char *end;
    long value = strtol(text, &end, 10);

    if (end == text || *end != '\0' || value < 1 || value > 65535)
        return -1;
    *port = (int)value;
    return 0;
}

int config_resolve(ServerAddress *out, int argc, char **argv, const char *(*getenv_fn)(const char *),
                   char *error, size_t error_size)
{
    const char *value;

    snprintf(out->host, sizeof(out->host), "%s", DEFAULT_HOST);
    out->port = DEFAULT_PORT;

    if ((value = getenv_fn("CHAT_SERVER_HOST")) && *value)
        snprintf(out->host, sizeof(out->host), "%s", value);
    if ((value = getenv_fn("CHAT_SERVER_PORT")) && *value && parse_port(value, &out->port) < 0) {
        snprintf(error, error_size, "CHAT_SERVER_PORT=%s is not a valid port (1-65535)", value);
        return -1;
    }

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--host") == 0 && i + 1 < argc) {
            snprintf(out->host, sizeof(out->host), "%s", argv[++i]);
        } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            if (parse_port(argv[++i], &out->port) < 0) {
                snprintf(error, error_size, "--port %s is not a valid port (1-65535)", argv[i]);
                return -1;
            }
        } else {
            snprintf(error, error_size, "usage: chat-client [--host HOST] [--port PORT] (got '%s')", argv[i]);
            return -1;
        }
    }
    return 0;
}
