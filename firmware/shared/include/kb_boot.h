#ifndef KB_BOOT_H
#define KB_BOOT_H

#include <stdbool.h>
#include <stdint.h>

#include "kb_config.h"
#include "kb_hal.h"

typedef enum {
    KB_BOOT_NO_CONFIG = 0,
    KB_BOOT_LOADING,
    KB_BOOT_VALID,
    KB_BOOT_RECOVERING,
    KB_BOOT_SAFE_MODE
} kb_boot_state_t;

/* State only. Startup transitions and storage recovery belong to F2-T3. */
typedef struct {
    kb_boot_state_t state;
    uint32_t active_generation;
    uint32_t last_good_generation;
    bool rollback_used;
    bool matrix_outputs_enabled;
    uint16_t validation_error_count;
} kb_boot_status_t;

typedef enum {
    KB_BOOT_REASON_NONE = 0,
    KB_BOOT_REASON_NO_CONFIG,
    KB_BOOT_REASON_BOTH_SLOTS_INVALID,
    KB_BOOT_REASON_ACTIVE_INVALID_ROLLBACK,
    KB_BOOT_REASON_STORAGE_ERROR
} kb_boot_reason_t;

typedef enum {
    KB_BOOT_OK = 0,
    KB_BOOT_NO_CHANGE,
    KB_BOOT_INVALID_ARGUMENT,
    KB_BOOT_INVALID_CONFIG,
    KB_BOOT_STORAGE_ERROR,
    KB_BOOT_NO_RECOVERY
} kb_boot_result_t;

typedef struct {
    kb_boot_status_t status;
    kb_boot_reason_t reason;
    kb_config_t active_config;
    kb_hal_probe_t descriptor;
    kb_hal_ops_t hal;
    kb_hal_store_slot_t active_slot;
    kb_hal_store_slot_t last_good_slot;
    bool has_active;
    bool has_last_good;
} kb_boot_t;

kb_boot_result_t kb_boot_start(kb_boot_t *boot,
                               const kb_hal_probe_t *descriptor,
                               const kb_hal_ops_t *hal);
kb_boot_result_t kb_boot_apply_config(kb_boot_t *boot,
                                      const kb_config_t *config);
/*
 * Roll back to the metadata-designated last-good generation. A successful
 * recovery consumes that pointer, so repeating recover() is a no-op rather
 * than swapping A/B back to a generation already left behind (ABA).
 */
kb_boot_result_t kb_boot_recover(kb_boot_t *boot);
const kb_config_t *kb_boot_active_config(const kb_boot_t *boot);

#endif
