#include "fake_hal.h"
#include "kb_scanner.h"
#include "test_harness.h"

#include <string.h>

static kb_hal_probe_t probe(void)
{
    kb_hal_probe_t value;
    memset(&value, 0, sizeof(value));
    value.pin_count = FAKE_HAL_MAX_PINS;
    return value;
}

static kb_config_t matrix_config(kb_scan_mode_t mode, uint16_t debounce_ms)
{
    static const uint8_t cells[][2] = {{0U, 0U}, {0U, 2U}, {1U, 1U},
                                       {2U, 0U}, {2U, 2U}};
    kb_config_t config;
    size_t index;
    kb_config_init(&config);
    (void)strcpy(config.chip_class, "host");
    config.matrix.rows = 3U;
    config.matrix.cols = 3U;
    config.pinmap.row_pin_count = 3U;
    config.pinmap.col_pin_count = 3U;
    config.pinmap.row_pins[0] = 1U;
    config.pinmap.row_pins[1] = 2U;
    config.pinmap.row_pins[2] = 3U;
    config.pinmap.col_pins[0] = 10U;
    config.pinmap.col_pins[1] = 11U;
    config.pinmap.col_pins[2] = 12U;
    config.pinmap.scan_mode = mode;
    config.pinmap.pull_up_source = KB_PULL_UP_INTERNAL;
    config.board_diode_direction =
        mode == KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP
            ? KB_DIODE_COL_TO_ROW
            : KB_DIODE_ROW_TO_COL;
    config.debounce_ms = debounce_ms;
    config.switch_count = (uint16_t)(sizeof(cells) / sizeof(cells[0]));
    for (index = 0U; index < config.switch_count; ++index) {
        config.switches[index].row = cells[index][0];
        config.switches[index].col = cells[index][1];
        config.switches[index].action.type = KB_ACTION_NONE;
    }
    (void)strcpy(config.meta.project_name, "scanner");
    (void)strcpy(config.meta.updated, "2026-10-17");
    config.generation = 1U;
    (void)kb_config_finalize_crc32(&config);
    return config;
}

static void scan(kb_scanner_t *scanner, kb_hal_ops_t *ops, uint64_t now,
                 kb_event_ring_t *events)
{
    size_t produced;
    ASSERT_EQ_U32(KB_SCANNER_OK,
                  kb_scanner_process(scanner, ops, now, events, &produced));
}

TEST(short_press_and_bounce_emit_nothing)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_config_t config = matrix_config(KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP,
                                       25U);
    kb_scanner_t scanner;
    kb_event_ring_t events;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    kb_events_init(&events);
    ASSERT_EQ_U32(KB_SCANNER_OK,
                  kb_scanner_init(&config, &descriptor, &ops, &scanner));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, true));
    scan(&scanner, &ops, 0U, &events);
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, false));
    scan(&scanner, &ops, 20U, &events);
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, true));
    scan(&scanner, &ops, 22U, &events);
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, false));
    scan(&scanner, &ops, 23U, &events);
    ASSERT_EQ_U32(0U, kb_events_count(&events));
}

TEST(stable_press_and_release_each_emit_once)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_config_t config = matrix_config(KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP,
                                       10U);
    kb_scanner_t scanner;
    kb_event_ring_t events;
    kb_event_t event;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    kb_events_init(&events);
    ASSERT_EQ_U32(KB_SCANNER_OK,
                  kb_scanner_init(&config, &descriptor, &ops, &scanner));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, true));
    scan(&scanner, &ops, 100U, &events);
    scan(&scanner, &ops, 109U, &events);
    scan(&scanner, &ops, 110U, &events);
    scan(&scanner, &ops, 150U, &events);
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, false));
    scan(&scanner, &ops, 151U, &events);
    scan(&scanner, &ops, 161U, &events);
    ASSERT_EQ_U32(2U, kb_events_count(&events));
    ASSERT_TRUE(kb_events_pop(&events, &event));
    ASSERT_EQ_U32(KB_EVENT_KEY_DOWN, event.type);
    ASSERT_EQ_U32(0U, event.switch_id);
    ASSERT_TRUE(kb_events_pop(&events, &event));
    ASSERT_EQ_U32(KB_EVENT_KEY_UP, event.type);
}

