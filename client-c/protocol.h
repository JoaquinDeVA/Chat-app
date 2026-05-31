#ifndef PROTOCOL_H
#define PROTOCOL_H

#define EOT        0x04
#define BUF_SIZE   8192
#define MAX_NAME   64

/* Construye JSONs pretty-print listos para enviar (sin EOT) */
void proto_login         (char *buf, size_t sz, const char *user, const char *pass);
void proto_create_user   (char *buf, size_t sz, const char *user, const char *pass);
void proto_create_chat   (char *buf, size_t sz, const char *name, const char **parts, int nparts);
void proto_send_msg      (char *buf, size_t sz, const char *chat, const char *msg, const char *user);
void proto_load_convs    (char *buf, size_t sz, const char *user);
void proto_load_delta    (char *buf, size_t sz, const char *user, const char *since);
void proto_logout        (char *buf, size_t sz);

/* Parseo mínimo de respuestas */
int  parse_code          (const char *json);
int  parse_str           (const char *json, const char *key, char *out, size_t out_sz);
int  json_has_key        (const char *json, const char *key);

#endif
