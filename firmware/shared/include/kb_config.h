#ifndef KB_CONFIG_H
#define KB_CONFIG_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KB_CONFIG_PROTOCOL_VERSION 1U
#define KB_CONFIG_SCHEMA_VERSION 1U
#define KB_CONFIG_MAX_ROWS 16U
#define KB_CONFIG_MAX_COLS 16U
#define KB_CONFIG_MAX_KEYS 256U
#define KB_CONFIG_MAX_ERRORS 32U
#define KB_CONFIG_MAX_RESERVED_PINS 32U
#define KB_CONFIG_MAX_INPUT_ONLY_PINS 32U
#define KB_CONFIG_MAX_EXTERNAL_PULLUP_PINS 32U
#define KB_CONFIG_MAX_SHORTCUT_MODIFIERS 4U
#define KB_CONFIG_KEY_NAME_MAX 24U
#define KB_CONFIG_CHIP_CLASS_MAX 16U
#define KB_CONFIG_PROJECT_NAME_MAX 64U
#define KB_CONFIG_UPDATED_MAX 40U

typedef enum {
    KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP = 0,
    KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP
} kb_scan_mode_t;

typedef enum {
    KB_PULL_UP_INTERNAL = 0,
    KB_PULL_UP_EXTERNAL
} kb_pull_up_source_t;

typedef enum {
    KB_DIODE_COL_TO_ROW = 0,
    KB_DIODE_ROW_TO_COL
} kb_diode_direction_t;

typedef enum {
    KB_DIODE_SCOPE_BOARD = 0,
    KB_DIODE_SCOPE_PER_SWITCH
} kb_diode_scope_t;

typedef enum {
    KB_ACTION_NONE = 0,
    KB_ACTION_KEY,
    KB_ACTION_SHORTCUT,
    KB_ACTION_MEDIA,
    KB_ACTION_MODIFIER
} kb_action_type_t;

typedef enum {
    KB_MODIFIER_DOWN = 0,
    KB_MODIFIER_UP
} kb_modifier_event_t;

typedef struct {
    kb_action_type_t type;
    char key_name[KB_CONFIG_KEY_NAME_MAX];
    uint16_t usage_id;
    uint8_t modifier_count;
    uint8_t modifier_bits[KB_CONFIG_MAX_SHORTCUT_MODIFIERS];
    uint8_t modifier_bit;
    kb_modifier_event_t modifier_event;
} kb_action_t;

typedef struct {
    uint8_t row;
    uint8_t col;
    kb_diode_direction_t diode_direction;
    kb_action_t action;
} kb_switch_config_t;

typedef struct {
    uint8_t rows;
    uint8_t cols;
} kb_matrix_config_t;

typedef struct {
    uint8_t row_pin_count;
    uint8_t col_pin_count;
    uint8_t row_pins[KB_CONFIG_MAX_ROWS];
    uint8_t col_pins[KB_CONFIG_MAX_COLS];
    kb_scan_mode_t scan_mode;
    kb_pull_up_source_t pull_up_source;
} kb_pinmap_config_t;

typedef struct {
    char project_name[KB_CONFIG_PROJECT_NAME_MAX];
    char updated[KB_CONFIG_UPDATED_MAX];
    uint16_t project_version;
    uint16_t profile_version;
    uint16_t matrix_schema_version;
} kb_config_meta_t;

typedef struct {
    uint16_t protocol_version;
    uint16_t config_schema_version;
    char chip_class[KB_CONFIG_CHIP_CLASS_MAX];
    kb_matrix_config_t matrix;
    kb_pinmap_config_t pinmap;
    kb_diode_scope_t diode_scope;
    kb_diode_direction_t board_diode_direction;
    uint16_t switch_count;
    kb_switch_config_t switches[KB_CONFIG_MAX_KEYS];
    kb_config_meta_t meta;
    uint32_t generation;
    uint32_t crc32;
} kb_config_t;

