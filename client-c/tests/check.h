/* check.h - the smallest possible test harness: CHECK macros and a summary. */
#ifndef CHECK_H
#define CHECK_H

#include <stdio.h>
#include <string.h>

static int checks_run = 0;
static int checks_failed = 0;

#define CHECK(condition)                                                                        \
    do {                                                                                        \
        checks_run++;                                                                           \
        if (!(condition)) {                                                                     \
            checks_failed++;                                                                    \
            printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #condition);                       \
        }                                                                                       \
    } while (0)

#define CHECK_STR(actual, expected)                                                             \
    do {                                                                                        \
        const char *a_ = (actual), *e_ = (expected);                                            \
        checks_run++;                                                                           \
        if (!a_ || strcmp(a_, e_) != 0) {                                                       \
            checks_failed++;                                                                    \
            printf("  FAIL %s:%d: expected \"%s\", got \"%s\"\n", __FILE__, __LINE__, e_,       \
                   a_ ? a_ : "(null)");                                                         \
        }                                                                                       \
    } while (0)

#define CHECK_INT(actual, expected)                                                             \
    do {                                                                                        \
        long a_ = (long)(actual), e_ = (long)(expected);                                        \
        checks_run++;                                                                           \
        if (a_ != e_) {                                                                         \
            checks_failed++;                                                                    \
            printf("  FAIL %s:%d: expected %ld, got %ld\n", __FILE__, __LINE__, e_, a_);        \
        }                                                                                       \
    } while (0)

#define RUN(test)                                                                               \
    do {                                                                                        \
        int before_ = checks_failed;                                                            \
        test();                                                                                 \
        printf("%s %s\n", checks_failed == before_ ? "ok  " : "FAIL", #test);                   \
    } while (0)

#define SUMMARY()                                                                               \
    (printf("\n%d checks, %d failed\n", checks_run, checks_failed), checks_failed ? 1 : 0)

#endif
