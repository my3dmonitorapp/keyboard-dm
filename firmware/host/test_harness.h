#ifndef TEST_HARNESS_H
#define TEST_HARNESS_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef void (*test_function_t)(void);

typedef struct {
    const char *name;
    test_function_t function;
} test_case_t;

static int test_harness_current_failed;

#define TEST(name) static void name(void)
#define TEST_CASE(name) {#name, name}

#define FAIL(message)                                                          \
    do {                                                                       \
        (void)fprintf(stderr, "    %s:%d: %s\n", __FILE__, __LINE__, message); \
        test_harness_current_failed = 1;                                       \
        return;                                                                \
    } while (0)

#define ASSERT_TRUE(expression)                                                \
    do {                                                                       \
        if (!(expression)) {                                                   \
            FAIL("assertion failed: " #expression);                           \
        }                                                                      \
    } while (0)

#define ASSERT_EQ_U32(expected, actual)                                        \
    do {                                                                       \
        const unsigned long test_expected = (unsigned long)(expected);         \
        const unsigned long test_actual = (unsigned long)(actual);             \
        if (test_expected != test_actual) {                                    \
            (void)fprintf(stderr, "    %s:%d: expected %lu, got %lu\n",       \
                          __FILE__, __LINE__, test_expected, test_actual);      \
            test_harness_current_failed = 1;                                   \
            return;                                                            \
        }                                                                      \
    } while (0)

#define ASSERT_STREQ(expected, actual)                                         \
    do {                                                                       \
        if (strcmp((expected), (actual)) != 0) {                               \
            (void)fprintf(stderr, "    %s:%d: expected '%s', got '%s'\n",     \
                          __FILE__, __LINE__, (expected), (actual));            \
            test_harness_current_failed = 1;                                   \
            return;                                                            \
        }                                                                      \
    } while (0)

static int test_harness_run(const test_case_t *cases, size_t count,
                            const char *suite_name)
{
    size_t index;
    size_t passed = 0U;
    (void)printf("suite %s (%lu tests)\n", suite_name, (unsigned long)count);
    for (index = 0U; index < count; ++index) {
        test_harness_current_failed = 0;
        cases[index].function();
        if (test_harness_current_failed) {
            (void)printf("  FAIL %s\n", cases[index].name);
        } else {
            ++passed;
            (void)printf("  PASS %s\n", cases[index].name);
        }
    }
    (void)printf("summary %s: %lu passed, %lu failed\n", suite_name,
                 (unsigned long)passed, (unsigned long)(count - passed));
    return passed == count ? EXIT_SUCCESS : EXIT_FAILURE;
}

#define TEST_MAIN(suite_name, cases)                                           \
    int main(void)                                                             \
    {                                                                          \
        return test_harness_run((cases), sizeof(cases) / sizeof((cases)[0]),   \
                                (suite_name));                                 \
    }

#endif
