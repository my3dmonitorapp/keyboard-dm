#include "fake_hal.h"
#include "kb_hid.h"
#include "test_harness.h"

#include <string.h>

static kb_typed_action_t action(kb_typed_action_type_t type, uint16_t page,
                                uint16_t usage)
{
    kb_typed_action_t value;
    memset(&value, 0, sizeof(value)); value.type = type;
    value.usage_page = page; value.usage = usage; return value;
}

TEST(boot_report_is_exactly_eight_bytes)
{
    kb_hid_state_t state; uint8_t report[KB_HID_BOOT_REPORT_BYTES];
    kb_typed_action_t modifier = action(KB_TYPED_ACTION_KEY_PRESS, 7U, 0xe1U);
    kb_typed_action_t key = action(KB_TYPED_ACTION_KEY_PRESS, 7U, 0x04U);
    kb_hid_init(&state);
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply(&state, &modifier));
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply(&state, &key));
    kb_hid_build_boot_report(&state, report);
    ASSERT_EQ_U32(2U, report[0]); ASSERT_EQ_U32(0U, report[1]); ASSERT_EQ_U32(4U, report[2]);
}

TEST(ble_report_prefix_and_consumer_tuples)
{
    kb_hid_state_t state; uint8_t report[KB_HID_BLE_REPORT_BYTES];
    kb_typed_action_t one = action(KB_TYPED_ACTION_CONSUMER_PRESS, 0x0cU, 1U);
    kb_typed_action_t two = action(KB_TYPED_ACTION_CONSUMER_PRESS, 0x0cU, 2U);
    kb_hid_init(&state);
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply(&state, &one));
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply(&state, &two));
    kb_hid_build_ble_report(&state, report);
    ASSERT_EQ_U32(0x0cU, report[8]); ASSERT_EQ_U32(1U, report[10]);
    ASSERT_EQ_U32(0x0cU, report[12]); ASSERT_EQ_U32(2U, report[14]);
}

TEST(report_emits_only_on_change)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_hid_state_t state;
    kb_typed_action_t key = action(KB_TYPED_ACTION_KEY_PRESS, 7U, 4U);
    fake_hal_reset(&fake); ops = fake_hal_ops(&fake); kb_hid_init(&state);
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply_and_emit(&state, &ops, &key));
    ASSERT_EQ_U32(32U, fake.ble_report_length); ASSERT_EQ_U32(1U, fake.ble_send_call_count);
    ASSERT_EQ_U32(KB_HID_NO_CHANGE, kb_hid_apply_and_emit(&state, &ops, &key));
    ASSERT_EQ_U32(1U, fake.ble_send_call_count);
}

TEST(release_removes_key_and_consumer)
{
    kb_hid_state_t state;
    kb_typed_action_t key = action(KB_TYPED_ACTION_KEY_PRESS, 7U, 4U);
    kb_typed_action_t consumer = action(KB_TYPED_ACTION_CONSUMER_PRESS, 0x0cU, 1U);
    kb_hid_init(&state); (void)kb_hid_apply(&state, &key); (void)kb_hid_apply(&state, &consumer);
    key.type = KB_TYPED_ACTION_KEY_RELEASE; consumer.type = KB_TYPED_ACTION_CONSUMER_RELEASE;
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply(&state, &key));
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply(&state, &consumer));
    ASSERT_EQ_U32(0U, state.keys[0]); ASSERT_EQ_U32(0U, state.consumer_count);
}

TEST(fifth_consumer_is_rejected_without_mutation)
{
    kb_hid_state_t state; kb_typed_action_t item; kb_hid_state_t before; uint16_t usage;
    kb_hid_init(&state);
    for (usage = 1U; usage <= 4U; ++usage) { item = action(KB_TYPED_ACTION_CONSUMER_PRESS, 0x0cU, usage); ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply(&state, &item)); }
    before = state; item = action(KB_TYPED_ACTION_CONSUMER_PRESS, 0x0cU, 5U);
    ASSERT_EQ_U32(KB_HID_ROLLOVER, kb_hid_apply(&state, &item));
    ASSERT_TRUE(memcmp(&before, &state, sizeof(state)) == 0);
}

TEST(custom_action_never_emits)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_hid_state_t state; kb_typed_action_t custom;
    const uint8_t bytes[] = {1U, 2U};
    fake_hal_reset(&fake); ops = fake_hal_ops(&fake); kb_hid_init(&state);
    ASSERT_EQ_U32(KB_ACTION_OK, kb_action_make_custom(bytes, sizeof(bytes), &custom));
    ASSERT_EQ_U32(KB_HID_NO_CHANGE, kb_hid_apply_and_emit(&state, &ops, &custom));
    ASSERT_EQ_U32(0U, fake.ble_send_call_count);
}

static const test_case_t cases[] = {
    TEST_CASE(boot_report_is_exactly_eight_bytes), TEST_CASE(ble_report_prefix_and_consumer_tuples),
    TEST_CASE(report_emits_only_on_change), TEST_CASE(release_removes_key_and_consumer),
    TEST_CASE(fifth_consumer_is_rejected_without_mutation), TEST_CASE(custom_action_never_emits)
};
TEST_MAIN("hid", cases)
