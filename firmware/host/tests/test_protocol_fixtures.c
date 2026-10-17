#include "kb_config.h"
#include "test_harness.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *load_file(const char *path, size_t *length)
{
    FILE *file = fopen(path, "rb");
    long size;
    char *buffer;
    if (file == NULL || fseek(file, 0L, SEEK_END) != 0) {
        if (file != NULL) {
            (void)fclose(file);
        }
        return NULL;
    }
    size = ftell(file);
    if (size < 0 || fseek(file, 0L, SEEK_SET) != 0) {
        (void)fclose(file);
        return NULL;
    }
    buffer = malloc((size_t)size + 1U);
    if (buffer == NULL) {
        (void)fclose(file);
        return NULL;
    }
    if (fread(buffer, 1U, (size_t)size, file) != (size_t)size) {
        free(buffer);
        (void)fclose(file);
        return NULL;
    }
    (void)fclose(file);
    buffer[size] = '\0';
    *length = (size_t)size;
    return buffer;
}

static void assert_valid_fixture(const char *path, uint16_t switch_count)
{
    char *json;
    size_t length;
    kb_config_t config;
    uint32_t calculated;
    kb_hal_probe_t descriptor;
    kb_config_error_list_t errors;
    memset(&descriptor, 0, sizeof(descriptor));
    descriptor.pin_count = 64U;
    json = load_file(path, &length);
    ASSERT_TRUE(json != NULL);
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_from_json(json, length, &config));
    ASSERT_EQ_U32(KB_CONFIG_PROTOCOL_VERSION, config.protocol_version);
    ASSERT_EQ_U32(KB_CONFIG_SCHEMA_VERSION, config.config_schema_version);
    ASSERT_EQ_U32(switch_count, config.switch_count);
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_calculate_crc32(&config, &calculated));
    ASSERT_EQ_U32(calculated, config.crc32);
    ASSERT_TRUE(kb_config_validate(&config, &descriptor, &errors));
    free(json);
}

TEST(valid_minimal_fixture)
{
    assert_valid_fixture("tests/protocol/valid/minimal_key.json", 1U);
}

TEST(valid_all_actions_fixture)
{
    kb_config_t config;
    char *json;
    size_t length;
    uint32_t calculated;
    kb_hal_probe_t descriptor;
    kb_config_error_list_t errors;
    memset(&descriptor, 0, sizeof(descriptor));
    descriptor.pin_count = 64U;
    json = load_file("tests/protocol/valid/all_actions.json", &length);
    ASSERT_TRUE(json != NULL);
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_from_json(json, length, &config));
    ASSERT_EQ_U32(4U, config.switch_count);
    ASSERT_EQ_U32(KB_ACTION_KEY, config.switches[0].action.type);
    ASSERT_EQ_U32(KB_ACTION_SHORTCUT, config.switches[1].action.type);
    ASSERT_EQ_U32(KB_ACTION_MEDIA, config.switches[2].action.type);
    ASSERT_EQ_U32(KB_ACTION_MODIFIER, config.switches[3].action.type);
    ASSERT_EQ_U32(0x16U, config.switches[1].action.usage_id);
    ASSERT_EQ_U32(0x00cdU, config.switches[2].action.usage_id);
    ASSERT_EQ_U32(0x00e6U, config.switches[3].action.usage_id);
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_calculate_crc32(&config, &calculated));
    ASSERT_EQ_U32(calculated, config.crc32);
    ASSERT_TRUE(kb_config_validate(&config, &descriptor, &errors));
    free(json);
}

static void assert_bad_fixture(const char *path, kb_config_parse_code_t expected)
{
    char *json;
    size_t length;
    kb_config_t output;
    kb_config_t before;
    json = load_file(path, &length);
    ASSERT_TRUE(json != NULL);
    memset(&output, 0xa5, sizeof(output));
    before = output;
    ASSERT_EQ_U32(expected, kb_config_from_json(json, length, &output));
    ASSERT_TRUE(memcmp(&before, &output, sizeof(output)) == 0);
    free(json);
}

TEST(malformed_fixtures_do_not_touch_output)
{
    assert_bad_fixture("tests/protocol/malformed/truncated.json",
                       KB_CONFIG_PARSE_JSON_SYNTAX);
    assert_bad_fixture("tests/protocol/malformed/missing_crc.json",
                       KB_CONFIG_PARSE_MISSING_FIELD);
    assert_bad_fixture("tests/protocol/malformed/unknown_action.json",
                       KB_CONFIG_PARSE_UNKNOWN_ACTION);
    assert_bad_fixture("tests/protocol/malformed/wrong_type.json",
                       KB_CONFIG_PARSE_WRONG_TYPE);
    assert_bad_fixture("tests/protocol/malformed/unknown_field.json",
                       KB_CONFIG_PARSE_UNKNOWN_FIELD);
}

static const test_case_t cases[] = {
    TEST_CASE(valid_minimal_fixture),
    TEST_CASE(valid_all_actions_fixture),
    TEST_CASE(malformed_fixtures_do_not_touch_output)
};

TEST_MAIN("protocol_fixtures", cases)
