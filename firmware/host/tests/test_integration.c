#include "fake_hal.h"
#include "kb_actions.h"
#include "kb_hid.h"
#include "kb_scanner.h"
#include "test_harness.h"

#include <stdio.h>
#include <string.h>

static kb_hal_probe_t probe(void)
{
    kb_hal_probe_t value; memset(&value, 0, sizeof(value)); value.pin_count = FAKE_HAL_MAX_PINS; return value;
}

static kb_config_t config_for(kb_action_type_t type, const char *name,
                              uint16_t usage)
{
    kb_config_t config; kb_config_init(&config); (void)strcpy(config.chip_class, "host");
    config.matrix.rows = 1U; config.matrix.cols = 1U; config.pinmap.row_pin_count = 1U;
    config.pinmap.col_pin_count = 1U; config.pinmap.row_pins[0] = 1U; config.pinmap.col_pins[0] = 2U;
    config.debounce_ms = 5U; config.switch_count = 1U; config.switches[0].action.type = type;
    (void)strcpy(config.switches[0].action.key_name, name); config.switches[0].action.usage_id = usage;
    (void)strcpy(config.meta.project_name, "integration"); (void)strcpy(config.meta.updated, "2026-10-17");
    config.generation = 1U; (void)kb_config_finalize_crc32(&config); return config;
}

static void dispatch_one(kb_event_ring_t *events, const kb_config_t *config,
                         kb_hid_state_t *hid, kb_hal_ops_t *ops)
{
    kb_event_t event; char key_id[16]; kb_key_action_t entry; kb_action_profile_t profile; kb_typed_action_t action;
    ASSERT_TRUE(kb_events_pop(events, &event));
    (void)snprintf(key_id, sizeof(key_id), "MX-%02u-%02u", (unsigned)event.row, (unsigned)event.col);
    entry.key_id = key_id; entry.desktop_action = &config->switches[event.switch_id].action;
    profile.key_actions = &entry; profile.key_action_count = 1U;
    ASSERT_EQ_U32(KB_ACTION_OK, kb_action_resolve(&profile, key_id, event.type == KB_EVENT_KEY_DOWN, &action));
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply_and_emit(hid, ops, &action));
}

TEST(fake_key_closes_debounces_resolves_and_emits)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_hal_probe_t descriptor = probe(); kb_config_t config = config_for(KB_ACTION_KEY, "a", 4U);
    kb_scanner_t scanner; kb_event_ring_t events; kb_hid_state_t hid; size_t count;
    fake_hal_reset(&fake); ops = fake_hal_ops(&fake); kb_events_init(&events); kb_hid_init(&hid);
    ASSERT_EQ_U32(KB_SCANNER_OK, kb_scanner_init(&config, &descriptor, &ops, &scanner));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 2U, true));
    ASSERT_EQ_U32(KB_SCANNER_OK, kb_scanner_process(&scanner, &ops, 0U, &events, &count));
    ASSERT_EQ_U32(KB_SCANNER_OK, kb_scanner_process(&scanner, &ops, 5U, &events, &count));
    dispatch_one(&events, &config, &hid, &ops);
    ASSERT_EQ_U32(32U, fake.ble_report_length); ASSERT_EQ_U32(4U, fake.ble_report[2]);
}

TEST(fake_release_emits_all_released_report)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_hal_probe_t descriptor = probe(); kb_config_t config = config_for(KB_ACTION_KEY, "a", 4U);
    kb_scanner_t scanner; kb_event_ring_t events; kb_hid_state_t hid; size_t count;
    fake_hal_reset(&fake); ops = fake_hal_ops(&fake); kb_events_init(&events); kb_hid_init(&hid);
    ASSERT_EQ_U32(KB_SCANNER_OK, kb_scanner_init(&config, &descriptor, &ops, &scanner));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 2U, true));
    (void)kb_scanner_process(&scanner, &ops, 0U, &events, &count); (void)kb_scanner_process(&scanner, &ops, 5U, &events, &count);
    dispatch_one(&events, &config, &hid, &ops); ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 2U, false));
    (void)kb_scanner_process(&scanner, &ops, 6U, &events, &count); (void)kb_scanner_process(&scanner, &ops, 11U, &events, &count);
    dispatch_one(&events, &config, &hid, &ops); ASSERT_EQ_U32(0U, fake.ble_report[2]); ASSERT_EQ_U32(2U, fake.ble_send_call_count);
}

TEST(consumer_path_reaches_ble_tuple)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_hal_probe_t descriptor = probe(); kb_config_t config = config_for(KB_ACTION_MEDIA, "vol_up", 0x00e9U);
    kb_scanner_t scanner; kb_event_ring_t events; kb_hid_state_t hid; size_t count;
    fake_hal_reset(&fake); ops = fake_hal_ops(&fake); kb_events_init(&events); kb_hid_init(&hid);
    ASSERT_EQ_U32(KB_SCANNER_OK, kb_scanner_init(&config, &descriptor, &ops, &scanner)); ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 2U, true));
    (void)kb_scanner_process(&scanner, &ops, 0U, &events, &count); (void)kb_scanner_process(&scanner, &ops, 5U, &events, &count);
    dispatch_one(&events, &config, &hid, &ops); ASSERT_EQ_U32(0x0cU, fake.ble_report[8]); ASSERT_EQ_U32(0xe9U, fake.ble_report[10]);
}

static const test_case_t cases[] = {
    TEST_CASE(fake_key_closes_debounces_resolves_and_emits),
    TEST_CASE(fake_release_emits_all_released_report),
    TEST_CASE(consumer_path_reaches_ble_tuple)
};
TEST_MAIN("integration", cases)
