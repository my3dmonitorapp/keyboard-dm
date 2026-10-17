#ifndef KB_HAL_H
#define KB_HAL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    KB_HAL_OK = 0,
    KB_HAL_ERR_INVALID_ARGUMENT,
    KB_HAL_ERR_UNSUPPORTED,
    KB_HAL_ERR_IO,
    KB_HAL_ERR_NOT_FOUND,
    KB_HAL_ERR_CORRUPT,
    KB_HAL_ERR_NO_SPACE,
    KB_HAL_ERR_BUSY
} kb_hal_error_t;

typedef enum {
    KB_HAL_PIN_INPUT = 0,
    KB_HAL_PIN_OUTPUT
} kb_hal_pin_direction_t;

typedef enum {
    KB_HAL_PIN_LOW = 0,
    KB_HAL_PIN_HIGH = 1
} kb_hal_pin_value_t;

typedef enum {
    KB_HAL_STORE_CONFIG_A = 0,
    KB_HAL_STORE_CONFIG_B,
    KB_HAL_STORE_METADATA,
    KB_HAL_STORE_SLOT_COUNT
} kb_hal_store_slot_t;

/*
 * The only platform boundary used by shared code. Implementations own ctx.
 * Reads and writes use in/out lengths so short data is never mistaken for a
 * complete record.
 */
typedef struct {
    void *ctx;
    kb_hal_error_t (*hal_pin_direction)(void *ctx, uint8_t pin,
                                        kb_hal_pin_direction_t direction);
    kb_hal_error_t (*hal_pin_write)(void *ctx, uint8_t pin,
                                    kb_hal_pin_value_t value);
    kb_hal_error_t (*hal_pin_read)(void *ctx, uint8_t pin,
                                   kb_hal_pin_value_t *value);
    kb_hal_error_t (*hal_pin_input_pulldown_en)(void *ctx, uint8_t pin,
                                                bool enabled);
    kb_hal_error_t (*hal_now_ms)(void *ctx, uint64_t *now_ms);
    kb_hal_error_t (*hal_store_read)(void *ctx, kb_hal_store_slot_t slot,
                                     void *buffer, size_t capacity,
                                     size_t *length);
    kb_hal_error_t (*hal_store_write)(void *ctx, kb_hal_store_slot_t slot,
                                      const void *buffer, size_t length);
    kb_hal_error_t (*hal_store_erase)(void *ctx, kb_hal_store_slot_t slot);
    kb_hal_error_t (*hal_console_send)(void *ctx, const void *buffer,
                                       size_t length);
    kb_hal_error_t (*hal_ble_send_report)(void *ctx, const void *report,
                                          size_t length);
} kb_hal_ops_t;

#endif
