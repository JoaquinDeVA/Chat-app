/* Unit tests of everything that is not the ncurses interface. Run with `make test`. */
#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#include "check.h"
#include "config.h"
#include "json.h"
#include "network.h"
#include "protocol.h"
#include "session.h"

/* ── json ────────────────────────────────────────────────────────────────────────────────── */

static void test_json_skips_values_by_structure(void)
{
    const char *doc = " {\"a\": [1, {\"b\": \"x]}\"}], \"c\": \"q\\\"uote\", \"d\": null} tail";
    const char *end = json_skip_value(doc);

    CHECK(end != NULL);
    CHECK_STR(end, " tail");
    CHECK(json_skip_value("{\"a\": ") == NULL);
    CHECK(json_skip_value("[1, 2") == NULL);
    CHECK(json_skip_value("\"unterminated") == NULL);
    CHECK(json_skip_value("{\"a\" 1}") == NULL);
    CHECK(json_skip_value("") == NULL);
}

static void test_json_strings_are_decoded(void)
{
    char out[64];

    CHECK(json_read_string("\"plain\"", out, sizeof(out)) != NULL);
    CHECK_STR(out, "plain");
    CHECK(json_read_string("\"a\\\"b\\\\c\\nd\\te\\/f\"", out, sizeof(out)) != NULL);
    CHECK_STR(out, "a\"b\\c\nd\te/f");
    CHECK(json_read_string("\"\\u0041\\u00f1\\u20ac\"", out, sizeof(out)) != NULL);
    CHECK_STR(out, "A??"); /* this client is ASCII-only: anything else becomes '?' */
}

static void test_json_strings_are_cut_and_malformed_ones_rejected(void)
{
    char small[5];
    const char *after = json_read_string("\"abcdefgh\" rest", small, sizeof(small));

    CHECK_STR(small, "abcd");
    CHECK_STR(after, " rest");
    CHECK(json_read_string("\"bad \\q escape\"", small, sizeof(small)) == NULL);
    CHECK(json_read_string("\"bad \\u12 unicode\"", small, sizeof(small)) == NULL);
    CHECK(json_read_string("no quote", small, sizeof(small)) == NULL);
    CHECK(json_read_string("\"open", small, sizeof(small)) == NULL);
}

static void test_json_object_members_are_found_at_the_top_level_only(void)
{
    const char *doc = "{\"inner\": {\"author\": \"nested\"}, \"text\": \"{\\\"author\\\": \\\"fake\\\"}\", \"author\": \"real\", \"n\": -42}";
    char value[32];
    long number;

    CHECK(json_object_get_string(doc, "author", value, sizeof(value)));
    CHECK_STR(value, "real");
    CHECK(json_object_get_long(doc, "n", &number));
    CHECK_INT(number, -42);
    CHECK(json_object_has(doc, "inner"));
    CHECK(!json_object_has(doc, "missing"));
    CHECK(!json_object_get_string(doc, "n", value, sizeof(value)));
    CHECK(!json_object_get_long(doc, "author", &number));
    CHECK(!json_object_has("not json", "a"));
}

struct counter {
    int members;
    int elements;
    int stop_at;
};

static int count_member(const char *key, const char *value, void *ctx)
{
    struct counter *c = ctx;
    (void)key;
    (void)value;
    return ++c->members == c->stop_at;
}

static int count_element(const char *element, void *ctx)
{
    struct counter *c = ctx;
    (void)element;
    return ++c->elements == c->stop_at;
}

