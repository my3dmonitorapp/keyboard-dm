#include "kbdm_idf_hal.h"

#define KBDM_FAMILY_NAME "esp32c3"

/* Board restrictions. GPIO11 has no header pad; GPIO18/19 preserve USB. */
static const kb_hal_probe_t capabilities = {
    .board = KBDM_FAMILY_NAME,
    .pin_count = 22,
    .reserved_pin_count = 12,
    .reserved_pins = {2, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19},
    .input_only_pin_count = 0,
    .external_pullup_pin_count = 0,
};

const kb_hal_probe_t *kbdm_family_capabilities(void) { return &capabilities; }
const char *kbdm_family_name(void) { return KBDM_FAMILY_NAME; }
void kbdm_family_console_init(void)
{
    /* CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG selects fixed-function USB CDC. */
}
