#include "fake_hal.h"
#include "kb_crc32.h"
#include "kb_protocol.h"
#include "test_harness.h"

#include <stdio.h>
#include <string.h>

static kb_hal_probe_t probe(void)
{
    kb_hal_probe_t value; memset(&value, 0, sizeof(value));
    value.pin_count = FAKE_HAL_MAX_PINS; return value;
}

static kb_config_t config_named(const char *name)
{
    kb_config_t config; kb_config_init(&config);
    (void)strcpy(config.chip_class, "host"); config.matrix.rows = 1U; config.matrix.cols = 1U;
    config.pinmap.row_pin_count = 1U; config.pinmap.col_pin_count = 1U;
    config.pinmap.row_pins[0] = 1U; config.pinmap.col_pins[0] = 2U;
    config.switch_count = 1U; config.switches[0].action.type = KB_ACTION_KEY;
    (void)strcpy(config.switches[0].action.key_name, "a"); config.switches[0].action.usage_id = 4U;
    (void)strcpy(config.meta.project_name, name); (void)strcpy(config.meta.updated, "2026-10-17");
    config.generation = 1U; (void)kb_config_finalize_crc32(&config); return config;
}

static void setup(fake_hal_t *fake, kb_hal_ops_t *ops, kb_boot_t *boot,
                  kb_protocol_context_t *protocol)
{
    kb_hal_probe_t descriptor = probe(); fake_hal_reset(fake); *ops = fake_hal_ops(fake);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(boot, &descriptor, ops));
    kb_protocol_context_init(protocol, boot, NULL);
}

static kb_protocol_apply_result_t process(kb_protocol_context_t *protocol,
                                          const char *line, char *response,
                                          size_t capacity)
{
    size_t length = 0U;
    kb_protocol_apply_result_t result = kb_protocol_process_line(protocol, line, strlen(line), response, capacity, &length);
    if (capacity != 0U && length < capacity) response[length] = '\0';
    return result;
}

static void b64(const uint8_t *input, size_t length, char *output)
{
    static const char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t in = 0U, out = 0U;
    while (in < length) {
        uint32_t value = (uint32_t)input[in++] << 16U; unsigned count = 1U;
        if (in < length) { value |= (uint32_t)input[in++] << 8U; ++count; }
        if (in < length) { value |= input[in++]; ++count; }
        output[out++] = alphabet[(value >> 18U) & 63U]; output[out++] = alphabet[(value >> 12U) & 63U];
        output[out++] = count > 1U ? alphabet[(value >> 6U) & 63U] : '=';
        output[out++] = count > 2U ? alphabet[value & 63U] : '=';
    }
    output[out] = '\0';
}

static void upload_chunks(kb_protocol_context_t *protocol, const char *json,
                          size_t json_length, uint32_t crc, char *response)
{
    char line[KB_PROTOCOL_MAX_LINE_BYTES + 1U]; size_t offset = 0U; uint32_t seq;
    (void)snprintf(line, sizeof(line), "{\"version\":\"0.1\",\"id\":\"s\",\"cmd\":\"config_upload\",\"params\":{\"phase\":\"start\",\"upload_id\":\"u\",\"encoding\":\"base64\",\"total_bytes\":%lu,\"crc32\":%lu}}",
                   (unsigned long)json_length, (unsigned long)crc);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_OK, process(protocol, line, response, 10000U));
    for (seq = 0U; seq < 3U; ++seq) {
        const size_t remaining = json_length - offset;
        const size_t part = seq == 2U ? remaining : (json_length / 3U);
        char encoded[1400]; b64((const uint8_t *)json + offset, part, encoded); offset += part;
        (void)snprintf(line, sizeof(line), "{\"id\":\"c\",\"cmd\":\"config_upload\",\"params\":{\"phase\":\"chunk\",\"upload_id\":\"u\",\"seq\":%lu,\"data\":\"%s\"}}", (unsigned long)seq, encoded);
        ASSERT_EQ_U32(KB_PROTOCOL_APPLY_OK, process(protocol, line, response, 10000U));
    }
}

TEST(version_and_key_events)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_boot_t boot; kb_protocol_context_t protocol; char response[512];
    setup(&fake, &ops, &boot, &protocol);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_OK, process(&protocol, "{\"version\":1,\"id\":\"v\",\"cmd\":\"version\",\"params\":{}}\n", response, sizeof(response)));
    ASSERT_TRUE(strstr(response, "\"protocol\":\"0.1\"") != NULL);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_OK, process(&protocol, "{\"id\":\"e\",\"cmd\":\"key_event\",\"params\":{\"enabled\":true}}", response, sizeof(response)));
    ASSERT_TRUE(protocol.key_events_enabled);
}

TEST(bad_version_and_unknown_field_are_structured_errors)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_boot_t boot; kb_protocol_context_t protocol; char response[512];
    setup(&fake, &ops, &boot, &protocol);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_BAD_CONFIG, process(&protocol, "{\"version\":2,\"id\":\"x\",\"cmd\":\"version\",\"params\":{}}", response, sizeof(response)));
    ASSERT_TRUE(strstr(response, "\"ok\":false") != NULL);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_BAD_CONFIG, process(&protocol, "{\"id\":\"x\",\"cmd\":\"version\",\"params\":{},\"mystery\":1}", response, sizeof(response)));
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_BAD_CONFIG, process(&protocol, "{\"id\":\"x\",\"cmd\":\"no_such_command\",\"params\":{}}", response, sizeof(response)));
    ASSERT_TRUE(strstr(response, "unknown_command") != NULL);
}