static void test_json_iteration(void)
{
    struct counter c = { 0, 0, 0 };

    CHECK_INT(json_each_member("{\"a\":1,\"b\":[1,2],\"c\":{}}", count_member, &c), 0);
    CHECK_INT(c.members, 3);
    CHECK_INT(json_each_element("[1, \"x\", [2, 3], {}]", count_element, &c), 0);
    CHECK_INT(c.elements, 4);

    c = (struct counter){ 0, 0, 2 };
    CHECK_INT(json_each_member("{\"a\":1,\"b\":2,\"c\":3}", count_member, &c), 1);
    CHECK_INT(c.members, 2);

    CHECK_INT(json_each_member("{}", count_member, &c), 0);
    CHECK_INT(json_each_element("[]", count_element, &c), 0);
    CHECK_INT(json_each_member("{\"a\":}", count_member, &c), -1);
    CHECK_INT(json_each_element("[1 2]", count_element, &c), -1);
    CHECK_INT(json_each_member("[1]", count_member, &c), -1);
}

static void test_json_escape(void)
{
    char out[64];

    CHECK_INT(json_escape("a\"b\\c\n\t\r\x01", out, sizeof(out)), 19);
    CHECK_STR(out, "a\\\"b\\\\c\\n\\t\\r\\u0001");
    CHECK_INT(json_escape("", out, sizeof(out)), 0);
    CHECK_INT(json_escape("abcdef", out, 4), -1);
    CHECK_INT(json_escape("abc", out, 4), 3);
    CHECK_INT(json_escape("\"", out, 2), -1);
}

/* ── protocol ────────────────────────────────────────────────────────────────────────────── */

static void test_the_hello_announces_version_1(void)
{
    char buf[128], action[16];
    long version;

    CHECK_INT(proto_hello(buf, sizeof(buf)), 0);
    CHECK(json_object_get_string(buf, "action", action, sizeof(action)));
    CHECK_STR(action, "hello");
    CHECK(json_object_get_long(buf, "version", &version));
    CHECK_INT(version, 1);
    CHECK_INT(PROTOCOL_VERSION, 1);
}

static void test_requests_are_valid_json_with_escaped_text(void)
{
    char buf[BUF_SIZE], value[256];
    const char *participants[] = { "ana", "b\"en", "c\\at" };
    const char *list;

    CHECK_INT(proto_login(buf, sizeof(buf), "an\"a", "p\\w\n"), 0);
    CHECK(json_skip_value(buf) != NULL);
    CHECK(json_object_get_string(buf, "username", value, sizeof(value)));
    CHECK_STR(value, "an\"a");
    CHECK(json_object_get_string(buf, "password", value, sizeof(value)));
    CHECK_STR(value, "p\\w\n");
    CHECK(json_object_get_string(buf, "action", value, sizeof(value)));
    CHECK_STR(value, "login");

    CHECK_INT(proto_create_user(buf, sizeof(buf), "u", "p"), 0);
    CHECK(json_object_get_string(buf, "action", value, sizeof(value)));
    CHECK_STR(value, "create_user");

    CHECK_INT(proto_create_chat(buf, sizeof(buf), "team \"x\"", participants, 3), 0);
    CHECK(json_object_get_string(buf, "chat_name", value, sizeof(value)));
    CHECK_STR(value, "team \"x\"");
    list = json_object_get(buf, "participants");
    CHECK(list != NULL);
    {
        struct counter c = { 0, 0, 0 };
        CHECK_INT(json_each_element(list, count_element, &c), 0);
        CHECK_INT(c.elements, 3);
    }

    CHECK_INT(proto_send_msg(buf, sizeof(buf), "team", "line1\nline2 \"q\""), 0);
    CHECK(json_object_get_string(buf, "msg", value, sizeof(value)));
    CHECK_STR(value, "line1\nline2 \"q\"");
    CHECK_INT(proto_load_delta(buf, sizeof(buf), EPOCH), 0);
    CHECK(json_object_get_string(buf, "since", value, sizeof(value)));
    CHECK_STR(value, "1970-01-01 00:00:00");
    CHECK_INT(proto_logout(buf, sizeof(buf)), 0);
    CHECK(json_object_get_string(buf, "action", value, sizeof(value)));
    CHECK_STR(value, "logout");
}

