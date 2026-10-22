#include "kbdm_idf_hal.h"
#include "driver/uart.h"
#include "sdkconfig.h"

#define KBDM_FAMILY_NAME "esp32"

/* Silicon/module restrictions, not a board wiring assignment.
 * GPIO0/2/5/12/15 are documented boot straps; GPIO6-11 connect to flash.
 * GPIO20/24/28-31 are unavailable, while GPIO34-39 are input-only and need
 * external pull-ups. GPIO16/17 are regular DevKit GPIOs, so they stay free.
 */
static const kb_hal_probe_t capabilities = {
    .board = KBDM_FAMILY_NAME,
    .pin_count = 40,
    .reserved_pin_count = 17,
    .reserved_pins = {0, 2, 5, 6, 7, 8, 9, 10, 11, 12, 15,
                      20, 24, 28, 29, 30, 31},
    .input_only_pin_count = 6,
    .input_only_pins = {34, 35, 36, 37, 38, 39},
    .external_pullup_pin_count = 6,
    .external_pullup_pins = {34, 35, 36, 37, 38, 39},
};

const kb_hal_probe_t *kbdm_family_capabilities(void) { return &capabilities; }
const char *kbdm_family_name(void) { return KBDM_FAMILY_NAME; }
void kbdm_family_console_init(void)
{
    (void)uart_set_baudrate(UART_NUM_0, CONFIG_KBDM_SERIAL_BAUD);
}
