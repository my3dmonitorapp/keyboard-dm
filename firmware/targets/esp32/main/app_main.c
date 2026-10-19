#include "kbdm_idf_hal.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "kb_boot.h"
#include "kb_runtime.h"
#include "sdkconfig.h"
#include "board_pinmap.h"

#include <stdlib.h>

_Static_assert(KBDM_BOARD_ROW_COUNT == 0 && KBDM_BOARD_COL_COUNT == 0,
               "unverified BSP must not contain GPIO assignments");

static const char *const tag = "kbdm";
static kb_hal_ops_t runtime_operations;
static kbdm_idf_hal_t *runtime_hal;
static kb_boot_t runtime_boot;
static kb_runtime_t *runtime;

static kb_hal_error_t runtime_hid_report(void *context, const void *report,
                                         size_t length)
{
    return kbdm_idf_hid_report(context, report, length);
}

static void runtime_task(void *argument)
{
    uint8_t input[256];
    const TickType_t delay = pdMS_TO_TICKS(CONFIG_KBDM_SCAN_PERIOD_MS) == 0
                                 ? 1
                                 : pdMS_TO_TICKS(CONFIG_KBDM_SCAN_PERIOD_MS);
    (void)argument;
    for (;;) {
        size_t input_length = 0U;
        uint64_t now_ms = 0U;
        if (kbdm_idf_console_read(runtime_hal, input, sizeof(input),
                                  &input_length) != KB_HAL_OK) {
            ESP_LOGW(tag, "console read failed");
            input_length = 0U;
        }
        if (runtime_operations.hal_now_ms(runtime_operations.ctx, &now_ms) ==
                KB_HAL_OK &&
            kb_runtime_poll(runtime, now_ms, input, input_length, NULL) !=
                KB_RUNTIME_OK) {
            ESP_LOGW(tag, "runtime poll reported an error");
        }
        vTaskDelay(delay);
    }
}

void app_main(void)
{
    kb_boot_result_t result;
    kbdm_family_console_init();
    if (kbdm_idf_hal_init(&runtime_hal, &runtime_operations) != KB_HAL_OK) {
        ESP_LOGE(tag, "HAL/NVS initialization failed; GPIO remains untouched");
        return;
    }
    result = kb_boot_start(&runtime_boot, kbdm_family_capabilities(),
                           &runtime_operations);
    ESP_LOGI(tag, "%s boot state=%d result=%d", kbdm_family_name(),
             (int)runtime_boot.status.state, (int)result);
    if (kbdm_idf_ble_start(runtime_hal) != KB_HAL_OK)
        ESP_LOGW(tag, "BLE HID disabled or unavailable");
    runtime_operations.hal_ble_send_report = runtime_hid_report;
    runtime = malloc(sizeof(*runtime));
    if (runtime == NULL) {
        ESP_LOGE(tag, "runtime allocation failed; HAL/BLE remain available");
        return;
    }
    if (kb_runtime_init(runtime, &runtime_boot, &runtime_operations,
                        CONFIG_KBDM_SCAN_PERIOD_MS) != KB_RUNTIME_OK) {
        ESP_LOGE(tag, "runtime initialization failed; HAL/BLE remain available");
        free(runtime);
        runtime = NULL;
        return;
    }
    if (xTaskCreate(runtime_task, "kbdm_runtime", CONFIG_KBDM_RUNTIME_TASK_STACK,
                    NULL, CONFIG_KBDM_RUNTIME_TASK_PRIORITY, NULL) != pdPASS) {
        ESP_LOGE(tag, "runtime task creation failed; HAL/BLE remain available");
        free(runtime);
        runtime = NULL;
    }
}