static void test_builders_report_overflow_instead_of_truncating(void)
{
    char tiny[16], big[BUF_SIZE * 2];

    CHECK_INT(proto_login(tiny, sizeof(tiny), "user", "pass"), -1);
    CHECK_INT(proto_logout(tiny, 8), -1);
    memset(big, 'a', sizeof(big) - 1);
    big[sizeof(big) - 1] = '\0';
    CHECK_INT(proto_send_msg(tiny, sizeof(tiny), "c", "m"), -1);
    {
        char out[BUF_SIZE];
        CHECK_INT(proto_send_msg(out, sizeof(out), "c", big), -1);
    }
}

static void test_replies_are_interpreted(void)
{
    char message[64];

    CHECK(proto_reply_ok("{\"processed\": 1, \"msg\": \"ok\"}"));
    CHECK(proto_reply_ok("{\"code\":1,\"conversations\":{}}"));
    CHECK(!proto_reply_ok("{\"processed\": 0, \"msg\": \"no\"}"));
    CHECK(!proto_reply_ok("{\"error\": \"Unknown request\"}"));
    CHECK(!proto_reply_ok("{\"msg\": \"{\\\"processed\\\": 1}\"}")); /* inside a string: not a field */
    CHECK(!proto_reply_ok("garbage"));
    CHECK(!proto_reply_ok(NULL));

    proto_reply_message("{\"processed\":0,\"msg\":\"Authentication failed\"}", message, sizeof(message), "x");
    CHECK_STR(message, "Authentication failed");
    proto_reply_message("{\"processed\":0}", message, sizeof(message), "fallback");
    CHECK_STR(message, "fallback");
    proto_reply_message(NULL, message, sizeof(message), "fallback");
    CHECK_STR(message, "fallback");
}

/* ── session ─────────────────────────────────────────────────────────────────────────────── */

static Session *new_session(void)
{
    Session *s = malloc(sizeof(*s));
    session_init(s);
    return s;
}

static void test_chats_and_messages(void)
{
    Session *s = new_session();
    int team = session_add_chat(s, "team");

    CHECK_INT(team, 0);
    CHECK_INT(s->active_chat, 0);
    CHECK_INT(session_add_chat(s, "team"), 0);
    CHECK_INT(session_add_chat(s, "other"), 1);
    CHECK_INT(s->active_chat, 0);
    CHECK_INT(session_add_chat(s, ""), -1);
    CHECK_INT(session_find_chat(s, "other"), 1);
    CHECK_INT(session_find_chat(s, "none"), -1);

    session_add_message(s, team, "ana", "hello", "2026-05-04 10:00:00", 0);
    session_add_message(s, team, "ana", "lost", "", 1);
    session_add_message(s, 99, "ana", "ignored", "", 0);
    CHECK_INT(s->chats[0].nmsg, 2);
    CHECK_STR(s->chats[0].msgs[0].content, "hello");
    CHECK_INT(s->chats[0].msgs[1].failed, 1);
    free(s);
}

static void test_the_oldest_messages_are_dropped_when_a_chat_is_full(void)
{
    Session *s = new_session();
    int chat = session_add_chat(s, "c");
    char text[16];

    for (int i = 0; i < MAX_MSGS + 10; i++) {
        snprintf(text, sizeof(text), "m%d", i);
        session_add_message(s, chat, "a", text, "", 0);
    }
    CHECK_INT(s->chats[0].nmsg, MAX_MSGS);
    CHECK_STR(s->chats[0].msgs[0].content, "m10");
    CHECK_STR(s->chats[0].msgs[MAX_MSGS - 1].content, "m265");
    free(s);
}

static void test_text_that_is_too_long_is_cut_not_overflowed(void)
{
    Session *s = new_session();
    int chat = session_add_chat(s, "c");
    char big[MAX_MSG_LEN * 2];

    memset(big, 'x', sizeof(big) - 1);
    big[sizeof(big) - 1] = '\0';
    session_add_message(s, chat, "a-very-long-author-name-that-does-not-fit-in-sixty-four-bytes-at-all", big, "", 0);
    CHECK_INT(strlen(s->chats[0].msgs[0].content), MAX_MSG_LEN - 1);
    CHECK_INT(strlen(s->chats[0].msgs[0].author), MAX_NAME - 1);
    free(s);
}

