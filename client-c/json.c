#include "json.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define KEY_BUFFER 128
#define MAX_DEPTH 64

const char *json_skip_ws(const char *p)
{
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')
        p++;
    return p;
}

static const char *skip_string(const char *p)
{
    if (*p != '"')
        return NULL;
    for (p++; *p; p++) {
        if (*p == '\\') {
            if (!p[1])
                return NULL;
            p++;
        } else if (*p == '"') {
            return p + 1;
        }
    }
    return NULL;
}

static const char *skip_value(const char *p, int depth)
{
    if (depth > MAX_DEPTH)
        return NULL;
    p = json_skip_ws(p);

    if (*p == '"')
        return skip_string(p);

    if (*p == '{' || *p == '[') {
        char close = (*p == '{') ? '}' : ']';
        p = json_skip_ws(p + 1);
        if (*p == close)
            return p + 1;
        for (;;) {
            if (close == '}') {
                p = skip_string(json_skip_ws(p));
                if (!p)
                    return NULL;
                p = json_skip_ws(p);
                if (*p != ':')
                    return NULL;
                p++;
            }
            p = skip_value(p, depth + 1);
            if (!p)
                return NULL;
            p = json_skip_ws(p);
            if (*p == ',') {
                p++;
                continue;
            }
            return (*p == close) ? p + 1 : NULL;
        }
    }

    /* number, true, false, null */
    const char *start = p;
    while (*p && *p != ',' && *p != '}' && *p != ']' && *p != ' ' && *p != '\n' && *p != '\r' && *p != '\t')
        p++;
    return p > start ? p : NULL;
}

const char *json_skip_value(const char *p)
{
    return skip_value(p, 0);
}

static int hex4(const char *p)
{
    int value = 0;
    for (int i = 0; i < 4; i++) {
        char c = p[i];
        value <<= 4;
        if (c >= '0' && c <= '9')
            value |= c - '0';
        else if (c >= 'a' && c <= 'f')
            value |= c - 'a' + 10;
        else if (c >= 'A' && c <= 'F')
            value |= c - 'A' + 10;
        else
            return -1;
    }
    return value;
}

const char *json_read_string(const char *p, char *out, size_t out_size)
{
    size_t length = 0;

    if (*p != '"' || out_size == 0)
        return NULL;
    for (p++; *p && *p != '"'; p++) {
        char c = *p;

        if (c == '\\') {
            p++;
            switch (*p) {
            case '"':  c = '"';  break;
            case '\\': c = '\\'; break;
            case '/':  c = '/';  break;
            case 'b':  c = '\b'; break;
            case 'f':  c = '\f'; break;
            case 'n':  c = '\n'; break;
            case 'r':  c = '\r'; break;
            case 't':  c = '\t'; break;
            case 'u': {
                int unit = hex4(p + 1);
                if (unit < 0)
                    return NULL;
                p += 4;
                c = (unit < 0x80) ? (char)unit : '?';
                break;
            }
            default:
                return NULL;
            }
        }
        if (length + 1 < out_size)
            out[length++] = c;
    }
    if (*p != '"')
        return NULL;
    out[length] = '\0';
    return p + 1;
}

int json_each_member(const char *object, json_member_fn fn, void *ctx)
{
    const char *p = json_skip_ws(object);
    if (*p != '{')
        return -1;
    p = json_skip_ws(p + 1);
    if (*p == '}')
        return 0;
    for (;;) {
        char key[KEY_BUFFER];
        p = json_read_string(json_skip_ws(p), key, sizeof(key));
        if (!p)
            return -1;
        p = json_skip_ws(p);
        if (*p != ':')
            return -1;
        const char *value = json_skip_ws(p + 1);
        if (fn(key, value, ctx))
            return 1;
        p = json_skip_value(value);
        if (!p)
            return -1;
        p = json_skip_ws(p);
        if (*p == ',') {
            p++;
            continue;
        }
        return *p == '}' ? 0 : -1;
    }
}

int json_each_element(const char *array, json_element_fn fn, void *ctx)
{
    const char *p = json_skip_ws(array);
    if (*p != '[')
        return -1;
    p = json_skip_ws(p + 1);
    if (*p == ']')
        return 0;
    for (;;) {
        const char *element = json_skip_ws(p);
        if (fn(element, ctx))
            return 1;
        p = json_skip_value(element);
        if (!p)
            return -1;
        p = json_skip_ws(p);
        if (*p == ',') {
            p++;
            continue;
        }
        return *p == ']' ? 0 : -1;
    }
}

struct find {
    const char *key;
    const char *value;
};

static int find_member(const char *key, const char *value, void *ctx)
{
    struct find *f = ctx;
    if (strcmp(key, f->key) == 0) {
        f->value = value;
        return 1;
    }
    return 0;
}

const char *json_object_get(const char *object, const char *key)
{
    struct find f = { key, NULL };
    json_each_member(object, find_member, &f);
    return f.value;
}

int json_object_has(const char *object, const char *key)
{
    return json_object_get(object, key) != NULL;
}

int json_object_get_string(const char *object, const char *key, char *out, size_t out_size)
{
    const char *value = json_object_get(object, key);
    return value && json_read_string(value, out, out_size) != NULL;
}

int json_object_get_long(const char *object, const char *key, long *out)
{
    const char *value = json_object_get(object, key);
    char *end;
    long number;

    if (!value)
        return 0;
    number = strtol(value, &end, 10);
    if (end == value)
        return 0;
    *out = number;
    return 1;
}

int json_escape(const char *in, char *out, size_t out_size)
{
    size_t length = 0;

    for (; *in; in++) {
        unsigned char c = (unsigned char)*in;
        char piece[8];
        int piece_length;

        switch (c) {
        case '"':  strcpy(piece, "\\\""); piece_length = 2; break;
        case '\\': strcpy(piece, "\\\\"); piece_length = 2; break;
        case '\n': strcpy(piece, "\\n");  piece_length = 2; break;
        case '\r': strcpy(piece, "\\r");  piece_length = 2; break;
        case '\t': strcpy(piece, "\\t");  piece_length = 2; break;
        default:
            if (c < 0x20)
                piece_length = snprintf(piece, sizeof(piece), "\\u%04x", c);
            else {
                piece[0] = (char)c;
                piece_length = 1;
            }
        }
        if (length + (size_t)piece_length + 1 > out_size)
            return -1;
        memcpy(out + length, piece, (size_t)piece_length);
        length += (size_t)piece_length;
    }
    if (length + 1 > out_size)
        return -1;
    out[length] = '\0';
    return (int)length;
}
