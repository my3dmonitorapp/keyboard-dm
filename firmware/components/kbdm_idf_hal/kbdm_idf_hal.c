#include "kbdm_idf_hal.h"

#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_err.h"
#include "esp_gap_ble_api.h"
#include "esp_gatt_common_api.h"
#include "esp_gatts_api.h"
#include "esp_timer.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#define KBDM_NVS_NAMESPACE "kbd_dm"
#define KBDM_HID_APP_ID 0x4b44
#define KBDM_INVALID_CONN_ID UINT16_MAX

enum { HID_SERVICE, HID_INFO, HID_INFO_VALUE, HID_REPORT_MAP,
       HID_REPORT_MAP_VALUE, HID_PROTOCOL_MODE, HID_PROTOCOL_MODE_VALUE,
       HID_CONTROL_POINT, HID_CONTROL_POINT_VALUE,
       HID_KEYBOARD, HID_KEYBOARD_VALUE, HID_KEYBOARD_CCCD, HID_KEYBOARD_REF,
       HID_CONSUMER, HID_CONSUMER_VALUE, HID_CONSUMER_CCCD, HID_CONSUMER_REF,
       HID_ATTRIBUTE_COUNT };

struct kbdm_idf_hal {
    nvs_handle_t nvs;
    int active_drive_pin;
    bool ledc_ready;
    bool ble_connected;
    esp_gatt_if_t gatts_if;
    uint16_t conn_id;
    uint16_t handles[HID_ATTRIBUTE_COUNT];
};

static struct kbdm_idf_hal state;
static const char *const slot_keys[KB_HAL_STORE_SLOT_COUNT] = {
    "cfg_a", "cfg_b", "metadata"
};

static const uint16_t primary_service_uuid = ESP_GATT_UUID_PRI_SERVICE;
static const uint16_t hid_service_uuid = ESP_GATT_UUID_HID_SVC;
static const uint16_t char_decl_uuid = ESP_GATT_UUID_CHAR_DECLARE;
static const uint16_t report_uuid = ESP_GATT_UUID_HID_REPORT;
static const uint16_t cccd_uuid = ESP_GATT_UUID_CHAR_CLIENT_CONFIG;
static const uint16_t report_ref_uuid = ESP_GATT_UUID_RPT_REF_DESCR;
static const uint16_t hid_info_uuid = ESP_GATT_UUID_HID_INFORMATION;
static const uint16_t report_map_uuid = ESP_GATT_UUID_HID_REPORT_MAP;
static const uint16_t protocol_mode_uuid = ESP_GATT_UUID_HID_PROTO_MODE;
static const uint16_t control_point_uuid = ESP_GATT_UUID_HID_CONTROL_POINT;
static const uint8_t char_props = ESP_GATT_CHAR_PROP_BIT_READ |
                                  ESP_GATT_CHAR_PROP_BIT_NOTIFY;
static const uint8_t read_props = ESP_GATT_CHAR_PROP_BIT_READ;
static const uint8_t read_write_props = ESP_GATT_CHAR_PROP_BIT_READ |
                                        ESP_GATT_CHAR_PROP_BIT_WRITE;
static const uint8_t write_props = ESP_GATT_CHAR_PROP_BIT_WRITE_NR;
static const uint8_t hid_info_value[] = {0x11, 0x01, 0x00, 0x02};
static const uint8_t hid_report_map[] = {
    0x05,0x01,0x09,0x06,0xa1,0x01,0x85,0x01,0x05,0x07,0x19,0xe0,0x29,0xe7,
    0x15,0x00,0x25,0x01,0x75,0x01,0x95,0x08,0x81,0x02,0x95,0x01,0x75,0x08,
    0x81,0x01,0x95,0x06,0x75,0x08,0x15,0x00,0x26,0xff,0x00,0x19,0x00,0x2a,
    0xff,0x00,0x81,0x00,0xc0,
    0x05,0x0c,0x09,0x01,0xa1,0x01,0x85,0x02,0x15,0x00,0x26,0xff,0x03,0x19,
    0x00,0x2a,0xff,0x03,0x75,0x10,0x95,0x04,0x81,0x00,0xc0
};
static uint8_t protocol_mode_value = 1;
static uint8_t control_point_value;
static uint8_t keyboard_ref[] = {1, 1};
static uint8_t consumer_ref[] = {2, 1};
static uint8_t keyboard_value[8];
static uint8_t consumer_value[8];
static uint8_t cccd_value[2];

