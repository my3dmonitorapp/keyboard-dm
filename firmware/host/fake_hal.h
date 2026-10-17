#ifndef FAKE_HAL_H
#define FAKE_HAL_H

#include "kb_hal.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define FAKE_HAL_MAX_PINS 64U
#define FAKE_HAL_STORE_CAPACITY 8192U
#define FAKE_HAL_TRANSPORT_CAPACITY 4096U

typedef struct {
    kb_hal_pin_direction_t pin_directions[FAKE_HAL_MAX_PINS];
    kb_hal_pin_value_t pin_values[FAKE_HAL_MAX_PINS];
    bool pin_pulldowns[FAKE_HAL_MAX_PINS];
    bool corrupt_pin_reads;
    uint64_t now_ms;
    int64_t next_time_jump_ms;
    uint8_t stores[KB_HAL_STORE_SLOT_COUNT][FAKE_HAL_STORE_CAPACITY];
    size_t store_lengths[KB_HAL_STORE_SLOT_COUNT];
    kb_hal_error_t next_store_read_error;
    kb_hal_error_t next_store_write_error;
    kb_hal_error_t next_store_erase_error;
    uint8_t console[FAKE_HAL_TRANSPORT_CAPACITY];
    size_t console_length;
    uint8_t ble_report[FAKE_HAL_TRANSPORT_CAPACITY];
    size_t ble_report_length;
    kb_hal_error_t next_console_error;
    kb_hal_error_t next_ble_error;
} fake_hal_t;

void fake_hal_reset(fake_hal_t *fake);
kb_hal_ops_t fake_hal_ops(fake_hal_t *fake);
void fake_hal_advance(fake_hal_t *fake, uint64_t milliseconds);
void fake_hal_inject_time_jump(fake_hal_t *fake, int64_t milliseconds);

#endif
