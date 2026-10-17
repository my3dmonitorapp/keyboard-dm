#include "kb_config.h"
#include "test_harness.h"

#include <stdint.h>
#include <string.h>

static kb_hal_probe_t probe(void)
{
    kb_hal_probe_t value;
    memset(&value, 0, sizeof(value));
    value.pin_count = 40U;
    value.reserved_pin_count = 5U;
    value.reserved_pins[0] = 6U;
    value.reserved_pins[1] = 7U;
    value.reserved_pins[2] = 8U;
    value.reserved_pins[3] = 12U;
    value.reserved_pins[4] = 15U;
    value.input_only_pin_count = 5U;
    value.external_pullup_pin_count = 6U;
    value.input_only_pins[0] = 35U;
    value.input_only_pins[1] = 36U;
    value.input_only_pins[2] = 37U;
    value.input_only_pins[3] = 38U;
    value.input_only_pins[4] = 39U;
    value.external_pullup_pins[0] = 34U;
    value.external_pullup_pins[1] = 35U;
    value.external_pullup_pins[2] = 36U;
    value.external_pullup_pins[3] = 37U;
    value.external_pullup_pins[4] = 38U;
    value.external_pullup_pins[5] = 39U;
    return value;
}

static kb_config_t minimal(void)
{
    kb_config_t config;
    kb_config_init(&config);
    (void)strcpy(config.chip_class, "esp32");
    config.matrix.rows = 2U;
    config.matrix.cols = 2U;
    config.pinmap.row_pin_count = 2U;
    config.pinmap.row_pins[0] = 1U;
    config.pinmap.row_pins[1] = 2U;
    config.pinmap.col_pin_count = 2U;
    config.pinmap.col_pins[0] = 3U;
    config.pinmap.col_pins[1] = 4U;
    config.switch_count = 1U;
    config.switches[0].row = 0U;
    config.switches[0].col = 1U;
    config.switches[0].action.type = KB_ACTION_KEY;
    (void)strcpy(config.switches[0].action.key_name, "a");
    config.switches[0].action.usage_id = 0x04U;
    (void)strcpy(config.meta.project_name, "Minimal");
    (void)strcpy(config.meta.updated, "2026-10-17T00:00:00+00:00");
    config.generation = 1U;
    (void)kb_config_finalize_crc32(&config);
    return config;
}

static bool has_code(const kb_config_error_list_t *errors,
                     kb_config_error_code_t code)
{
    size_t index;
    for (index = 0U; index < errors->count; ++index) {
        if (errors->items[index].code == code) {
            return true;
        }
    }
    return false;
}

static void expect_error(kb_config_t *config, kb_config_error_code_t code)
{
    kb_config_error_list_t errors;
    kb_hal_probe_t descriptor = probe();
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK, kb_config_finalize_crc32(config));
    ASSERT_TRUE(!kb_config_validate(config, &descriptor, &errors));
    ASSERT_TRUE(has_code(&errors, code));
}

TEST(valid_minimal_config)
{
    kb_config_t config = minimal();
    kb_config_error_list_t errors;
    kb_hal_probe_t descriptor = probe();
    ASSERT_TRUE(kb_config_validate(&config, &descriptor, &errors));
    ASSERT_EQ_U32(0U, errors.count);
}

TEST(bad_protocol_version)
{
    kb_config_t config = minimal();
    config.protocol_version = 2U;
    expect_error(&config, KB_CONFIG_ERROR_BAD_PROTOCOL_VERSION);
}

TEST(bad_schema_version)
{
    kb_config_t config = minimal();
    config.config_schema_version = 2U;
    expect_error(&config, KB_CONFIG_ERROR_BAD_SCHEMA_VERSION);
}

TEST(wrong_pin_count)
{
    kb_config_t config = minimal();
    config.pinmap.row_pin_count = 1U;
    expect_error(&config, KB_CONFIG_ERROR_ROW_PIN_COUNT);
}

TEST(populated_outside_matrix)
{
    kb_config_t config = minimal();
    config.switches[0].row = 2U;
    expect_error(&config, KB_CONFIG_ERROR_POPULATED_OUT_OF_RANGE);
}

TEST(illegal_hid_usage)
{
    kb_config_t config = minimal();
    config.switches[0].action.usage_id = 0x7fU;
    expect_error(&config, KB_CONFIG_ERROR_HID_USAGE);
}