TEST(repeated_bounce_settles_to_one_transition)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_config_t config = matrix_config(KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP,
                                       10U);
    kb_scanner_t scanner;
    kb_event_ring_t events;
    kb_event_t event;
    uint64_t now;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    kb_events_init(&events);
    ASSERT_EQ_U32(KB_SCANNER_OK,
                  kb_scanner_init(&config, &descriptor, &ops, &scanner));
    for (now = 0U; now < 8U; ++now) {
        ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, now % 2U == 0U));
        scan(&scanner, &ops, now, &events);
    }
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, true));
    scan(&scanner, &ops, 8U, &events);
    scan(&scanner, &ops, 18U, &events);
    scan(&scanner, &ops, 40U, &events);
    ASSERT_EQ_U32(1U, kb_events_count(&events));
    ASSERT_TRUE(kb_events_pop(&events, &event));
    ASSERT_EQ_U32(KB_EVENT_KEY_DOWN, event.type);
}

TEST(switches_debounce_independently)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_config_t config = matrix_config(KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP,
                                       10U);
    kb_scanner_t scanner;
    kb_event_ring_t events;
    kb_event_t event;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    kb_events_init(&events);
    ASSERT_EQ_U32(KB_SCANNER_OK,
                  kb_scanner_init(&config, &descriptor, &ops, &scanner));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 10U, true));
    scan(&scanner, &ops, 0U, &events);
    ASSERT_TRUE(fake_hal_set_switch(&fake, 1U, 12U, true));
    scan(&scanner, &ops, 6U, &events);
    scan(&scanner, &ops, 10U, &events);
    ASSERT_EQ_U32(1U, kb_events_count(&events));
    ASSERT_TRUE(kb_events_pop(&events, &event));
    ASSERT_EQ_U32(0U, event.switch_id);
    scan(&scanner, &ops, 16U, &events);
    ASSERT_TRUE(kb_events_pop(&events, &event));
    ASSERT_EQ_U32(1U, event.switch_id);
}

TEST(populated_subset_only_produces_events)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_config_t config = matrix_config(KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP,
                                       5U);
    kb_scanner_t scanner;
    kb_event_ring_t events;
    kb_event_t event;
    uint16_t index;
    uint64_t now = 0U;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    kb_events_init(&events);
    ASSERT_EQ_U32(KB_SCANNER_OK,
                  kb_scanner_init(&config, &descriptor, &ops, &scanner));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 2U, 10U, true));
    scan(&scanner, &ops, now, &events);
    scan(&scanner, &ops, now + 5U, &events);
    ASSERT_EQ_U32(0U, kb_events_count(&events));
    ASSERT_TRUE(fake_hal_set_switch(&fake, 2U, 10U, false));
    for (index = 0U; index < config.switch_count; ++index) {
        uint8_t row_pin = config.pinmap.row_pins[config.switches[index].row];
        uint8_t col_pin = config.pinmap.col_pins[config.switches[index].col];
        now += 10U;
        ASSERT_TRUE(fake_hal_set_switch(&fake, row_pin, col_pin, true));
        scan(&scanner, &ops, now, &events);
        scan(&scanner, &ops, now + 5U, &events);
        ASSERT_TRUE(fake_hal_set_switch(&fake, row_pin, col_pin, false));
        scan(&scanner, &ops, now + 6U, &events);
        scan(&scanner, &ops, now + 11U, &events);
        ASSERT_TRUE(kb_events_pop(&events, &event));
        ASSERT_EQ_U32(KB_EVENT_KEY_DOWN, event.type);
        ASSERT_EQ_U32(index, event.switch_id);
        ASSERT_TRUE(kb_events_pop(&events, &event));
        ASSERT_EQ_U32(KB_EVENT_KEY_UP, event.type);
        ASSERT_EQ_U32(index, event.switch_id);
        ASSERT_EQ_U32(0U, kb_events_count(&events));
        now += 12U;
    }
}