static const esp_gatts_attr_db_t hid_db[HID_ATTRIBUTE_COUNT] = {
    [HID_SERVICE] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&primary_service_uuid, ESP_GATT_PERM_READ,
        sizeof(hid_service_uuid), sizeof(hid_service_uuid),
        (uint8_t *)&hid_service_uuid}},
    [HID_INFO] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&char_decl_uuid, ESP_GATT_PERM_READ,
        sizeof(read_props), sizeof(read_props), (uint8_t *)&read_props}},
    [HID_INFO_VALUE] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&hid_info_uuid, ESP_GATT_PERM_READ, sizeof(hid_info_value),
        sizeof(hid_info_value), (uint8_t *)hid_info_value}},
    [HID_REPORT_MAP] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&char_decl_uuid, ESP_GATT_PERM_READ,
        sizeof(read_props), sizeof(read_props), (uint8_t *)&read_props}},
    [HID_REPORT_MAP_VALUE] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&report_map_uuid, ESP_GATT_PERM_READ, sizeof(hid_report_map),
        sizeof(hid_report_map), (uint8_t *)hid_report_map}},
    [HID_PROTOCOL_MODE] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&char_decl_uuid, ESP_GATT_PERM_READ,
        sizeof(read_write_props), sizeof(read_write_props),
        (uint8_t *)&read_write_props}},
    [HID_PROTOCOL_MODE_VALUE] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&protocol_mode_uuid, ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
        sizeof(protocol_mode_value), sizeof(protocol_mode_value),
        &protocol_mode_value}},
    [HID_CONTROL_POINT] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&char_decl_uuid, ESP_GATT_PERM_READ,
        sizeof(write_props), sizeof(write_props), (uint8_t *)&write_props}},
    [HID_CONTROL_POINT_VALUE] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&control_point_uuid, ESP_GATT_PERM_WRITE,
        sizeof(control_point_value), sizeof(control_point_value),
        &control_point_value}},
    [HID_KEYBOARD] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&char_decl_uuid, ESP_GATT_PERM_READ,
        sizeof(char_props), sizeof(char_props), (uint8_t *)&char_props}},
    [HID_KEYBOARD_VALUE] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&report_uuid, ESP_GATT_PERM_READ, sizeof(keyboard_value),
        sizeof(keyboard_value), keyboard_value}},
    [HID_KEYBOARD_CCCD] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&cccd_uuid, ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
        sizeof(cccd_value), sizeof(cccd_value), cccd_value}},
    [HID_KEYBOARD_REF] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&report_ref_uuid, ESP_GATT_PERM_READ,
        sizeof(keyboard_ref), sizeof(keyboard_ref), keyboard_ref}},
    [HID_CONSUMER] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&char_decl_uuid, ESP_GATT_PERM_READ,
        sizeof(char_props), sizeof(char_props), (uint8_t *)&char_props}},
    [HID_CONSUMER_VALUE] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&report_uuid, ESP_GATT_PERM_READ, sizeof(consumer_value),
        sizeof(consumer_value), consumer_value}},
    [HID_CONSUMER_CCCD] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&cccd_uuid, ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
        sizeof(cccd_value), sizeof(cccd_value), cccd_value}},
    [HID_CONSUMER_REF] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16,
        (uint8_t *)&report_ref_uuid, ESP_GATT_PERM_READ,
        sizeof(consumer_ref), sizeof(consumer_ref), consumer_ref}},
};

static esp_ble_adv_params_t adv_params = {
    .adv_int_min = 0x20, .adv_int_max = 0x40,
    .adv_type = ADV_TYPE_IND, .own_addr_type = BLE_ADDR_TYPE_PUBLIC,
    .channel_map = ADV_CHNL_ALL, .adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY
};
static esp_ble_adv_data_t adv_data = {
    .set_scan_rsp = false, .include_name = true, .include_txpower = true,
    .min_interval = 0x0006, .max_interval = 0x0010,
    .appearance = ESP_BLE_APPEARANCE_HID_KEYBOARD,
    .manufacturer_len = 0, .p_manufacturer_data = NULL,
    .service_data_len = 0, .p_service_data = NULL,
    .service_uuid_len = 0, .p_service_uuid = NULL,
    .flag = ESP_BLE_ADV_FLAG_GEN_DISC | ESP_BLE_ADV_FLAG_BREDR_NOT_SPT
};