TEST(incremental_reader_rejects_invalid_utf8)
{
    kb_protocol_reader_t reader; kb_protocol_request_t request; kb_protocol_parse_error_t error;
    const uint8_t bytes[] = {'{', 0xffU, '}', '\n'}; size_t consumed;
    kb_protocol_reader_init(&reader);
    ASSERT_EQ_U32(KB_PROTOCOL_READ_ERROR, kb_protocol_read_one_cmd(&reader, bytes, sizeof(bytes), &consumed, &request, &error));
    ASSERT_EQ_U32(KB_PROTOCOL_PARSE_BAD_UTF8, error); ASSERT_EQ_U32(sizeof(bytes), consumed);
}

TEST(incremental_reader_rejects_overlong_frame_and_recovers)
{
    static const uint8_t valid[] =
        "{\"version\":1,\"id\":\"v\",\"cmd\":\"version\",\"params\":{}}\n";
    kb_protocol_reader_t reader;
    kb_protocol_request_t request;
    kb_protocol_parse_error_t error;
    uint8_t bytes[KB_PROTOCOL_MAX_LINE_BYTES + 2U];
    size_t consumed;
    memset(bytes, 'x', sizeof(bytes));
    bytes[sizeof(bytes) - 1U] = '\n';
    kb_protocol_reader_init(&reader);
    ASSERT_EQ_U32(KB_PROTOCOL_READ_ERROR,
                  kb_protocol_read_one_cmd(&reader, bytes, sizeof(bytes),
                                           &consumed, &request, &error));
    ASSERT_EQ_U32(KB_PROTOCOL_PARSE_OVERLONG, error);
    ASSERT_EQ_U32(sizeof(bytes), consumed);
    ASSERT_EQ_U32(KB_PROTOCOL_READ_COMMAND,
                  kb_protocol_read_one_cmd(
                      &reader, valid, sizeof(valid) - 1U, &consumed, &request,
                      &error));
}

TEST(three_chunk_bad_crc_then_good_commit_and_get)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_boot_t boot; kb_protocol_context_t protocol;
    kb_config_t config = config_named("uploaded"); char json[8192]; size_t json_length; char response[10000]; uint32_t crc;
    setup(&fake, &ops, &boot, &protocol);
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK, kb_config_to_json(&config, json, sizeof(json), &json_length)); crc = kb_crc32(json, json_length);
    upload_chunks(&protocol, json, json_length, crc ^ 1U, response);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_BAD_CONFIG, process(&protocol, "{\"id\":\"bad\",\"cmd\":\"config_commit\",\"params\":{}}", response, sizeof(response)));
    ASSERT_TRUE(kb_boot_active_config(&boot) == NULL); ASSERT_TRUE(strstr(response, "bad_crc") != NULL);
    upload_chunks(&protocol, json, json_length, crc, response);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_OK, process(&protocol, "{\"id\":\"good\",\"cmd\":\"config_commit\",\"params\":{}}", response, sizeof(response)));
    ASSERT_STREQ("uploaded", kb_boot_active_config(&boot)->meta.project_name);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_OK, process(&protocol, "{\"id\":\"get\",\"cmd\":\"config_get\",\"params\":{\"source\":\"active\"}}", response, sizeof(response)));
    ASSERT_TRUE(strstr(response, "\"project_name\":\"uploaded\"") != NULL);
}

TEST(out_of_order_chunk_does_not_mutate_config)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_boot_t boot; kb_protocol_context_t protocol; char response[512];
    setup(&fake, &ops, &boot, &protocol);
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_OK, process(&protocol, "{\"id\":\"s\",\"cmd\":\"config_upload\",\"params\":{\"phase\":\"start\",\"upload_id\":\"u\",\"encoding\":\"base64\",\"total_bytes\":3,\"crc32\":1}}", response, sizeof(response)));
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_BAD_STATE, process(&protocol, "{\"id\":\"c\",\"cmd\":\"config_upload\",\"params\":{\"phase\":\"chunk\",\"upload_id\":\"u\",\"seq\":1,\"data\":\"YWJj\"}}", response, sizeof(response)));
    ASSERT_TRUE(kb_boot_active_config(&boot) == NULL); ASSERT_EQ_U32(0U, protocol.upload_length);
}

TEST(factory_reset_erases_config_slots)
{
    fake_hal_t fake; kb_hal_ops_t ops; kb_boot_t boot; kb_protocol_context_t protocol; kb_config_t config = config_named("active"); char response[512];
    setup(&fake, &ops, &boot, &protocol); ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_apply_config(&boot, &config));
    ASSERT_EQ_U32(KB_PROTOCOL_APPLY_OK, process(&protocol, "{\"id\":\"f\",\"cmd\":\"factory_reset\",\"params\":{\"confirm\":\"ERASE_CONFIG_AND_BONDS\"}}", response, sizeof(response)));
    ASSERT_TRUE(kb_boot_active_config(&boot) == NULL); ASSERT_EQ_U32(0U, fake.store_lengths[KB_HAL_STORE_CONFIG_A]);
    ASSERT_EQ_U32(0U, fake.store_lengths[KB_HAL_STORE_CONFIG_B]); ASSERT_EQ_U32(0U, fake.store_lengths[KB_HAL_STORE_METADATA]);
}

static const test_case_t cases[] = {
    TEST_CASE(version_and_key_events), TEST_CASE(bad_version_and_unknown_field_are_structured_errors),
    TEST_CASE(incremental_reader_rejects_invalid_utf8), TEST_CASE(three_chunk_bad_crc_then_good_commit_and_get),
    TEST_CASE(incremental_reader_rejects_overlong_frame_and_recovers),
    TEST_CASE(out_of_order_chunk_does_not_mutate_config), TEST_CASE(factory_reset_erases_config_slots)
};
TEST_MAIN("protocol", cases)
