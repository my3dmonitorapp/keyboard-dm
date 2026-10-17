#include "kbdm_idf_hal.h"
#include "esp_log.h"
#include "kb_boot.h"
#include "board_pinmap.h"

_Static_assert(KBDM_BOARD_ROW_COUNT == 0 && KBDM_BOARD_COL_COUNT == 0,
               "unverified BSP must not contain GPIO assignments");

static const char *const tag = "kbdm";

void app_main(void)
{
    kb_hal_ops_t operations;
    kbdm_idf_hal_t *hal = NULL;
    kb_boot_t boot;
    kb_boot_result_t result;
    kbdm_family_console_init();
    if (kbdm_idf_hal_init(&hal, &operations) != KB_HAL_OK) {
        ESP_LOGE(tag, "HAL/NVS initialization failed; GPIO remains untouched");
        return;
    }
    result = kb_boot_start(&boot, kbdm_family_capabilities(), &operations);
    ESP_LOGI(tag, "%s boot state=%d result=%d", kbdm_family_name(),
             (int)boot.status.state, (int)result);
    if (kbdm_idf_ble_start(hal) != KB_HAL_OK)
        ESP_LOGW(tag, "BLE HID disabled or unavailable");
    /* No scanner or matrix task starts until a validated config exists. */
}