static kb_hal_error_t from_esp(esp_err_t error)
{
    if (error == ESP_OK) return KB_HAL_OK;
    if (error == ESP_ERR_INVALID_ARG) return KB_HAL_ERR_INVALID_ARGUMENT;
    if (error == ESP_ERR_NVS_NOT_FOUND) return KB_HAL_ERR_NOT_FOUND;
    if (error == ESP_ERR_NVS_NOT_ENOUGH_SPACE || error == ESP_ERR_NO_MEM)
        return KB_HAL_ERR_NO_SPACE;
    return KB_HAL_ERR_IO;
}

static kb_hal_error_t pin_direction(void *opaque, uint8_t pin,
                                    kb_hal_pin_direction_t direction)
{
    struct kbdm_idf_hal *hal = opaque;
    if (!GPIO_IS_VALID_GPIO(pin)) return KB_HAL_ERR_INVALID_ARGUMENT;
    if (direction == KB_HAL_PIN_INPUT) {
        if (hal->active_drive_pin == pin) {
            (void)ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0);
            hal->active_drive_pin = -1;
        }
        return from_esp(gpio_set_direction(pin, GPIO_MODE_INPUT));
    }
    if (!GPIO_IS_VALID_OUTPUT_GPIO(pin)) return KB_HAL_ERR_UNSUPPORTED;
    if (!hal->ledc_ready) {
        ledc_timer_config_t timer = {
            .speed_mode = LEDC_LOW_SPEED_MODE, .duty_resolution = LEDC_TIMER_1_BIT,
            .timer_num = LEDC_TIMER_0, .freq_hz = 100000,
            .clk_cfg = LEDC_AUTO_CLK
        };
        if (ledc_timer_config(&timer) != ESP_OK) return KB_HAL_ERR_IO;
        hal->ledc_ready = true;
    }
    {
        ledc_channel_config_t channel = {
            .gpio_num = pin, .speed_mode = LEDC_LOW_SPEED_MODE,
            .channel = LEDC_CHANNEL_0, .intr_type = LEDC_INTR_DISABLE,
            .timer_sel = LEDC_TIMER_0, .duty = 0, .hpoint = 0
        };
        if (ledc_channel_config(&channel) != ESP_OK) return KB_HAL_ERR_IO;
    }
    hal->active_drive_pin = pin;
    return KB_HAL_OK;
}

static kb_hal_error_t pin_write(void *opaque, uint8_t pin,
                                kb_hal_pin_value_t value)
{
    struct kbdm_idf_hal *hal = opaque;
    if (hal->active_drive_pin != pin) return KB_HAL_ERR_BUSY;
    if (ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0,
                      value == KB_HAL_PIN_HIGH ? 1 : 0) != ESP_OK ||
        ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0) != ESP_OK)
        return KB_HAL_ERR_IO;
    return KB_HAL_OK;
}

static kb_hal_error_t pin_read(void *opaque, uint8_t pin,
                               kb_hal_pin_value_t *value)
{
    (void)opaque;
    if (value == NULL || !GPIO_IS_VALID_GPIO(pin))
        return KB_HAL_ERR_INVALID_ARGUMENT;
    *value = gpio_get_level(pin) ? KB_HAL_PIN_HIGH : KB_HAL_PIN_LOW;
    return KB_HAL_OK;
}

static kb_hal_error_t pin_pulldown(void *opaque, uint8_t pin, bool enabled)
{
    (void)opaque;
    if (!GPIO_IS_VALID_GPIO(pin)) return KB_HAL_ERR_INVALID_ARGUMENT;
    /* The core passes false for its active-low read side: select pull-up. */
    return from_esp(gpio_set_pull_mode(pin, enabled ? GPIO_PULLDOWN_ONLY
                                                    : GPIO_PULLUP_ONLY));
}

static kb_hal_error_t now_ms(void *opaque, uint64_t *value)
{
    (void)opaque;
    if (value == NULL) return KB_HAL_ERR_INVALID_ARGUMENT;
    *value = (uint64_t)esp_timer_get_time() / 1000U;
    return KB_HAL_OK;
}