static void test_the_delta_reply_fills_the_session(void)
{
    Session *s = new_session();
    const char *delta =
        "{\"code\":1,\"msg\":\"\",\"conversations\":{"
        "\"team\":[{\"chatname\":\"team\",\"author\":\"ana\",\"contents\":\"say \\\"hi\\\"\",\"sent\":\"2026-05-04 10:00:00\"},"
        "{\"chatname\":\"team\",\"author\":\"ben\",\"contents\":\"{\\\"author\\\": \\\"x\\\"}\",\"sent\":\"2026-05-04 10:01:00\"}],"
        "\"quiet\":[]}}";

    CHECK_INT(session_apply_delta(s, delta), 2);
    CHECK_INT(s->nchats, 2);
    CHECK_STR(s->chats[0].name, "team");
    CHECK_STR(s->chats[0].msgs[0].content, "say \"hi\"");
    CHECK_STR(s->chats[0].msgs[1].content, "{\"author\": \"x\"}");
    CHECK_STR(s->chats[0].msgs[1].author, "ben");
    CHECK_STR(s->chats[0].msgs[0].date, "2026-05-04 10:00:00");
    CHECK_INT(s->chats[1].nmsg, 0);
    free(s);
}

static void test_a_malformed_delta_is_rejected_without_crashing(void)
{
    Session *s = new_session();

    CHECK_INT(session_apply_delta(s, "{\"processed\":0}"), -1);
    CHECK_INT(session_apply_delta(s, "{\"conversations\":[1,2]}"), -1);
    CHECK_INT(session_apply_delta(s, "{\"conversations\":{\"a\":[{\"author\":"), -1);
    CHECK_INT(session_apply_delta(s, ""), -1);
    free(s);
}

static void test_pushes_add_messages_and_new_chats(void)
{
    Session *s = new_session();

    CHECK(session_apply_push(s, "{\"chatname\":\"fresh\"}"));
    CHECK_INT(s->nchats, 1);
    CHECK(!session_apply_push(s, "{\"chatname\":\"fresh\"}")); /* nothing new */
    CHECK(session_apply_push(s, "{\"chatname\":\"fresh\",\"author\":\"ben\",\"contents\":\"yo\",\"sent\":\"2026-05-04 10:00:00\"}"));
    CHECK_INT(s->chats[0].nmsg, 1);
    CHECK_STR(s->chats[0].msgs[0].content, "yo");
    CHECK(session_apply_push(s, "{\"chatname\":\"other\",\"author\":\"cat\",\"contents\":\"hi\",\"sent\":\"\"}"));
    CHECK_INT(s->nchats, 2);

    CHECK(!session_apply_push(s, "{\"processed\":1}"));
    CHECK(!session_apply_push(s, "{\"chatname\":\"\"}"));
    CHECK(!session_apply_push(s, "not json"));
    free(s);
}

/* ── config ──────────────────────────────────────────────────────────────────────────────── */

static const char *fake_env_host;
static const char *fake_env_port;

static const char *fake_getenv(const char *name)
{
    if (strcmp(name, "CHAT_SERVER_HOST") == 0)
        return fake_env_host;
    if (strcmp(name, "CHAT_SERVER_PORT") == 0)
        return fake_env_port;
    return NULL;
}

