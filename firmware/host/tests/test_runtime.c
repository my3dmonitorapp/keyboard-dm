#include "fake_hal.h"
#include "kb_crc32.h"
#include "kb_runtime.h"
#include "test_harness.h"

#include <stdio.h>
#include <string.h>

static kb_hal_probe_t probe(void)
{
    kb_hal_probe_t value;
    memset(&value, 0, sizeof(value));
    value.pin_count = FAKE_HAL_MAX_PINS;
    return value;
}

static kb_config_t config_named(const char *name, uint8_t key_usage)
{
    kb_config_t config;
    kb_config_init(&config);
    (void)strcpy(config.chip_class, "host");
    config.matrix.rows = 1U;
    config.matrix.cols = 1U;
    config.pinmap.row_pin_count = 1U;
    config.pinmap.col_pin_count = 1U;
    config.pinmap.row_pins[0] = 1U;
    config.pinmap.col_pins[0] = 2U;
    config.debounce_ms = 5U;
    config.switch_count = 1U;
    config.switches[0].row = 0U;
    config.switches[0].col = 0U;
    config.switches[0].action.type = KB_ACTION_KEY;
    config.switches[0].action.usage_id = key_usage;
    (void)strcpy(config.switches[0].action.key_name,
                 key_usage == 5U ? "b" : "a");
    (void)strcpy(config.meta.project_name, name);
    (void)strcpy(config.meta.updated, "2026-10-17");
    config.generation = 1U;
    (void)kb_config_finalize_crc32(&config);
    return config;
}

static kb_config_t two_key_config(void)
{
    kb_config_t config = config_named("two-key", 4U);
    config.matrix.cols = 2U;
    config.pinmap.col_pin_count = 2U;
    config.pinmap.col_pins[1] = 3U;
    config.switch_count = 2U;
    config.switches[1].row = 0U;
    config.switches[1].col = 1U;
    config.switches[1].action.type = KB_ACTION_KEY;
    config.switches[1].action.usage_id = 5U;
    (void)strcpy(config.switches[1].action.key_name, "b");
    (void)kb_config_finalize_crc32(&config);
    return config;
}

static void setup_no_config(fake_hal_t *fake, kb_hal_ops_t *ops,
                            kb_boot_t *boot, kb_runtime_t *runtime)
{
    kb_hal_probe_t descriptor = probe();
    fake_hal_reset(fake);
    *ops = fake_hal_ops(fake);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(boot, &descriptor, ops));
    ASSERT_EQ_U32(KB_RUNTIME_OK,
                  kb_runtime_init(runtime, boot, ops, 1U));
}

static void setup_valid(fake_hal_t *fake, kb_hal_ops_t *ops, kb_boot_t *boot,
                        kb_runtime_t *runtime, const char *name)
{
    kb_config_t config = config_named(name, 4U);
    setup_no_config(fake, ops, boot, runtime);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_apply_config(boot, &config));
    fake->console_length = 0U;
}

static void poll_ok(kb_runtime_t *runtime, uint64_t now_ms,
                    const void *input, size_t input_length)
{
    size_t consumed = 0U;
    ASSERT_EQ_U32(KB_RUNTIME_OK,
                  kb_runtime_poll(runtime, now_ms, input, input_length,
                                  &consumed));
    ASSERT_EQ_U32(input_length, consumed);
}

