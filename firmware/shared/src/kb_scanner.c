#include "kb_scanner.h"

#include <string.h>

static bool hal_complete(const kb_hal_ops_t *hal)
{
    return hal != NULL && hal->hal_pin_direction != NULL &&
           hal->hal_pin_write != NULL && hal->hal_pin_read != NULL;
}

static kb_scanner_result_t configure_inputs(const kb_config_t *config,
                                            const kb_hal_ops_t *hal)
{
    const bool drive_rows = config->pinmap.scan_mode ==
                            KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP;
    const uint8_t *drive_pins = drive_rows ? config->pinmap.row_pins
                                           : config->pinmap.col_pins;
    const uint8_t *read_pins = drive_rows ? config->pinmap.col_pins
                                          : config->pinmap.row_pins;
    const uint8_t drive_count = drive_rows ? config->pinmap.row_pin_count
                                           : config->pinmap.col_pin_count;
    const uint8_t read_count = drive_rows ? config->pinmap.col_pin_count
                                          : config->pinmap.row_pin_count;
    uint8_t index;

    for (index = 0U; index < drive_count; ++index) {
        if (hal->hal_pin_direction(hal->ctx, drive_pins[index],
                                   KB_HAL_PIN_INPUT) != KB_HAL_OK) {
            return KB_SCANNER_HAL_ERROR;
        }
    }
    for (index = 0U; index < read_count; ++index) {
        if (hal->hal_pin_direction(hal->ctx, read_pins[index],
                                   KB_HAL_PIN_INPUT) != KB_HAL_OK) {
            return KB_SCANNER_HAL_ERROR;
        }
        if (hal->hal_pin_input_pulldown_en != NULL &&
            hal->hal_pin_input_pulldown_en(hal->ctx, read_pins[index], false) !=
                KB_HAL_OK) {
            return KB_SCANNER_HAL_ERROR;
        }
    }
    return KB_SCANNER_OK;
}

kb_scanner_result_t kb_scanner_init(const kb_config_t *config,
                                    const kb_hal_probe_t *descriptor,
                                    const kb_hal_ops_t *hal,
                                    kb_scanner_t *out)
{
    kb_config_error_list_t errors;
    if (config == NULL || descriptor == NULL || out == NULL ||
        !hal_complete(hal)) {
        return KB_SCANNER_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));
    if (config->switch_count > KB_CONFIG_MAX_KEYS ||
        !kb_config_validate(config, descriptor, &errors)) {
        return KB_SCANNER_INVALID_CONFIG;
    }
    out->config = *config;
    if (configure_inputs(config, hal) != KB_SCANNER_OK) {
        memset(out, 0, sizeof(*out));
        return KB_SCANNER_HAL_ERROR;
    }
    out->initialized = true;
    return KB_SCANNER_OK;
}

static int switch_at(const kb_scanner_t *scanner, uint8_t row, uint8_t col)
{
    uint16_t index;
    for (index = 0U; index < scanner->config.switch_count; ++index) {
        if (scanner->config.switches[index].row == row &&
            scanner->config.switches[index].col == col) {
            return (int)index;
        }
    }
    return -1;
}

static void debounce_sample(kb_scanner_t *scanner, uint16_t switch_id,
                            bool pressed, uint64_t now_ms,
                            kb_event_ring_t *events, size_t *produced)
{
    kb_scanner_switch_state_t *state = &scanner->switches[switch_id];
    const kb_switch_config_t *item = &scanner->config.switches[switch_id];
    kb_event_t event;

    if (pressed == state->stable_pressed) {
        state->candidate_pressed = pressed;
        state->candidate_since_ms = now_ms;
        return;
    }
    if (state->candidate_pressed != pressed ||
        now_ms < state->candidate_since_ms) {
        state->candidate_pressed = pressed;
        state->candidate_since_ms = now_ms;
        return;
    }
    if (now_ms - state->candidate_since_ms < scanner->config.debounce_ms) {
        return;
    }
    state->stable_pressed = pressed;
    event.type = pressed ? KB_EVENT_KEY_DOWN : KB_EVENT_KEY_UP;
    event.row = item->row;
    event.col = item->col;
    event.switch_id = switch_id;
    event.timestamp_ms = now_ms;
    (void)kb_events_push(events, &event);
    ++*produced;
}

kb_scanner_result_t kb_scanner_process(kb_scanner_t *scanner,
                                       const kb_hal_ops_t *hal,
                                       uint64_t now_ms,
                                       kb_event_ring_t *out_events,
                                       size_t *new_event_count)
{
    bool sampled[KB_CONFIG_MAX_KEYS] = {false};
    const bool drive_rows = scanner != NULL &&
                            scanner->config.pinmap.scan_mode ==
                                KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP;
    const uint8_t *drive_pins;
    const uint8_t *read_pins;
    uint8_t drive_count;
    uint8_t read_count;
    uint8_t drive;
    size_t produced = 0U;
    uint16_t index;

    if (new_event_count != NULL) {
        *new_event_count = 0U;
    }
    if (scanner == NULL || out_events == NULL || !hal_complete(hal)) {
        return KB_SCANNER_INVALID_ARGUMENT;
    }
    if (!scanner->initialized) {
        return KB_SCANNER_NOT_INITIALIZED;
    }
    drive_pins = drive_rows ? scanner->config.pinmap.row_pins
                            : scanner->config.pinmap.col_pins;
    read_pins = drive_rows ? scanner->config.pinmap.col_pins
                           : scanner->config.pinmap.row_pins;
    drive_count = drive_rows ? scanner->config.pinmap.row_pin_count
                             : scanner->config.pinmap.col_pin_count;
    read_count = drive_rows ? scanner->config.pinmap.col_pin_count
                            : scanner->config.pinmap.row_pin_count;

    for (drive = 0U; drive < drive_count; ++drive) {
        uint8_t read;
        if (hal->hal_pin_direction(hal->ctx, drive_pins[drive],
                                   KB_HAL_PIN_OUTPUT) != KB_HAL_OK ||
            hal->hal_pin_write(hal->ctx, drive_pins[drive], KB_HAL_PIN_LOW) !=
                KB_HAL_OK) {
            (void)hal->hal_pin_direction(hal->ctx, drive_pins[drive],
                                         KB_HAL_PIN_INPUT);
            return KB_SCANNER_HAL_ERROR;
        }
        for (read = 0U; read < read_count; ++read) {
            kb_hal_pin_value_t value;
            const uint8_t row = drive_rows ? drive : read;
            const uint8_t col = drive_rows ? read : drive;
            const int found = switch_at(scanner, row, col);
            if (hal->hal_pin_read(hal->ctx, read_pins[read], &value) != KB_HAL_OK) {
                (void)hal->hal_pin_direction(hal->ctx, drive_pins[drive],
                                             KB_HAL_PIN_INPUT);
                return KB_SCANNER_HAL_ERROR;
            }
            if (found >= 0) {
                sampled[(size_t)found] = value == KB_HAL_PIN_LOW;
            }
        }
        if (hal->hal_pin_direction(hal->ctx, drive_pins[drive],
                                   KB_HAL_PIN_INPUT) != KB_HAL_OK) {
            return KB_SCANNER_HAL_ERROR;
        }
    }
    for (index = 0U; index < scanner->config.switch_count; ++index) {
        debounce_sample(scanner, index, sampled[index], now_ms, out_events,
                        &produced);
    }
    if (new_event_count != NULL) {
        *new_event_count = produced;
    }
    return KB_SCANNER_OK;
}