static kb_hal_error_t store_read(void *opaque, kb_hal_store_slot_t slot,
                                 void *buffer, size_t capacity, size_t *length)
{
    struct kbdm_idf_hal *hal = opaque;
    size_t needed = capacity;
    esp_err_t error;
    if (slot >= KB_HAL_STORE_SLOT_COUNT || buffer == NULL || length == NULL)
        return KB_HAL_ERR_INVALID_ARGUMENT;
    error = nvs_get_blob(hal->nvs, slot_keys[slot], buffer, &needed);
    *length = needed;
    return from_esp(error);
}

static kb_hal_error_t store_write(void *opaque, kb_hal_store_slot_t slot,
                                  const void *buffer, size_t length)
{
    struct kbdm_idf_hal *hal = opaque;
    esp_err_t error;
    if (slot >= KB_HAL_STORE_SLOT_COUNT || buffer == NULL)
        return KB_HAL_ERR_INVALID_ARGUMENT;
    error = nvs_set_blob(hal->nvs, slot_keys[slot], buffer, length);
    if (error == ESP_OK) error = nvs_commit(hal->nvs);
    return from_esp(error);
}

static kb_hal_error_t store_erase(void *opaque, kb_hal_store_slot_t slot)
{
    struct kbdm_idf_hal *hal = opaque;
    esp_err_t error;
    if (slot >= KB_HAL_STORE_SLOT_COUNT) return KB_HAL_ERR_INVALID_ARGUMENT;
    error = nvs_erase_key(hal->nvs, slot_keys[slot]);
    if (error == ESP_OK || error == ESP_ERR_NVS_NOT_FOUND)
        error = nvs_commit(hal->nvs);
    return from_esp(error);
}

static kb_hal_error_t console_send(void *opaque, const void *buffer, size_t length)
{
    (void)opaque;
    if (buffer == NULL) return KB_HAL_ERR_INVALID_ARGUMENT;
    return fwrite(buffer, 1, length, stdout) == length ? KB_HAL_OK : KB_HAL_ERR_IO;
}

static kb_hal_error_t ble_send(void *opaque, const void *buffer, size_t length)
{
    struct kbdm_idf_hal *hal = opaque;
    const uint8_t *report = buffer;
    uint8_t consumer[8] = {0};
    size_t index;
    if (buffer == NULL || length != 32) return KB_HAL_ERR_INVALID_ARGUMENT;
    if (!hal->ble_connected) return KB_HAL_ERR_BUSY;
    if (esp_ble_gatts_send_indicate(hal->gatts_if, hal->conn_id,
            hal->handles[HID_KEYBOARD_VALUE], 8, (uint8_t *)report, false) != ESP_OK)
        return KB_HAL_ERR_IO;
    for (index = 0; index < 4; ++index) {
        consumer[index * 2] = report[8 + index * 4 + 2];
        consumer[index * 2 + 1] = report[8 + index * 4 + 3];
    }
    return from_esp(esp_ble_gatts_send_indicate(hal->gatts_if, hal->conn_id,
        hal->handles[HID_CONSUMER_VALUE], sizeof(consumer), consumer, false));
}

static void gap_callback(esp_gap_ble_cb_event_t event,
                         esp_ble_gap_cb_param_t *parameter)
{
    (void)parameter;
    if (event == ESP_GAP_BLE_ADV_DATA_SET_COMPLETE_EVT)
        (void)esp_ble_gap_start_advertising(&adv_params);
}

static void gatts_callback(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if,
                           esp_ble_gatts_cb_param_t *parameter)
{
    if (event == ESP_GATTS_REG_EVT) {
        state.gatts_if = gatts_if;
        (void)esp_ble_gap_set_device_name("Keyboard DM");
        (void)esp_ble_gap_config_adv_data(&adv_data);
        (void)esp_ble_gatts_create_attr_tab(hid_db, gatts_if,
                                            HID_ATTRIBUTE_COUNT, 0);
    } else if (event == ESP_GATTS_CREAT_ATTR_TAB_EVT &&
               parameter->add_attr_tab.status == ESP_GATT_OK) {
        memcpy(state.handles, parameter->add_attr_tab.handles,
               sizeof(state.handles));
        (void)esp_ble_gatts_start_service(state.handles[HID_SERVICE]);
    } else if (event == ESP_GATTS_CONNECT_EVT) {
        state.ble_connected = true;
        state.conn_id = parameter->connect.conn_id;
        state.gatts_if = gatts_if;
        (void)esp_ble_set_encryption(parameter->connect.remote_bda,
                                     ESP_BLE_SEC_ENCRYPT_NO_MITM);
    } else if (event == ESP_GATTS_DISCONNECT_EVT) {
        state.ble_connected = false;
        state.conn_id = KBDM_INVALID_CONN_ID;
        (void)esp_ble_gap_start_advertising(&adv_params);
    }
}

