#ifndef KBDM_IDF_HAL_H
#define KBDM_IDF_HAL_H

#include "kb_config.h"
#include "kb_hal.h"

typedef struct kbdm_idf_hal kbdm_idf_hal_t;

kb_hal_error_t kbdm_idf_hal_init(kbdm_idf_hal_t **context,
                                 kb_hal_ops_t *operations);
kb_hal_error_t kbdm_idf_ble_start(kbdm_idf_hal_t *context);

/* Implemented by the selected family component. */
const kb_hal_probe_t *kbdm_family_capabilities(void);
void kbdm_family_console_init(void);
const char *kbdm_family_name(void);

#endif