TEST(scan_modes_have_identical_randomized_streams)
{
    fake_hal_t fakes[2];
    kb_hal_ops_t ops[2];
    kb_hal_probe_t descriptor = probe();
    kb_config_t configs[2];
    kb_scanner_t scanners[2];
    kb_event_ring_t events[2];
    bool closed[5] = {false};
    uint32_t random = UINT32_C(0x12345678);
    uint64_t now = 0U;
    size_t step;
    int mode;
    configs[0] = matrix_config(KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP, 5U);
    configs[1] = matrix_config(KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP, 5U);
    for (mode = 0; mode < 2; ++mode) {
        fake_hal_reset(&fakes[mode]);
        ops[mode] = fake_hal_ops(&fakes[mode]);
        kb_events_init(&events[mode]);
        ASSERT_EQ_U32(KB_SCANNER_OK,
                      kb_scanner_init(&configs[mode], &descriptor, &ops[mode],
                                      &scanners[mode]));
    }
    for (step = 0U; step < 100U; ++step) {
        size_t selected;
        random = random * UINT32_C(1664525) + UINT32_C(1013904223);
        selected = random % 5U;
        closed[selected] = !closed[selected];
        for (mode = 0; mode < 2; ++mode) {
            uint8_t row = configs[mode].switches[selected].row;
            uint8_t col = configs[mode].switches[selected].col;
            ASSERT_TRUE(fake_hal_set_switch(&fakes[mode],
                configs[mode].pinmap.row_pins[row],
                configs[mode].pinmap.col_pins[col], closed[selected]));
            scan(&scanners[mode], &ops[mode], now, &events[mode]);
            scan(&scanners[mode], &ops[mode], now + 5U, &events[mode]);
        }
        now += 6U;
    }
    ASSERT_EQ_U32(kb_events_count(&events[0]), kb_events_count(&events[1]));
    while (kb_events_count(&events[0]) != 0U) {
        kb_event_t left;
        kb_event_t right;
        ASSERT_TRUE(kb_events_pop(&events[0], &left));
        ASSERT_TRUE(kb_events_pop(&events[1], &right));
        ASSERT_EQ_U32(left.type, right.type);
        ASSERT_EQ_U32(left.switch_id, right.switch_id);
        ASSERT_EQ_U32(left.timestamp_ms, right.timestamp_ms);
    }
}

TEST(pin_access_is_isolated_by_role)
{
    fake_hal_t fake;
    kb_hal_ops_t ops;
    kb_hal_probe_t descriptor = probe();
    kb_config_t config = matrix_config(KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP,
                                       5U);
    kb_scanner_t scanner;
    kb_event_ring_t events;
    size_t index;
    fake_hal_reset(&fake);
    ops = fake_hal_ops(&fake);
    kb_events_init(&events);
    ASSERT_EQ_U32(KB_SCANNER_OK,
                  kb_scanner_init(&config, &descriptor, &ops, &scanner));
    for (index = 0U; index < 50U; ++index) {
        const uint8_t row = config.switches[index % config.switch_count].row;
        const uint8_t col = config.switches[index % config.switch_count].col;
        ASSERT_TRUE(fake_hal_set_switch(&fake, config.pinmap.row_pins[row],
                                        config.pinmap.col_pins[col],
                                        index % 3U != 0U));
        scan(&scanner, &ops, index * 5U, &events);
    }
    for (index = 0U; index < fake.pin_write_call_count; ++index) {
        ASSERT_TRUE(fake.pin_write_calls[index] >= 10U &&
                    fake.pin_write_calls[index] <= 12U);
    }
    for (index = 0U; index < fake.pin_read_call_count; ++index) {
        ASSERT_TRUE(fake.pin_read_calls[index] >= 1U &&
                    fake.pin_read_calls[index] <= 3U);
    }
}

static const test_case_t cases[] = {
    TEST_CASE(short_press_and_bounce_emit_nothing),
    TEST_CASE(stable_press_and_release_each_emit_once),
    TEST_CASE(repeated_bounce_settles_to_one_transition),
    TEST_CASE(switches_debounce_independently),
    TEST_CASE(populated_subset_only_produces_events),
    TEST_CASE(scan_modes_have_identical_randomized_streams),
    TEST_CASE(pin_access_is_isolated_by_role)
};

TEST_MAIN("scanner", cases)
