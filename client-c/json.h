/*
 * json.h - the small part of JSON this client needs.
 *
 * All functions work on NUL-terminated text that is not modified. They never read past the end
 * of the text and treat malformed input by returning NULL / 0, so a broken or hostile reply
 * cannot crash the client. Unlike searching the text for `"key"`, they follow the structure of
 * the document, so a message that happens to contain the text `"author"` is not mistaken for a
 * field.
 */
#ifndef JSON_H
#define JSON_H

#include <stddef.h>

/* First non-whitespace character at or after p. */
const char *json_skip_ws(const char *p);

/* Pointer just after the JSON value that starts at p, or NULL if it is malformed. */
const char *json_skip_value(const char *p);

/*
 * Decodes the string that starts at the opening quote p into out (always NUL-terminated, cut if
 * out is too small). Handles the escapes \" \\ \/ \b \f \n \r \t; \uXXXX gives the character if it is
 * ASCII and '?' otherwise (this client is ASCII-only). Returns the pointer just after the
 * closing quote, or NULL if the string is malformed.
 */
const char *json_read_string(const char *p, char *out, size_t out_size);

/* Value of member `key` of the object that starts at '{', or NULL if there is none. */
const char *json_object_get(const char *object, const char *key);

/* Convenience getters on top of json_object_get; return 1 on success, 0 otherwise. */
int json_object_get_string(const char *object, const char *key, char *out, size_t out_size);
int json_object_get_long(const char *object, const char *key, long *out);

/* 1 if the object has a member `key`. */
int json_object_has(const char *object, const char *key);

/* Iteration. A callback returns 0 to go on, anything else to stop; the iteration function
 * returns 0 on success, 1 if stopped by a callback, -1 if the JSON is malformed. */
typedef int (*json_member_fn)(const char *key, const char *value, void *ctx);
typedef int (*json_element_fn)(const char *element, void *ctx);
int json_each_member(const char *object, json_member_fn fn, void *ctx);
int json_each_element(const char *array, json_element_fn fn, void *ctx);

/*
 * Writes `in` as the body of a JSON string (no surrounding quotes) into out.
 * Returns the number of bytes written (excluding the NUL), or -1 if out is too small.
 */
int json_escape(const char *in, char *out, size_t out_size);

#endif
