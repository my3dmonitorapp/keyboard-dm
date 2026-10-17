#ifndef FAKE_HAL_H
#define FAKE_HAL_H

#include "kb_hal.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define FAKE_HAL_MAX_PINS 64U
#define FAKE_HAL_STORE_CAPACITY 8192U
#define FAKE_HAL_TRANSPORT_CAPACITY 4096U
#define FAKE_HAL_MAX_PIN_CALLS 16384U
#define FAKE_HAL_MAX_SWITCHES 256U

typedef struct {
    uint8_t pin_a;
    uint8_t pin_b;
    bool closed;
} fake_hal_switch_t;

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
    size_t next_store_write_partial_bytes;
    kb_hal_error_t next_store_erase_error;
    uint8_t console[FAKE_HAL_TRANSPORT_CAPACITY];
    size_t console_length;
    uint8_t ble_report[FAKE_HAL_TRANSPORT_CAPACITY];
    size_t ble_report_length;
    size_t ble_send_call_count;
    kb_hal_error_t next_console_error;
    kb_hal_error_t next_ble_error;
    uint8_t pin_write_calls[FAKE_HAL_MAX_PIN_CALLS];
    size_t pin_write_call_count;
    uint8_t pin_read_calls[FAKE_HAL_MAX_PIN_CALLS];
    size_t pin_read_call_count;
    fake_hal_switch_t switches[FAKE_HAL_MAX_SWITCHES];
    size_t switch_count;
} fake_hal_t;

void fake_hal_reset(fake_hal_t *fake);
kb_hal_ops_t fake_hal_ops(fake_hal_t *fake);
void fake_hal_advance(fake_hal_t *fake, uint64_t milliseconds);
void fake_hal_inject_time_jump(fake_hal_t *fake, int64_t milliseconds);
bool fake_hal_set_switch(fake_hal_t *fake, uint8_t pin_a, uint8_t pin_b,
                         bool closed);

#endif