static void test_the_server_address_comes_from_flags_then_environment_then_defaults(void)
{
    ServerAddress a;
    char error[128];
    char *none[] = { "chat-client" };
    char *flags[] = { "chat-client", "--host", "example.org", "--port", "7100" };
    char *bad_port[] = { "chat-client", "--port", "70000" };
    char *unknown[] = { "chat-client", "--nope" };

    fake_env_host = fake_env_port = NULL;
    CHECK_INT(config_resolve(&a, 1, none, fake_getenv, error, sizeof(error)), 0);
    CHECK_STR(a.host, "127.0.0.1");
    CHECK_INT(a.port, 6969);

    fake_env_host = "10.0.0.5";
    fake_env_port = "7000";
    CHECK_INT(config_resolve(&a, 1, none, fake_getenv, error, sizeof(error)), 0);
    CHECK_STR(a.host, "10.0.0.5");
    CHECK_INT(a.port, 7000);

    CHECK_INT(config_resolve(&a, 5, flags, fake_getenv, error, sizeof(error)), 0);
    CHECK_STR(a.host, "example.org");
    CHECK_INT(a.port, 7100);

    CHECK_INT(config_resolve(&a, 3, bad_port, fake_getenv, error, sizeof(error)), -1);
    CHECK(strstr(error, "70000") != NULL);
    CHECK_INT(config_resolve(&a, 2, unknown, fake_getenv, error, sizeof(error)), -1);
    CHECK(strstr(error, "usage") != NULL);

    fake_env_port = "abc";
    CHECK_INT(config_resolve(&a, 1, none, fake_getenv, error, sizeof(error)), -1);
    CHECK(strstr(error, "CHAT_SERVER_PORT") != NULL);
    fake_env_host = fake_env_port = NULL;
}

/* ── network, against a real socket ──────────────────────────────────────────────────────── */

static void pause_ms(int ms)
{
    struct timespec t = { ms / 1000, (long)(ms % 1000) * 1000000L };
    nanosleep(&t, NULL);
}

typedef struct {
    int listener;
    int port;
    char received[256];
    size_t big_size; /* if non-zero, the server sends one message of this many bytes */
} Peer;

static void *peer_thread(void *arg)
{
    Peer *peer = arg;
    int fd = accept(peer->listener, NULL, NULL);
    ssize_t n;

    if (fd < 0)
        return NULL;

    /* two messages in one write, then one in two pieces */
    send(fd, "{\"n\":1}\x04{\"n\":2}\x04{\"n\"", 20, 0);
    pause_ms(50);
    send(fd, ":3}\x04", 4, 0);

    if (peer->big_size) {
        char *big = malloc(peer->big_size + 1);
        memset(big, 'z', peer->big_size);
        big[peer->big_size] = EOT;
        for (size_t sent = 0; sent < peer->big_size + 1;) {
            n = send(fd, big + sent, peer->big_size + 1 - sent, 0);
            if (n <= 0)
                break;
            sent += (size_t)n;
        }
        free(big);
    }

    n = recv(fd, peer->received, sizeof(peer->received) - 1, 0);
    peer->received[n > 0 ? n : 0] = '\0';
    close(fd);
    return NULL;
}

