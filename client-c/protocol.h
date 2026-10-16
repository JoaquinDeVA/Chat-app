/*
 * protocol.h - the messages of the client/server protocol (see docs/PROTOCOL.md).
 *
 * Every message is a JSON object followed by the end-of-transmission byte (EOT). The builders
 * write the JSON (without the EOT) into a caller's buffer and return 0, or -1 if it does not fit.
 * All text is escaped, so names and messages may contain quotes, backslashes or newlines.
 */
#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stddef.h>

#define EOT 0x04
/* The protocol version of this client: version 1, the simple one (plain ASCII text, no images). */
#define PROTOCOL_VERSION 1
#define BUF_SIZE 8192
#define MAX_NAME 64
#define MAX_MSG_LEN 1024
#define DATE_LEN 32
#define EPOCH "1970-01-01 00:00:00"

int proto_hello(char *buf, size_t size);
int proto_login(char *buf, size_t size, const char *user, const char *pass);
int proto_create_user(char *buf, size_t size, const char *user, const char *pass);
int proto_create_chat(char *buf, size_t size, const char *name, const char **participants, int count);
int proto_send_msg(char *buf, size_t size, const char *chat, const char *msg);
int proto_load_delta(char *buf, size_t size, const char *since);
int proto_logout(char *buf, size_t size);

/* 1 if a server reply reports success: "processed": 1 or "code": 1. */
int proto_reply_ok(const char *json);

/* "msg" of a reply, or fallback if it has none. */
void proto_reply_message(const char *json, char *out, size_t size, const char *fallback);

#endif
