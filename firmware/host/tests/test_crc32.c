#include "kb_crc32.h"
#include "test_harness.h"

#include <stdint.h>
#include <string.h>

TEST(empty_vector)
{
    ASSERT_EQ_U32(UINT32_C(0x00000000), kb_crc32("", 0U));
}

TEST(check_vector)
{
    ASSERT_EQ_U32(UINT32_C(0xcbf43926), kb_crc32("123456789", 9U));
}

TEST(binary_vector)
{
    static const uint8_t bytes[] = {0x00, 0x01, 0x02, 0x03};
    ASSERT_EQ_U32(UINT32_C(0x8bb98613), kb_crc32(bytes, sizeof(bytes)));
}

static const test_case_t cases[] = {
    TEST_CASE(empty_vector),
    TEST_CASE(check_vector),
    TEST_CASE(binary_vector)
};

TEST_MAIN("crc32", cases)