static void b64(const uint8_t *input, size_t length, char *output)
{
    static const char alphabet[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t in = 0U;
    size_t out = 0U;
    while (in < length) {
        uint32_t value = (uint32_t)input[in++] << 16U;
        unsigned count = 1U;
        if (in < length) {
            value |= (uint32_t)input[in++] << 8U;
            ++count;
        }
        if (in < length) {
            value |= input[in++];
            ++count;
        }
        output[out++] = alphabet[(value >> 18U) & 63U];
        output[out++] = alphabet[(value >> 12U) & 63U];
        output[out++] = count > 1U ? alphabet[(value >> 6U) & 63U] : '=';
        output[out++] = count > 2U ? alphabet[value & 63U] : '=';
    }
    output[out] = '\0';
}

static void runtime_upload(kb_runtime_t *runtime, const char *json,
                           size_t json_length, uint32_t crc, uint64_t now_ms)
{
    char line[KB_PROTOCOL_MAX_LINE_BYTES + 2U];
    size_t offset = 0U;
    uint32_t sequence = 0U;

    (void)snprintf(
        line, sizeof(line),
        "{\"id\":\"start\",\"cmd\":\"config_upload\",\"params\":{"
        "\"phase\":\"start\",\"upload_id\":\"runtime\",\"encoding\":"
        "\"base64\",\"total_bytes\":%lu,\"crc32\":%lu}}\n",
        (unsigned long)json_length, (unsigned long)crc);
    poll_ok(runtime, now_ms, line, strlen(line));
    while (offset < json_length) {
        const size_t remaining = json_length - offset;
        const size_t part = remaining > 600U ? 600U : remaining;
        char encoded[801];
        b64((const uint8_t *)json + offset, part, encoded);
        (void)snprintf(
            line, sizeof(line),
            "{\"id\":\"chunk\",\"cmd\":\"config_upload\",\"params\":{"
            "\"phase\":\"chunk\",\"upload_id\":\"runtime\",\"seq\":%lu,"
            "\"data\":\"%s\"}}\n",
            (unsigned long)sequence, encoded);
        poll_ok(runtime, now_ms, line, strlen(line));
        offset += part;
        ++sequence;
    }
    poll_ok(runtime, now_ms,
            "{\"id\":\"commit\",\"cmd\":\"config_commit\",\"params\":{}}\n",
            strlen("{\"id\":\"commit\",\"cmd\":\"config_commit\",\"params\":{}}\n"));
}

TEST(scanner_gate_blocks_every_gpio_operation)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_boot_t boot;
    kb_runtime_t runtime;
    setup_no_config(&fake, &ops, &boot, &runtime);
    poll_ok(&runtime, 100U, NULL, 0U);
    ASSERT_TRUE(!kb_runtime_scanner_started(&runtime));
    ASSERT_EQ_U32(0U, kb_events_count(&runtime.events));
    ASSERT_EQ_U32(0U, fake.pin_direction_call_count);
    ASSERT_EQ_U32(0U, fake.pin_pulldown_call_count);
    ASSERT_EQ_U32(0U, fake.pin_write_call_count);
    ASSERT_EQ_U32(0U, fake.pin_read_call_count);
}

TEST(full_press_release_cycle_emits_reports_in_order)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_boot_t boot;
    kb_runtime_t runtime;
    setup_valid(&fake, &ops, &boot, &runtime, "cycle");
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 2U, true));
    poll_ok(&runtime, 0U, NULL, 0U);
    poll_ok(&runtime, 5U, NULL, 0U);
    ASSERT_EQ_U32(1U, fake.ble_send_call_count);
    ASSERT_EQ_U32(4U, fake.ble_report[2]);
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 2U, false));
    poll_ok(&runtime, 6U, NULL, 0U);
    poll_ok(&runtime, 11U, NULL, 0U);
    ASSERT_EQ_U32(2U, fake.ble_send_call_count);
    ASSERT_EQ_U32(0U, fake.ble_report[2]);
}

TEST(two_simultaneous_keys_preserve_multi_key_hid_state)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_boot_t boot;
    kb_runtime_t runtime;
    kb_config_t config = two_key_config();
    setup_no_config(&fake, &ops, &boot, &runtime);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_apply_config(&boot, &config));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 2U, true));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 3U, true));
    poll_ok(&runtime, 0U, NULL, 0U);
    poll_ok(&runtime, 5U, NULL, 0U);
    ASSERT_EQ_U32(2U, fake.ble_send_call_count);
    ASSERT_EQ_U32(4U, fake.ble_report[2]);
    ASSERT_EQ_U32(5U, fake.ble_report[3]);
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 2U, false));
    poll_ok(&runtime, 6U, NULL, 0U);
    poll_ok(&runtime, 11U, NULL, 0U);
    ASSERT_EQ_U32(3U, fake.ble_send_call_count);
    ASSERT_EQ_U32(5U, fake.ble_report[2]);
    ASSERT_EQ_U32(0U, fake.ble_report[3]);
}

TEST(valid_console_upload_commits_and_reloads_runtime_config)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_boot_t boot;
    kb_runtime_t runtime;
    kb_config_t replacement = config_named("replacement", 5U);
    char json[KB_PROTOCOL_MAX_UPLOAD_BYTES];
    size_t json_length = 0U;
    setup_valid(&fake, &ops, &boot, &runtime, "original");
    poll_ok(&runtime, 0U, NULL, 0U);
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_to_json(&replacement, json, sizeof(json),
                                    &json_length));
    runtime_upload(&runtime, json, json_length, kb_crc32(json, json_length),
                   1U);
    ASSERT_STREQ("replacement", kb_boot_active_config(&boot)->meta.project_name);
    ASSERT_STREQ("replacement", runtime.scanner.config.meta.project_name);
    ASSERT_EQ_U32(2U, boot.status.active_generation);
    ASSERT_TRUE(strstr((const char *)fake.console, "\"ok\":true") != NULL);
}