static int start_peer(Peer *peer, pthread_t *thread)
{
    struct sockaddr_in address = { .sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
    socklen_t length = sizeof(address);

    peer->listener = socket(AF_INET, SOCK_STREAM, 0);
    if (bind(peer->listener, (struct sockaddr *)&address, sizeof(address)) != 0 || listen(peer->listener, 1) != 0)
        return -1;
    getsockname(peer->listener, (struct sockaddr *)&address, &length);
    peer->port = ntohs(address.sin_port);
    peer->received[0] = '\0';
    return pthread_create(thread, NULL, peer_thread, peer);
}

static void test_messages_are_cut_at_the_terminator_whatever_the_packets(void)
{
    Peer peer = { 0 };
    pthread_t thread;
    NetworkClient nc;
    char *message;

    CHECK_INT(start_peer(&peer, &thread), 0);
    CHECK_INT(net_connect(&nc, "127.0.0.1", peer.port), 0);

    for (int expected = 1; expected <= 3; expected++) {
        char want[16];
        snprintf(want, sizeof(want), "{\"n\":%d}", expected);
        message = net_recv(&nc, 2000);
        CHECK_STR(message, want);
        free(message);
    }
    CHECK(net_try_recv(&nc) == NULL);

    CHECK_INT(net_send(&nc, "{\"action\":\"x\"}"), 0);
    pthread_join(thread, NULL);
    CHECK(memcmp(peer.received, "{\"action\":\"x\"}\x04", 15) == 0);

    CHECK(net_recv(&nc, 200) == NULL); /* timeout */
    net_close(&nc);
    close(peer.listener);
}

static void test_a_message_larger_than_the_receive_chunks_is_reassembled(void)
{
    Peer peer = { 0 };
    pthread_t thread;
    NetworkClient nc;
    char *message;
    size_t size = 300 * 1024;

    peer.big_size = size;
    CHECK_INT(start_peer(&peer, &thread), 0);
    CHECK_INT(net_connect(&nc, "127.0.0.1", peer.port), 0);
    for (int i = 0; i < 3; i++)
        free(net_recv(&nc, 2000));
    message = net_recv(&nc, 5000);
    CHECK(message != NULL);
    if (message) {
        CHECK_INT(strlen(message), size);
        CHECK(message[0] == 'z' && message[size - 1] == 'z');
        free(message);
    }
    net_send(&nc, "bye");
    pthread_join(thread, NULL);
    net_close(&nc);
    close(peer.listener);
}

static void test_the_connection_state_follows_the_peer(void)
{
    Peer peer = { 0 };
    pthread_t thread;
    NetworkClient nc;
    int tries;

    CHECK_INT(start_peer(&peer, &thread), 0);
    CHECK_INT(net_connect(&nc, "127.0.0.1", peer.port), 0);
    CHECK(net_alive(&nc));
    net_send(&nc, "bye");
    pthread_join(thread, NULL); /* the peer closes after reading */
    for (tries = 0; tries < 100 && net_alive(&nc); tries++)
        pause_ms(20);
    CHECK(!net_alive(&nc));
    net_close(&nc);
    close(peer.listener);
}

static void test_connecting_to_nothing_fails(void)
{
    NetworkClient nc;
    int probe = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address = { .sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
    socklen_t length = sizeof(address);
    int port;

    bind(probe, (struct sockaddr *)&address, sizeof(address));
    getsockname(probe, (struct sockaddr *)&address, &length);
    port = ntohs(address.sin_port);
    close(probe); /* nobody listens there now */

    CHECK_INT(net_connect(&nc, "127.0.0.1", port), -1);
    CHECK_INT(net_connect(&nc, "host.invalid", 80), -1);
}

int main(void)
{
    RUN(test_json_skips_values_by_structure);
    RUN(test_json_strings_are_decoded);
    RUN(test_json_strings_are_cut_and_malformed_ones_rejected);
    RUN(test_json_object_members_are_found_at_the_top_level_only);
    RUN(test_json_iteration);
    RUN(test_json_escape);
    RUN(test_the_hello_announces_version_1);
    RUN(test_requests_are_valid_json_with_escaped_text);
    RUN(test_builders_report_overflow_instead_of_truncating);
    RUN(test_replies_are_interpreted);
    RUN(test_chats_and_messages);
    RUN(test_the_oldest_messages_are_dropped_when_a_chat_is_full);
    RUN(test_text_that_is_too_long_is_cut_not_overflowed);
    RUN(test_the_delta_reply_fills_the_session);
    RUN(test_a_malformed_delta_is_rejected_without_crashing);
    RUN(test_pushes_add_messages_and_new_chats);
    RUN(test_the_server_address_comes_from_flags_then_environment_then_defaults);
    RUN(test_messages_are_cut_at_the_terminator_whatever_the_packets);
    RUN(test_a_message_larger_than_the_receive_chunks_is_reassembled);
    RUN(test_the_connection_state_follows_the_peer);
    RUN(test_connecting_to_nothing_fails);
    return SUMMARY();
}
