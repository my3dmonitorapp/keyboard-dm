#ifndef KB_HID_H
#define KB_HID_H

#include "kb_actions.h"
#include "kb_hal.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KB_HID_BOOT_REPORT_BYTES 8U
#define KB_HID_BLE_REPORT_BYTES 32U
#define KB_HID_MAX_KEYS 6U
#define KB_HID_MAX_CONSUMER_USAGES 4U

typedef enum {
    KB_HID_OK = 0,
    KB_HID_NO_CHANGE,
    KB_HID_INVALID_ARGUMENT,
    KB_HID_UNSUPPORTED_ACTION,
    KB_HID_ROLLOVER,
    KB_HID_HAL_ERROR
} kb_hid_result_t;

typedef struct {
    uint8_t modifiers;
    uint8_t keys[KB_HID_MAX_KEYS];
    uint16_t consumer_usages[KB_HID_MAX_CONSUMER_USAGES];
    uint8_t consumer_count;
    uint8_t last_report[KB_HID_BLE_REPORT_BYTES];
    bool has_last_report;
} kb_hid_state_t;

void kb_hid_init(kb_hid_state_t *state);
kb_hid_result_t kb_hid_apply(kb_hid_state_t *state,
                             const kb_typed_action_t *action);
void kb_hid_build_boot_report(const kb_hid_state_t *state,
                              uint8_t report[KB_HID_BOOT_REPORT_BYTES]);
void kb_hid_build_ble_report(const kb_hid_state_t *state,
                             uint8_t report[KB_HID_BLE_REPORT_BYTES]);
kb_hid_result_t kb_hid_emit_if_changed(kb_hid_state_t *state,
                                       const kb_hal_ops_t *hal);
kb_hid_result_t kb_hid_apply_and_emit(kb_hid_state_t *state,
                                      const kb_hal_ops_t *hal,
                                      const kb_typed_action_t *action);

#endif
