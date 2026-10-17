#include "fake_hal.h"
#include "kb_boot.h"
#include "test_harness.h"

#include <string.h>

static kb_hal_probe_t probe(void)
{
    kb_hal_probe_t value;
    memset(&value, 0, sizeof(value));
    value.pin_count = FAKE_HAL_MAX_PINS;
    return value;
}

static kb_config_t valid_config(const char *name)
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
    config.switch_count = 1U;
    config.switches[0].row = 0U;
    config.switches[0].col = 0U;
    config.switches[0].action.type = KB_ACTION_NONE;
    (void)strcpy(config.meta.project_name, name);
    (void)strcpy(config.meta.updated, "2026-10-17");
    config.generation = 1U;
    (void)kb_config_finalize_crc32(&config);
    return config;
}

static void write_slot(kb_hal_ops_t *ops, kb_hal_store_slot_t slot,
                       const kb_config_t *config)
{
    char json[4096];
    size_t length;
    ASSERT_EQ_U32(KB_CONFIG_PARSE_OK,
                  kb_config_to_json(config, json, sizeof(json), &length));
    ASSERT_EQ_U32(KB_HAL_OK,
                  ops->hal_store_write(ops->ctx, slot, json, length));
}

TEST(no_config_has_distinct_banner_and_no_pin_writes)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_boot_t boot;
    char banner[FAKE_HAL_TRANSPORT_CAPACITY + 1U];
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(&boot, &descriptor, &ops));
    ASSERT_EQ_U32(KB_BOOT_NO_CONFIG, boot.status.state);
    ASSERT_EQ_U32(0U, fake.pin_write_call_count);
    memcpy(banner, fake.console, fake.console_length);
    banner[fake.console_length] = '\0';
    ASSERT_TRUE(strstr(banner, "\"reason\":\"no_config\"") != NULL);
}

TEST(garbage_slots_enter_safe_mode_without_gpio)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_boot_t boot;
    char banner[FAKE_HAL_TRANSPORT_CAPACITY + 1U];
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    memcpy(fake.stores[KB_HAL_STORE_CONFIG_A], "garbage-a", 9U);
    fake.store_lengths[KB_HAL_STORE_CONFIG_A] = 9U;
    memcpy(fake.stores[KB_HAL_STORE_CONFIG_B], "garbage-b", 9U);
    fake.store_lengths[KB_HAL_STORE_CONFIG_B] = 9U;
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(&boot, &descriptor, &ops));
    ASSERT_EQ_U32(KB_BOOT_SAFE_MODE, boot.status.state);
    ASSERT_EQ_U32(0U, fake.pin_write_call_count);
    memcpy(banner, fake.console, fake.console_length);
    banner[fake.console_length] = '\0';
    ASSERT_TRUE(strstr(banner, "both_slots_invalid") != NULL);
}

TEST(valid_slot_a_is_discovered)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_boot_t boot;
    kb_config_t config = valid_config("slot-a");
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    write_slot(&ops, KB_HAL_STORE_CONFIG_A, &config);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(&boot, &descriptor, &ops));
    ASSERT_EQ_U32(KB_BOOT_VALID, boot.status.state);
    ASSERT_EQ_U32(1U, boot.status.active_generation);
    ASSERT_STREQ("slot-a", kb_boot_active_config(&boot)->meta.project_name);
}

TEST(corrupt_metadata_never_guesses_an_active_slot)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_boot_t boot;
    kb_boot_t restarted;
    kb_config_t config = valid_config("active");
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(&boot, &descriptor, &ops));
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_apply_config(&boot, &config));
    fake.stores[KB_HAL_STORE_METADATA][0] ^= UINT8_C(0xff);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(&restarted, &descriptor, &ops));
    ASSERT_EQ_U32(KB_BOOT_SAFE_MODE, restarted.status.state);
    ASSERT_EQ_U32(0U, fake.pin_write_call_count);
}

TEST(partial_commit_fault_leaves_active_generation_unchanged)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_boot_t boot;
    kb_boot_t restarted;
    kb_config_t first = valid_config("first");
    kb_config_t second = valid_config("second");
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(&boot, &descriptor, &ops));
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_apply_config(&boot, &first));
    fake.next_store_write_error = KB_HAL_ERR_IO;
    fake.next_store_write_partial_bytes = 17U;
    ASSERT_EQ_U32(KB_BOOT_STORAGE_ERROR,
                  kb_boot_apply_config(&boot, &second));
    ASSERT_EQ_U32(1U, boot.status.active_generation);
    ASSERT_STREQ("first", kb_boot_active_config(&boot)->meta.project_name);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(&restarted, &descriptor, &ops));
    ASSERT_EQ_U32(KB_BOOT_VALID, restarted.status.state);
    ASSERT_EQ_U32(1U, restarted.status.active_generation);
    ASSERT_STREQ("first", kb_boot_active_config(&restarted)->meta.project_name);
}

TEST(recover_uses_last_good_and_prevents_aba)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_boot_t boot;
    kb_config_t first = valid_config("first");
    kb_config_t second = valid_config("second");
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_start(&boot, &descriptor, &ops));
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_apply_config(&boot, &first));
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_apply_config(&boot, &second));
    ASSERT_EQ_U32(2U, boot.status.active_generation);
    fake.stores[boot.active_slot][0] ^= UINT8_C(0xff);
    ASSERT_EQ_U32(KB_BOOT_OK, kb_boot_recover(&boot));
    ASSERT_EQ_U32(KB_BOOT_VALID, boot.status.state);
    ASSERT_EQ_U32(1U, boot.status.active_generation);
    ASSERT_STREQ("first", kb_boot_active_config(&boot)->meta.project_name);
    ASSERT_EQ_U32(KB_BOOT_NO_CHANGE, kb_boot_recover(&boot));
    ASSERT_EQ_U32(1U, boot.status.active_generation);
}

static const test_case_t cases[] = {
    TEST_CASE(no_config_has_distinct_banner_and_no_pin_writes),
    TEST_CASE(garbage_slots_enter_safe_mode_without_gpio),
    TEST_CASE(valid_slot_a_is_discovered),
    TEST_CASE(corrupt_metadata_never_guesses_an_active_slot),
    TEST_CASE(partial_commit_fault_leaves_active_generation_unchanged),
    TEST_CASE(recover_uses_last_good_and_prevents_aba)
};

TEST_MAIN("boot", cases)
