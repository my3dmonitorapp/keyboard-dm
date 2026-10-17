#include "fake_hal.h"
#include "test_harness.h"

#include <stdint.h>
#include <string.h>

TEST(storage_faults_are_one_shot)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    const char value[] = "config";
    char restored[16];
    size_t length = 0U;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    fake.next_store_write_error = KB_HAL_ERR_IO;
    ASSERT_EQ_U32(KB_HAL_ERR_IO,
                  ops.hal_store_write(ops.ctx, KB_HAL_STORE_CONFIG_A, value,
                                      sizeof(value)));
    ASSERT_EQ_U32(KB_HAL_OK,
                  ops.hal_store_write(ops.ctx, KB_HAL_STORE_CONFIG_A, value,
                                      sizeof(value)));
    fake.next_store_read_error = KB_HAL_ERR_CORRUPT;
    ASSERT_EQ_U32(KB_HAL_ERR_CORRUPT,
                  ops.hal_store_read(ops.ctx, KB_HAL_STORE_CONFIG_A, restored,
                                     sizeof(restored), &length));
    ASSERT_EQ_U32(KB_HAL_OK,
                  ops.hal_store_read(ops.ctx, KB_HAL_STORE_CONFIG_A, restored,
                                     sizeof(restored), &length));
    ASSERT_EQ_U32(sizeof(value), length);
    ASSERT_TRUE(memcmp(value, restored, sizeof(value)) == 0);
}

TEST(pin_reads_can_be_corrupted)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_pin_value_t value;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    fake.pin_values[4] = KB_HAL_PIN_HIGH;
    fake.corrupt_pin_reads = true;
    ASSERT_EQ_U32(KB_HAL_OK, ops.hal_pin_read(ops.ctx, 4U, &value));
    ASSERT_EQ_U32(KB_HAL_PIN_LOW, value);
}

TEST(clock_jumps_are_injected)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    uint64_t now;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    fake_hal_advance(&fake, 100U);
    fake_hal_inject_time_jump(&fake, 250);
    ASSERT_EQ_U32(KB_HAL_OK, ops.hal_now_ms(ops.ctx, &now));
    ASSERT_EQ_U32(350U, now);
    fake_hal_inject_time_jump(&fake, -50);
    ASSERT_EQ_U32(KB_HAL_OK, ops.hal_now_ms(ops.ctx, &now));
    ASSERT_EQ_U32(300U, now);
}

static const test_case_t cases[] = {
    TEST_CASE(storage_faults_are_one_shot),
    TEST_CASE(pin_reads_can_be_corrupted),
    TEST_CASE(clock_jumps_are_injected)
};

TEST_MAIN("fake_hal", cases)