TEST(corrupt_upload_is_rejected_without_state_change)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_boot_t boot;
    kb_runtime_t runtime;
    kb_config_t replacement = config_named("corrupt", 5U);
    char json[KB_PROTOCOL_MAX_UPLOAD_BYTES];
    size_t json_length = 0U;
    setup_valid(&fake, &ops, &boot, &runtime, "preserved");
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_to_json(&replacement, json, sizeof(json),
                                    &json_length));
    runtime_upload(&runtime, json, json_length,
                   kb_crc32(json, json_length) ^ UINT32_C(1), 0U);
    ASSERT_STREQ("preserved", kb_boot_active_config(&boot)->meta.project_name);
    ASSERT_EQ_U32(1U, boot.status.active_generation);
    ASSERT_TRUE(strstr((const char *)fake.console, "bad_crc") != NULL);
}

TEST(malformed_frame_emits_error_and_does_not_corrupt_state)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_boot_t boot;
    kb_runtime_t runtime;
    static const char bad[] = "{not-json}\n";
    setup_valid(&fake, &ops, &boot, &runtime, "preserved");
    poll_ok(&runtime, 0U, bad, sizeof(bad) - 1U);
    ASSERT_STREQ("preserved", kb_boot_active_config(&boot)->meta.project_name);
    ASSERT_TRUE(strstr((const char *)fake.console, "\"ok\":false") != NULL);
}

TEST(release_only_event_emits_an_all_released_report)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_boot_t boot;
    kb_runtime_t runtime;
    kb_typed_action_t press = {
        .type = KB_TYPED_ACTION_KEY_PRESS,
        .usage_page = UINT16_C(0x0007),
        .usage = 4U
    };
    kb_event_t release = {
        .type = KB_EVENT_KEY_UP,
        .row = 0U,
        .col = 0U,
        .switch_id = 0U,
        .timestamp_ms = 1U
    };
    setup_valid(&fake, &ops, &boot, &runtime, "release");
    poll_ok(&runtime, 0U, NULL, 0U);
    ASSERT_EQ_U32(KB_HID_OK, kb_hid_apply(&runtime.hid, &press));
    ASSERT_TRUE(kb_events_push(&runtime.events, &release));
    poll_ok(&runtime, 1U, NULL, 0U);
    ASSERT_EQ_U32(1U, fake.ble_send_call_count);
    ASSERT_EQ_U32(0U, fake.ble_report[2]);
}

TEST(queue_overflow_and_partial_frame_timeout_are_bounded)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_boot_t boot;
    kb_runtime_t runtime;
    kb_event_t event = {
        .type = KB_EVENT_KEY_DOWN,
        .row = 0U,
        .col = 0U,
        .switch_id = 99U
    };
    size_t index;
    static const char partial[] = "{\"id\":\"partial\"";
    setup_valid(&fake, &ops, &boot, &runtime, "bounded");
    poll_ok(&runtime, 0U, NULL, 0U);
    for (index = 0U; index < KB_EVENT_RING_CAPACITY + 10U; ++index)
        (void)kb_events_push(&runtime.events, &event);
    ASSERT_EQ_U32(10U, kb_events_dropped(&runtime.events));
    poll_ok(&runtime, 1U, partial, sizeof(partial) - 1U);
    poll_ok(&runtime, KB_RUNTIME_CONSOLE_TIMEOUT_MS + 1U, NULL, 0U);
    ASSERT_EQ_U32(0U, kb_events_count(&runtime.events));
    ASSERT_EQ_U32(0U, runtime.reader.length);
    ASSERT_TRUE(strstr((const char *)fake.console, "invalid_command") != NULL);
}

static const test_case_t cases[] = {
    TEST_CASE(scanner_gate_blocks_every_gpio_operation),
    TEST_CASE(full_press_release_cycle_emits_reports_in_order),
    TEST_CASE(two_simultaneous_keys_preserve_multi_key_hid_state),
    TEST_CASE(valid_console_upload_commits_and_reloads_runtime_config),
    TEST_CASE(corrupt_upload_is_rejected_without_state_change),
    TEST_CASE(malformed_frame_emits_error_and_does_not_corrupt_state),
    TEST_CASE(release_only_event_emits_an_all_released_report),
    TEST_CASE(queue_overflow_and_partial_frame_timeout_are_bounded)
};
TEST_MAIN("runtime", cases)
