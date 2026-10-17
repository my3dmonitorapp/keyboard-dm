#ifndef KB_BOOT_H
#define KB_BOOT_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    KB_BOOT_NO_CONFIG = 0,
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

#endif