/* Platform/board capability supplied to chip-family-agnostic validation. */
typedef struct {
    uint8_t pin_count;
    uint8_t reserved_pin_count;
    uint8_t reserved_pins[KB_CONFIG_MAX_RESERVED_PINS];
    uint8_t input_only_pin_count;
    uint8_t input_only_pins[KB_CONFIG_MAX_INPUT_ONLY_PINS];
    uint8_t external_pullup_pin_count;
    uint8_t external_pullup_pins[KB_CONFIG_MAX_EXTERNAL_PULLUP_PINS];
} kb_hal_probe_t;

typedef enum {
    KB_CONFIG_ERROR_BAD_PROTOCOL_VERSION = 0,
    KB_CONFIG_ERROR_BAD_SCHEMA_VERSION,
    KB_CONFIG_ERROR_MATRIX_ROWS,
    KB_CONFIG_ERROR_MATRIX_COLS,
    KB_CONFIG_ERROR_ROW_PIN_COUNT,
    KB_CONFIG_ERROR_COL_PIN_COUNT,
    KB_CONFIG_ERROR_PIN_RANGE,
    KB_CONFIG_ERROR_DUPLICATE_PIN,
    KB_CONFIG_ERROR_RESERVED_PIN,
    KB_CONFIG_ERROR_INPUT_ONLY_OUTPUT_PIN,
    KB_CONFIG_ERROR_EXTERNAL_PULLUP_REQUIRED,
    KB_CONFIG_ERROR_POPULATED_OUT_OF_RANGE,
    KB_CONFIG_ERROR_DUPLICATE_SWITCH,
    KB_CONFIG_ERROR_SCAN_DIODE_MISMATCH,
    KB_CONFIG_ERROR_ACTION_TYPE,
    KB_CONFIG_ERROR_HID_USAGE,
    KB_CONFIG_ERROR_SHORTCUT_MODIFIERS,
    KB_CONFIG_ERROR_CRC_MISMATCH
} kb_config_error_code_t;

typedef struct {
    kb_config_error_code_t code;
    char field[48];
    int16_t index;
    int16_t related_index;
} kb_config_error_t;

typedef struct {
    size_t count;
    size_t dropped;
    kb_config_error_t items[KB_CONFIG_MAX_ERRORS];
} kb_config_error_list_t;

typedef enum {
    KB_CONFIG_PARSE_OK = 0,
    KB_CONFIG_PARSE_INVALID_ARGUMENT,
    KB_CONFIG_PARSE_NO_MEMORY,
    KB_CONFIG_PARSE_JSON_SYNTAX,
    KB_CONFIG_PARSE_TOO_COMPLEX,
    KB_CONFIG_PARSE_MISSING_FIELD,
    KB_CONFIG_PARSE_UNKNOWN_FIELD,
    KB_CONFIG_PARSE_WRONG_TYPE,
    KB_CONFIG_PARSE_VALUE_RANGE,
    KB_CONFIG_PARSE_UNKNOWN_ACTION,
    KB_CONFIG_PARSE_BUFFER_TOO_SMALL
} kb_config_parse_code_t;

void kb_config_init(kb_config_t *config);
void kb_config_errors_reset(kb_config_error_list_t *errors);
bool kb_config_validate(const kb_config_t *config, const kb_hal_probe_t *probe,
                        kb_config_error_list_t *errors);

/*
 * Canonical JSON is compact and deterministically ordered. crc32 covers the
 * canonical object with the crc32 member omitted. to_json includes crc32.
 */
kb_config_parse_code_t kb_config_to_json(const kb_config_t *config, char *output,
                                         size_t capacity, size_t *length);
kb_config_parse_code_t kb_config_from_json(const char *json, size_t length,
                                           kb_config_t *output);
kb_config_parse_code_t kb_config_calculate_crc32(const kb_config_t *config,
                                                 uint32_t *crc32);
kb_config_parse_code_t kb_config_finalize_crc32(kb_config_t *config);

#endif