kb_hal_error_t kbdm_idf_ble_start(kbdm_idf_hal_t *context)
{
    esp_err_t error;
    if (context == NULL) return KB_HAL_ERR_INVALID_ARGUMENT;
#if !CONFIG_KBDM_BLE_ENABLED
    return KB_HAL_ERR_UNSUPPORTED;
#else
    (void)esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
    esp_bt_controller_config_t config = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    error = esp_bt_controller_init(&config);
    if (error == ESP_OK) error = esp_bt_controller_enable(ESP_BT_MODE_BLE);
    if (error == ESP_OK) error = esp_bluedroid_init();
    if (error == ESP_OK) error = esp_bluedroid_enable();
    if (error == ESP_OK) error = esp_ble_gap_register_callback(gap_callback);
    if (error == ESP_OK) error = esp_ble_gatts_register_callback(gatts_callback);
    if (error == ESP_OK) {
        esp_ble_auth_req_t auth = ESP_LE_AUTH_BOND;
        esp_ble_io_cap_t io = ESP_IO_CAP_NONE;
        uint8_t key_size = 16;
        uint8_t keys = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
        error = esp_ble_gap_set_security_param(ESP_BLE_SM_AUTHEN_REQ_MODE,
                                                &auth, sizeof(auth));
        if (error == ESP_OK)
            error = esp_ble_gap_set_security_param(ESP_BLE_SM_IOCAP_MODE,
                                                    &io, sizeof(io));
        if (error == ESP_OK)
            error = esp_ble_gap_set_security_param(ESP_BLE_SM_MAX_KEY_SIZE,
                                                    &key_size, sizeof(key_size));
        if (error == ESP_OK)
            error = esp_ble_gap_set_security_param(ESP_BLE_SM_SET_INIT_KEY,
                                                    &keys, sizeof(keys));
        if (error == ESP_OK)
            error = esp_ble_gap_set_security_param(ESP_BLE_SM_SET_RSP_KEY,
                                                    &keys, sizeof(keys));
    }
    if (error == ESP_OK) error = esp_ble_gatts_app_register(KBDM_HID_APP_ID);
    return from_esp(error);
#endif
}

kb_hal_error_t kbdm_idf_hal_init(kbdm_idf_hal_t **context,
                                 kb_hal_ops_t *operations)
{
    esp_err_t error;
    uint16_t stored_version = 0;
    if (context == NULL || operations == NULL) return KB_HAL_ERR_INVALID_ARGUMENT;
    memset(&state, 0, sizeof(state));
    state.active_drive_pin = -1;
    state.conn_id = KBDM_INVALID_CONN_ID;
    error = nvs_flash_init();
    if (error == ESP_OK) error = nvs_open(KBDM_NVS_NAMESPACE, NVS_READWRITE,
                                          &state.nvs);
    if (error != ESP_OK) return from_esp(error);
    error = nvs_get_u16(state.nvs, "version", &stored_version);
    if (error == ESP_ERR_NVS_NOT_FOUND) {
        error = nvs_set_u16(state.nvs, "version", CONFIG_KBDM_NVS_CONFIG_VERSION);
        if (error == ESP_OK) error = nvs_commit(state.nvs);
        if (error != ESP_OK) return from_esp(error);
    } else if (error != ESP_OK) {
        return from_esp(error);
    } else if (stored_version != CONFIG_KBDM_NVS_CONFIG_VERSION) {
        return KB_HAL_ERR_CORRUPT;
    }
    *operations = (kb_hal_ops_t){
        .ctx = &state, .hal_pin_direction = pin_direction,
        .hal_pin_write = pin_write, .hal_pin_read = pin_read,
        .hal_pin_input_pulldown_en = pin_pulldown, .hal_now_ms = now_ms,
        .hal_store_read = store_read, .hal_store_write = store_write,
        .hal_store_erase = store_erase, .hal_console_send = console_send,
        .hal_ble_send_report = ble_send
    };
    *context = &state;
    return KB_HAL_OK;
}
