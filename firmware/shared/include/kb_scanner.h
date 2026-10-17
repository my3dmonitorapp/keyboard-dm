#ifndef KB_SCANNER_H
#define KB_SCANNER_H

#include "kb_config.h"
#include "kb_events.h"
#include "kb_hal.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KB_SCANNER_DEFAULT_DEBOUNCE_MS KB_CONFIG_DEFAULT_DEBOUNCE_MS
#define KB_SCANNER_MIN_DEBOUNCE_MS KB_CONFIG_MIN_DEBOUNCE_MS
#define KB_SCANNER_MAX_DEBOUNCE_MS KB_CONFIG_MAX_DEBOUNCE_MS

typedef enum {
    KB_SCANNER_OK = 0,
    KB_SCANNER_INVALID_ARGUMENT,
    KB_SCANNER_INVALID_CONFIG,
    KB_SCANNER_HAL_ERROR,
    KB_SCANNER_NOT_INITIALIZED
} kb_scanner_result_t;

typedef struct {
    bool stable_pressed;
    bool candidate_pressed;
    uint64_t candidate_since_ms;
} kb_scanner_switch_state_t;

typedef struct {
    kb_config_t config;
    kb_scanner_switch_state_t switches[KB_CONFIG_MAX_KEYS];
    bool initialized;
} kb_scanner_t;

kb_scanner_result_t kb_scanner_init(const kb_config_t *config,
                                    const kb_hal_probe_t *descriptor,
                                    const kb_hal_ops_t *hal,
                                    kb_scanner_t *out);
kb_scanner_result_t kb_scanner_process(kb_scanner_t *scanner,
                                       const kb_hal_ops_t *hal,
                                       uint64_t now_ms,
                                       kb_event_ring_t *out_events,
                                       size_t *new_event_count);

#endif