TEST(crc_mismatch)
{
    kb_config_t config = minimal();
    kb_config_error_list_t errors;
    kb_hal_probe_t descriptor = probe();
    config.crc32 ^= UINT32_C(1);
    ASSERT_TRUE(!kb_config_validate(&config, &descriptor, &errors));
    ASSERT_TRUE(has_code(&errors, KB_CONFIG_ERROR_CRC_MISMATCH));
}

TEST(duplicate_pin)
{
    kb_config_t config = minimal();
    config.pinmap.col_pins[1] = config.pinmap.row_pins[0];
    expect_error(&config, KB_CONFIG_ERROR_DUPLICATE_PIN);
}

TEST(reserved_chip_pin)
{
    kb_config_t config = minimal();
    config.pinmap.row_pins[0] = 6U;
    expect_error(&config, KB_CONFIG_ERROR_RESERVED_PIN);
}

TEST(input_only_row_pin)
{
    kb_config_t config = minimal();
    config.pinmap.row_pins[0] = 35U;
    expect_error(&config, KB_CONFIG_ERROR_INPUT_ONLY_OUTPUT_PIN);
}

TEST(external_pullup_required)
{
    kb_config_t config = minimal();
    config.pinmap.col_pins[0] = 34U;
    expect_error(&config, KB_CONFIG_ERROR_EXTERNAL_PULLUP_REQUIRED);
}

TEST(scan_diode_pair_must_match)
{
    kb_config_t config = minimal();
    config.pinmap.scan_mode = KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP;
    expect_error(&config, KB_CONFIG_ERROR_SCAN_DIODE_MISMATCH);
}

TEST(debounce_defaults_and_range_are_validated)
{
    kb_config_t config = minimal();
    ASSERT_EQ_U32(KB_CONFIG_DEFAULT_DEBOUNCE_MS, config.debounce_ms);
    config.debounce_ms = KB_CONFIG_MIN_DEBOUNCE_MS - 1U;
    expect_error(&config, KB_CONFIG_ERROR_DEBOUNCE_RANGE);
    config.debounce_ms = KB_CONFIG_MAX_DEBOUNCE_MS + 1U;
    expect_error(&config, KB_CONFIG_ERROR_DEBOUNCE_RANGE);
}

TEST(canonical_switch_order_is_row_major)
{
    kb_config_t config = minimal();
    char json[4096];
    char *first;
    char *second;
    size_t length;
    config.switch_count = 2U;
    config.switches[0].row = 1U;
    config.switches[0].col = 1U;
    config.switches[1].row = 0U;
    config.switches[1].col = 0U;
    config.switches[1].action.type = KB_ACTION_KEY;
    (void)strcpy(config.switches[1].action.key_name, "b");
    config.switches[1].action.usage_id = 0x05U;
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK, kb_config_finalize_crc32(&config));
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_to_json(&config, json, sizeof(json), &length));
    ASSERT_TRUE(length > 0U);
    first = strstr(json, "{\"row\":0,\"col\":0");
    second = strstr(json, "{\"row\":1,\"col\":1");
    ASSERT_TRUE(first != NULL && second != NULL && first < second);
}

TEST(canonical_round_trip)
{
    kb_config_t source = minimal();
    kb_config_t restored;
    kb_config_error_list_t errors;
    kb_hal_probe_t descriptor = probe();
    char first[4096];
    char second[4096];
    size_t first_length;
    size_t second_length;
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_to_json(&source, first, sizeof(first), &first_length));
    memset(&restored, 0xa5, sizeof(restored));
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_from_json(first, first_length, &restored));
    ASSERT_TRUE(kb_config_validate(&restored, &descriptor, &errors));
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_to_json(&restored, second, sizeof(second),
                                    &second_length));
    ASSERT_EQ_U32(first_length, second_length);
    ASSERT_STREQ(first, second);
    ASSERT_EQ_U32(source.crc32, restored.crc32);
}

static const test_case_t cases[] = {
    TEST_CASE(valid_minimal_config),
    TEST_CASE(bad_protocol_version),
    TEST_CASE(bad_schema_version),
    TEST_CASE(wrong_pin_count),
    TEST_CASE(populated_outside_matrix),
    TEST_CASE(illegal_hid_usage),
    TEST_CASE(crc_mismatch),
    TEST_CASE(duplicate_pin),
    TEST_CASE(reserved_chip_pin),
    TEST_CASE(input_only_row_pin),
    TEST_CASE(external_pullup_required),
    TEST_CASE(scan_diode_pair_must_match),
    TEST_CASE(debounce_defaults_and_range_are_validated),
    TEST_CASE(canonical_switch_order_is_row_major),
    TEST_CASE(canonical_round_trip)
};

TEST_MAIN("config", cases)
