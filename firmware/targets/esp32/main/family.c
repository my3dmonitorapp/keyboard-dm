#include "kbdm_idf_hal.h"
#include "driver/uart.h"
#include "sdkconfig.h"

/* Silicon/module restrictions, not a board wiring assignment. */
static const kb_hal_probe_t capabilities = {
    .pin_count = 40,
    .reserved_pin_count = 19,
    .reserved_pins = {0, 2, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16, 17,
                      20, 24, 28, 29, 30, 31},
    .input_only_pin_count = 6,
    .input_only_pins = {34, 35, 36, 37, 38, 39},
    .external_pullup_pin_count = 6,
    .external_pullup_pins = {34, 35, 36, 37, 38, 39},
};

const kb_hal_probe_t *kbdm_family_capabilities(void) { return &capabilities; }
const char *kbdm_family_name(void) { return "esp32"; }
void kbdm_family_console_init(void)
{
    (void)uart_set_baudrate(UART_NUM_0, CONFIG_KBDM_SERIAL_BAUD);
}
