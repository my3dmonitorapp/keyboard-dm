#include "kb_config.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef enum {
    JSON_UNDEFINED = 0,
    JSON_OBJECT,
    JSON_ARRAY,
    JSON_STRING,
    JSON_PRIMITIVE
} json_type_t;

typedef struct {
    json_type_t type;
    int start;
    int end;
    int size;
    int parent;
} json_token_t;

#define KB_JSON_MAX_TOKENS 4096U

typedef struct {
    const char *json;
    size_t length;
    json_token_t tokens[KB_JSON_MAX_TOKENS];
    size_t count;
} json_document_t;

typedef struct {
    char *buffer;
    size_t capacity;
    size_t length;
    bool failed;
    bool crc_enabled;
    uint32_t crc;
} json_writer_t;

typedef struct {
    const char *name;
    uint16_t usage;
} usage_name_t;

static const char *const modifier_names[8] = {
    "lctrl", "lshift", "lalt", "lsuper",
    "rctrl", "rshift", "ralt", "rsuper"
};

static const usage_name_t media_usages[] = {
    {"vol_up", UINT16_C(0x00e9)},
    {"vol_down", UINT16_C(0x00ea)},
    {"mute", UINT16_C(0x00e2)},
    {"play_pause", UINT16_C(0x00cd)},
    {"next_track", UINT16_C(0x00b0)},
    {"previous_track", UINT16_C(0x00b2)}
};

static const usage_name_t key_usages[] = {
    {"a", 0x04}, {"b", 0x05}, {"c", 0x06}, {"d", 0x07},
    {"e", 0x08}, {"f", 0x09}, {"g", 0x0a}, {"h", 0x0b},
    {"i", 0x0c}, {"j", 0x0d}, {"k", 0x0e}, {"l", 0x0f},
    {"m", 0x10}, {"n", 0x11}, {"o", 0x12}, {"p", 0x13},
    {"q", 0x14}, {"r", 0x15}, {"s", 0x16}, {"t", 0x17},
    {"u", 0x18}, {"v", 0x19}, {"w", 0x1a}, {"x", 0x1b},
    {"y", 0x1c}, {"z", 0x1d},
    {"1", 0x1e}, {"2", 0x1f}, {"3", 0x20}, {"4", 0x21},
    {"5", 0x22}, {"6", 0x23}, {"7", 0x24}, {"8", 0x25},
    {"9", 0x26}, {"0", 0x27},
    {"enter", 0x28}, {"escape", 0x29}, {"backspace", 0x2a},
    {"tab", 0x2b}, {"space", 0x2c}, {"minus", 0x2d},
    {"equal", 0x2e}, {"left_bracket", 0x2f},
    {"right_bracket", 0x30}, {"backslash", 0x31},
    {"non_us_hash", 0x32}, {"semicolon", 0x33},
    {"apostrophe", 0x34}, {"grave", 0x35}, {"comma", 0x36},
    {"period", 0x37}, {"slash", 0x38}, {"caps_lock", 0x39},
    {"f1", 0x3a}, {"f2", 0x3b}, {"f3", 0x3c}, {"f4", 0x3d},
    {"f5", 0x3e}, {"f6", 0x3f}, {"f7", 0x40}, {"f8", 0x41},
    {"f9", 0x42}, {"f10", 0x43}, {"f11", 0x44}, {"f12", 0x45},
    {"print", 0x46}, {"scroll_lock", 0x47}, {"pause", 0x48},
    {"insert", 0x49}, {"home", 0x4a}, {"page_up", 0x4b},
    {"delete", 0x4c}, {"end", 0x4d}, {"page_down", 0x4e},
    {"right", 0x4f}, {"left", 0x50}, {"down", 0x51}, {"up", 0x52},
    {"num_lock", 0x53}, {"keypad_divide", 0x54},
    {"keypad_multiply", 0x55}, {"keypad_subtract", 0x56},
    {"keypad_add", 0x57}, {"keypad_enter", 0x58},
    {"keypad_1", 0x59}, {"keypad_2", 0x5a}, {"keypad_3", 0x5b},
    {"keypad_4", 0x5c}, {"keypad_5", 0x5d}, {"keypad_6", 0x5e},
    {"keypad_7", 0x5f}, {"keypad_8", 0x60}, {"keypad_9", 0x61},
    {"keypad_0", 0x62}, {"keypad_decimal", 0x63},
    {"non_us_backslash", 0x64}, {"application", 0x65}, {"power", 0x66},
    {"keypad_equal", 0x67},
    {"f13", 0x68}, {"f14", 0x69}, {"f15", 0x6a}, {"f16", 0x6b},
    {"f17", 0x6c}, {"f18", 0x6d}, {"f19", 0x6e}, {"f20", 0x6f},
    {"f21", 0x70}, {"f22", 0x71}, {"f23", 0x72}, {"f24", 0x73},
    {"execute", 0x74}, {"help", 0x75}, {"menu", 0x76},
    {"select", 0x77}, {"stop", 0x78}, {"again", 0x79},
    {"undo", 0x7a}, {"cut", 0x7b}, {"copy", 0x7c},
    {"paste", 0x7d}, {"find", 0x7e}
};

static uint32_t crc_update(uint32_t crc, const unsigned char *data, size_t length)
{
    size_t index;

    for (index = 0U; index < length; ++index) {
        unsigned bit;
        crc ^= data[index];
        for (bit = 0U; bit < 8U; ++bit) {
            const uint32_t mask = (uint32_t)-(int32_t)(crc & UINT32_C(1));
            crc = (crc >> 1U) ^ (UINT32_C(0xedb88320) & mask);
        }
    }
    return crc;
}

static void writer_bytes(json_writer_t *writer, const char *bytes, size_t length)
{
    if (writer->failed) {
        return;
    }
    if (length > SIZE_MAX - writer->length ||
        (writer->buffer != NULL && writer->length + length >= writer->capacity)) {
        writer->failed = true;
        return;
    }
    if (writer->buffer != NULL) {
        memcpy(writer->buffer + writer->length, bytes, length);
    }
    if (writer->crc_enabled) {
        writer->crc = crc_update(writer->crc, (const unsigned char *)bytes, length);
    }
    writer->length += length;
}

static void writer_text(json_writer_t *writer, const char *text)
{
    writer_bytes(writer, text, strlen(text));
}

static void writer_uint(json_writer_t *writer, uint32_t value)
{
    char number[16];
    const int count = snprintf(number, sizeof(number), "%lu", (unsigned long)value);
    if (count < 0 || (size_t)count >= sizeof(number)) {
        writer->failed = true;
        return;
    }
    writer_bytes(writer, number, (size_t)count);
}

static void writer_string(json_writer_t *writer, const char *value)
{
    const unsigned char *cursor = (const unsigned char *)value;
    writer_text(writer, "\"");
    while (*cursor != 0U) {
        char escaped[7];
        if (*cursor == '"' || *cursor == '\\') {
            escaped[0] = '\\';
            escaped[1] = (char)*cursor;
            writer_bytes(writer, escaped, 2U);
        } else if (*cursor < 0x20U) {
            const int count = snprintf(escaped, sizeof(escaped), "\\u%04x", *cursor);
            if (count != 6) {
                writer->failed = true;
                return;
            }
            writer_bytes(writer, escaped, 6U);
        } else {
            writer_bytes(writer, (const char *)cursor, 1U);
        }
        ++cursor;
    }
    writer_text(writer, "\"");
}

static const char *scan_mode_name(kb_scan_mode_t mode)
{
    return mode == KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP
               ? "drive_cols_low_read_rows_pullup"
               : "drive_rows_low_read_cols_pullup";
}

static const char *diode_name(kb_diode_direction_t direction)
{
    return direction == KB_DIODE_ROW_TO_COL ? "row_to_col" : "col_to_row";
}

static const char *pullup_name(kb_pull_up_source_t source)
{
    return source == KB_PULL_UP_EXTERNAL ? "external" : "internal";
}

static void write_key_id(json_writer_t *writer, uint8_t row, uint8_t col)
{
    char key_id[16];
    const int count = snprintf(key_id, sizeof(key_id), "MX-%02u-%02u",
                               (unsigned)row, (unsigned)col);
    if (count < 0 || (size_t)count >= sizeof(key_id)) {
        writer->failed = true;
        return;
    }
    writer_string(writer, key_id);
}

static void write_action(json_writer_t *writer, const kb_action_t *action)
{
    size_t index;

    switch (action->type) {
    case KB_ACTION_NONE:
        writer_text(writer, "null");
        break;
    case KB_ACTION_KEY:
        writer_text(writer, "{\"type\":\"key\",\"key\":");
        writer_string(writer, action->key_name);
        writer_text(writer, "}");
        break;
    case KB_ACTION_SHORTCUT:
        writer_text(writer, "{\"type\":\"shortcut\",\"modifiers\":[");
        for (index = 0U; index < action->modifier_count &&
                         index < KB_CONFIG_MAX_SHORTCUT_MODIFIERS; ++index) {
            if (index != 0U) {
                writer_text(writer, ",");
            }
            if (action->modifier_bits[index] < 8U) {
                writer_string(writer, modifier_names[action->modifier_bits[index]]);
            } else {
                writer_string(writer, "invalid");
            }
        }
        writer_text(writer, "],\"key\":");
        writer_string(writer, action->key_name);
        writer_text(writer, "}");
        break;
    case KB_ACTION_MEDIA:
        writer_text(writer, "{\"type\":\"media\",\"key\":");
        writer_string(writer, action->key_name);
        writer_text(writer, "}");
        break;
    case KB_ACTION_MODIFIER:
        writer_text(writer, "{\"type\":\"modifier\",\"modifier\":");
        if (action->modifier_bit < 8U) {
            writer_string(writer, modifier_names[action->modifier_bit]);
        } else {
            writer_string(writer, "invalid");
        }
        writer_text(writer, ",\"event\":");
        writer_string(writer, action->modifier_event == KB_MODIFIER_UP ? "up" : "down");
        writer_text(writer, "}");
        break;
    default:
        writer_text(writer, "null");
        break;
    }
}

static void serialize_config(json_writer_t *writer, const kb_config_t *config,
                             bool include_crc)
{
    size_t index;
    size_t switch_count = config->switch_count;
    uint16_t order[KB_CONFIG_MAX_KEYS];

    if (switch_count > KB_CONFIG_MAX_KEYS) {
        switch_count = KB_CONFIG_MAX_KEYS;
    }
    for (index = 0U; index < switch_count; ++index) {
        size_t position = index;
        order[index] = (uint16_t)index;
        while (position > 0U) {
            const kb_switch_config_t *current = &config->switches[order[position]];
            const kb_switch_config_t *previous =
                &config->switches[order[position - 1U]];
            uint16_t temporary;
            if (previous->row < current->row ||
                (previous->row == current->row && previous->col <= current->col)) {
                break;
            }
            temporary = order[position];
            order[position] = order[position - 1U];
            order[position - 1U] = temporary;
            --position;
        }
    }

    writer_text(writer, "{\"protocol_version\":");
    writer_uint(writer, config->protocol_version);
    writer_text(writer, ",\"config_schema_version\":");
    writer_uint(writer, config->config_schema_version);
    writer_text(writer, ",\"chip_class\":");
    writer_string(writer, config->chip_class);
    writer_text(writer, ",\"matrix\":{\"rows\":");
    writer_uint(writer, config->matrix.rows);
    writer_text(writer, ",\"cols\":");
    writer_uint(writer, config->matrix.cols);
    writer_text(writer, ",\"row_pins\":[");
    for (index = 0U; index < config->pinmap.row_pin_count &&
                     index < KB_CONFIG_MAX_ROWS; ++index) {
        if (index != 0U) {
            writer_text(writer, ",");
        }
        writer_uint(writer, config->pinmap.row_pins[index]);
    }
    writer_text(writer, "],\"col_pins\":[");
    for (index = 0U; index < config->pinmap.col_pin_count &&
                     index < KB_CONFIG_MAX_COLS; ++index) {
        if (index != 0U) {
            writer_text(writer, ",");
        }
        writer_uint(writer, config->pinmap.col_pins[index]);
    }
    writer_text(writer, "],\"scan_mode\":");
    writer_string(writer, scan_mode_name(config->pinmap.scan_mode));
    writer_text(writer, ",\"pull_up_source\":");
    writer_string(writer, pullup_name(config->pinmap.pull_up_source));
    writer_text(writer, ",\"debounce_ms\":");
    writer_uint(writer, config->debounce_ms);
    writer_text(writer, ",\"diode_direction\":");
    if (config->diode_scope == KB_DIODE_SCOPE_BOARD) {
        writer_string(writer, diode_name(config->board_diode_direction));
    } else {
        writer_text(writer, "{");
        for (index = 0U; index < switch_count; ++index) {
            const kb_switch_config_t *item = &config->switches[order[index]];
            if (index != 0U) {
                writer_text(writer, ",");
            }
            write_key_id(writer, item->row, item->col);
            writer_text(writer, ":");
            writer_string(writer, diode_name(item->diode_direction));
        }
        writer_text(writer, "}");
    }
    writer_text(writer, ",\"populated\":[");
    for (index = 0U; index < switch_count; ++index) {
        const kb_switch_config_t *item = &config->switches[order[index]];
        if (index != 0U) {
            writer_text(writer, ",");
        }
        writer_text(writer, "{\"row\":");
        writer_uint(writer, item->row);
        writer_text(writer, ",\"col\":");
        writer_uint(writer, item->col);
        writer_text(writer, ",\"key_id\":");
        write_key_id(writer, item->row, item->col);
        writer_text(writer, "}");
    }
    writer_text(writer, "]},\"actions\":{");
    for (index = 0U; index < switch_count; ++index) {
        const kb_switch_config_t *item = &config->switches[order[index]];
        if (index != 0U) {
            writer_text(writer, ",");
        }
        write_key_id(writer, item->row, item->col);
        writer_text(writer, ":");
        write_action(writer, &item->action);
    }
    writer_text(writer, "},\"meta\":{\"project_name\":");
    writer_string(writer, config->meta.project_name);
    writer_text(writer, ",\"project_version\":");
    writer_uint(writer, config->meta.project_version);
    writer_text(writer, ",\"profile_version\":");
    writer_uint(writer, config->meta.profile_version);
    writer_text(writer, ",\"matrix_schema_version\":");
    writer_uint(writer, config->meta.matrix_schema_version);
    writer_text(writer, ",\"updated\":");
    writer_string(writer, config->meta.updated);
    writer_text(writer, "},\"extensions\":{},\"generation\":");
    writer_uint(writer, config->generation);
    if (include_crc) {
        writer_text(writer, ",\"crc32\":");
        writer_uint(writer, config->crc32);
    }
    writer_text(writer, "}");
}

void kb_config_init(kb_config_t *config)
{
    if (config == NULL) {
        return;
    }
    memset(config, 0, sizeof(*config));
    config->protocol_version = KB_CONFIG_PROTOCOL_VERSION;
    config->config_schema_version = KB_CONFIG_SCHEMA_VERSION;
    (void)snprintf(config->chip_class, sizeof(config->chip_class), "%s", "generic");
    config->pinmap.scan_mode = KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP;
    config->pinmap.pull_up_source = KB_PULL_UP_INTERNAL;
    config->debounce_ms = KB_CONFIG_DEFAULT_DEBOUNCE_MS;
    config->diode_scope = KB_DIODE_SCOPE_BOARD;
    config->board_diode_direction = KB_DIODE_COL_TO_ROW;
    config->meta.project_version = 3U;
    config->meta.profile_version = 2U;
    config->meta.matrix_schema_version = 1U;
}

static kb_config_build_result_t builder_copy(char *target, size_t capacity,
                                             const char *source)
{
    size_t length;
    if (source == NULL) {
        return KB_CONFIG_BUILD_INVALID_ARGUMENT;
    }
    length = strlen(source);
    if (length >= capacity) {
        return KB_CONFIG_BUILD_BUFFER_TOO_SMALL;
    }
    memcpy(target, source, length + 1U);
    return KB_CONFIG_BUILD_OK;
}

kb_config_build_result_t kb_config_builder_init(kb_config_builder_t *builder,
                                                const char *chip_class,
                                                uint8_t rows, uint8_t cols)
{
    kb_config_build_result_t result;
    if (builder == NULL || chip_class == NULL) {
        return KB_CONFIG_BUILD_INVALID_ARGUMENT;
    }
    if (rows == 0U || rows > KB_CONFIG_MAX_ROWS || cols == 0U ||
        cols > KB_CONFIG_MAX_COLS) {
        return KB_CONFIG_BUILD_VALUE_RANGE;
    }
    kb_config_init(&builder->config);
    result = builder_copy(builder->config.chip_class,
                          sizeof(builder->config.chip_class), chip_class);
    if (result != KB_CONFIG_BUILD_OK) {
        memset(builder, 0, sizeof(*builder));
        return result;
    }
    builder->config.matrix.rows = rows;
    builder->config.matrix.cols = cols;
    return KB_CONFIG_BUILD_OK;
}

kb_config_build_result_t kb_config_builder_set_pinmap(
    kb_config_builder_t *builder, const uint8_t *row_pins,
    size_t row_pin_count, const uint8_t *col_pins, size_t col_pin_count,
    kb_scan_mode_t scan_mode, kb_pull_up_source_t pull_up_source)
{
    if (builder == NULL || row_pins == NULL || col_pins == NULL) {
        return KB_CONFIG_BUILD_INVALID_ARGUMENT;
    }
    if (row_pin_count != builder->config.matrix.rows ||
        col_pin_count != builder->config.matrix.cols ||
        row_pin_count > KB_CONFIG_MAX_ROWS || col_pin_count > KB_CONFIG_MAX_COLS ||
        scan_mode > KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP ||
        pull_up_source > KB_PULL_UP_EXTERNAL) {
        return KB_CONFIG_BUILD_VALUE_RANGE;
    }
    memcpy(builder->config.pinmap.row_pins, row_pins, row_pin_count);
    memcpy(builder->config.pinmap.col_pins, col_pins, col_pin_count);
    builder->config.pinmap.row_pin_count = (uint8_t)row_pin_count;
    builder->config.pinmap.col_pin_count = (uint8_t)col_pin_count;
    builder->config.pinmap.scan_mode = scan_mode;
    builder->config.pinmap.pull_up_source = pull_up_source;
    return KB_CONFIG_BUILD_OK;
}

kb_config_build_result_t kb_config_builder_set_electrical(
    kb_config_builder_t *builder, uint16_t debounce_ms,
    kb_diode_scope_t diode_scope,
    kb_diode_direction_t board_diode_direction)
{
    if (builder == NULL) {
        return KB_CONFIG_BUILD_INVALID_ARGUMENT;
    }
    if (debounce_ms < KB_CONFIG_MIN_DEBOUNCE_MS ||
        debounce_ms > KB_CONFIG_MAX_DEBOUNCE_MS ||
        diode_scope > KB_DIODE_SCOPE_PER_SWITCH ||
        board_diode_direction > KB_DIODE_ROW_TO_COL) {
        return KB_CONFIG_BUILD_VALUE_RANGE;
    }
    builder->config.debounce_ms = debounce_ms;
    builder->config.diode_scope = diode_scope;
    builder->config.board_diode_direction = board_diode_direction;
    return KB_CONFIG_BUILD_OK;
}

kb_config_build_result_t kb_config_builder_set_meta(
    kb_config_builder_t *builder, const char *project_name,
    uint16_t project_version, uint16_t profile_version,
    uint16_t matrix_schema_version, const char *updated)
{
    kb_config_meta_t candidate;
    kb_config_build_result_t result;
    if (builder == NULL) {
        return KB_CONFIG_BUILD_INVALID_ARGUMENT;
    }
    candidate = builder->config.meta;
    result = builder_copy(candidate.project_name, sizeof(candidate.project_name),
                          project_name);
    if (result != KB_CONFIG_BUILD_OK) {
        return result;
    }
    result = builder_copy(candidate.updated, sizeof(candidate.updated), updated);
    if (result != KB_CONFIG_BUILD_OK) {
        return result;
    }
    candidate.project_version = project_version;
    candidate.profile_version = profile_version;
    candidate.matrix_schema_version = matrix_schema_version;
    builder->config.meta = candidate;
    return KB_CONFIG_BUILD_OK;
}

kb_config_build_result_t kb_config_builder_add_switch(
    kb_config_builder_t *builder, uint8_t row, uint8_t col,
    kb_diode_direction_t diode_direction, const kb_action_t *action)
{
    kb_switch_config_t *item;
    size_t index;
    if (builder == NULL || action == NULL) {
        return KB_CONFIG_BUILD_INVALID_ARGUMENT;
    }
    if (row >= builder->config.matrix.rows || col >= builder->config.matrix.cols ||
        diode_direction > KB_DIODE_ROW_TO_COL) {
        return KB_CONFIG_BUILD_VALUE_RANGE;
    }
    if (builder->config.switch_count >= KB_CONFIG_MAX_KEYS) {
        return KB_CONFIG_BUILD_TOO_MANY_SWITCHES;
    }
    for (index = 0U; index < builder->config.switch_count; ++index) {
        if (builder->config.switches[index].row == row &&
            builder->config.switches[index].col == col) {
            return KB_CONFIG_BUILD_VALUE_RANGE;
        }
    }
    item = &builder->config.switches[builder->config.switch_count++];
    item->row = row;
    item->col = col;
    item->diode_direction = diode_direction;
    item->action = *action;
    return KB_CONFIG_BUILD_OK;
}

kb_config_build_result_t kb_config_builder_finish(kb_config_builder_t *builder,
                                                  uint32_t generation,
                                                  kb_config_t *output)
{
    kb_config_t candidate;
    if (builder == NULL || output == NULL) {
        return KB_CONFIG_BUILD_INVALID_ARGUMENT;
    }
    candidate = builder->config;
    candidate.generation = generation;
    if (kb_config_finalize_crc32(&candidate) != KB_CONFIG_PARSE_OK) {
        return KB_CONFIG_BUILD_BUFFER_TOO_SMALL;
    }
    *output = candidate;
    return KB_CONFIG_BUILD_OK;
}

void kb_config_errors_reset(kb_config_error_list_t *errors)
{
    if (errors != NULL) {
        memset(errors, 0, sizeof(*errors));
    }
}

static void add_error(kb_config_error_list_t *errors,
                      kb_config_error_code_t code, const char *field,
                      int index, int related)
{
    kb_config_error_t *item;
    if (errors == NULL) {
        return;
    }
    if (errors->count >= KB_CONFIG_MAX_ERRORS) {
        ++errors->dropped;
        return;
    }
    item = &errors->items[errors->count++];
    item->code = code;
    item->index = (int16_t)index;
    item->related_index = (int16_t)related;
    (void)snprintf(item->field, sizeof(item->field), "%s", field);
}

static bool pin_in_list(uint8_t pin, const uint8_t *pins, uint8_t count)
{
    uint8_t index;
    for (index = 0U; index < count; ++index) {
        if (pins[index] == pin) {
            return true;
        }
    }
    return false;
}

static bool known_key(const char *name, uint16_t usage)
{
    size_t index;
    for (index = 0U; index < sizeof(key_usages) / sizeof(key_usages[0]); ++index) {
        if (key_usages[index].usage == usage &&
            strcmp(key_usages[index].name, name) == 0) {
            return true;
        }
    }
    return false;
}

static bool known_media(const char *name, uint16_t usage)
{
    size_t index;
    for (index = 0U; index < sizeof(media_usages) / sizeof(media_usages[0]); ++index) {
        if (media_usages[index].usage == usage &&
            strcmp(media_usages[index].name, name) == 0) {
            return true;
        }
    }
    return false;
}

static bool expected_diode(const kb_config_t *config,
                           kb_diode_direction_t direction)
{
    if (config->pinmap.scan_mode == KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP) {
        return direction == KB_DIODE_COL_TO_ROW;
    }
    if (config->pinmap.scan_mode == KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP) {
        return direction == KB_DIODE_ROW_TO_COL;
    }
    return false;
}

static void validate_pin(const kb_config_t *config, const kb_hal_probe_t *probe,
                         kb_config_error_list_t *errors, uint8_t pin,
                         bool driven, const char *field, int index)
{
    if (probe == NULL) {
        return;
    }
    if (pin >= probe->pin_count) {
        add_error(errors, KB_CONFIG_ERROR_PIN_RANGE, field, index, -1);
    }
    if (pin_in_list(pin, probe->reserved_pins, probe->reserved_pin_count)) {
        add_error(errors, KB_CONFIG_ERROR_RESERVED_PIN, field, index, -1);
    }
    if (driven && pin_in_list(pin, probe->input_only_pins,
                              probe->input_only_pin_count)) {
        add_error(errors, KB_CONFIG_ERROR_INPUT_ONLY_OUTPUT_PIN, field, index, -1);
    }
    if (!driven && config->pinmap.pull_up_source == KB_PULL_UP_INTERNAL &&
        pin_in_list(pin, probe->external_pullup_pins,
                    probe->external_pullup_pin_count)) {
        add_error(errors, KB_CONFIG_ERROR_EXTERNAL_PULLUP_REQUIRED, field, index, -1);
    }
}

bool kb_config_validate(const kb_config_t *config, const kb_hal_probe_t *probe,
                        kb_config_error_list_t *errors)
{
    size_t index;
    uint8_t all_pins[KB_CONFIG_MAX_ROWS + KB_CONFIG_MAX_COLS];
    size_t pin_total = 0U;
    uint32_t calculated_crc = 0U;

    kb_config_errors_reset(errors);
    if (config == NULL) {
        add_error(errors, KB_CONFIG_ERROR_BAD_SCHEMA_VERSION, "config", -1, -1);
        return false;
    }
    if (config->protocol_version != KB_CONFIG_PROTOCOL_VERSION) {
        add_error(errors, KB_CONFIG_ERROR_BAD_PROTOCOL_VERSION,
                  "protocol_version", -1, -1);
    }
    if (config->config_schema_version != KB_CONFIG_SCHEMA_VERSION) {
        add_error(errors, KB_CONFIG_ERROR_BAD_SCHEMA_VERSION,
                  "config_schema_version", -1, -1);
    }
    if (config->matrix.rows == 0U || config->matrix.rows > KB_CONFIG_MAX_ROWS) {
        add_error(errors, KB_CONFIG_ERROR_MATRIX_ROWS, "matrix.rows", -1, -1);
    }
    if (config->matrix.cols == 0U || config->matrix.cols > KB_CONFIG_MAX_COLS) {
        add_error(errors, KB_CONFIG_ERROR_MATRIX_COLS, "matrix.cols", -1, -1);
    }
    if (config->pinmap.row_pin_count != config->matrix.rows) {
        add_error(errors, KB_CONFIG_ERROR_ROW_PIN_COUNT, "matrix.row_pins", -1, -1);
    }
    if (config->pinmap.col_pin_count != config->matrix.cols) {
        add_error(errors, KB_CONFIG_ERROR_COL_PIN_COUNT, "matrix.col_pins", -1, -1);
    }
    if (config->debounce_ms < KB_CONFIG_MIN_DEBOUNCE_MS ||
        config->debounce_ms > KB_CONFIG_MAX_DEBOUNCE_MS) {
        add_error(errors, KB_CONFIG_ERROR_DEBOUNCE_RANGE,
                  "matrix.debounce_ms", -1, -1);
    }
    if (config->switch_count > KB_CONFIG_MAX_KEYS) {
        add_error(errors, KB_CONFIG_ERROR_SWITCH_COUNT,
                  "matrix.populated", -1, -1);
    }
    for (index = 0U; index < config->pinmap.row_pin_count &&
                     index < KB_CONFIG_MAX_ROWS; ++index) {
        const bool driven = config->pinmap.scan_mode ==
                            KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP;
        validate_pin(config, probe, errors, config->pinmap.row_pins[index], driven,
                     "matrix.row_pins", (int)index);
        all_pins[pin_total++] = config->pinmap.row_pins[index];
    }
    for (index = 0U; index < config->pinmap.col_pin_count &&
                     index < KB_CONFIG_MAX_COLS; ++index) {
        const bool driven = config->pinmap.scan_mode ==
                            KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP;
        validate_pin(config, probe, errors, config->pinmap.col_pins[index], driven,
                     "matrix.col_pins", (int)index);
        all_pins[pin_total++] = config->pinmap.col_pins[index];
    }
    for (index = 0U; index < pin_total; ++index) {
        size_t other;
        for (other = index + 1U; other < pin_total; ++other) {
            if (all_pins[index] == all_pins[other]) {
                add_error(errors, KB_CONFIG_ERROR_DUPLICATE_PIN, "matrix.pinmap",
                          (int)index, (int)other);
            }
        }
    }
    if (config->diode_scope == KB_DIODE_SCOPE_BOARD &&
        !expected_diode(config, config->board_diode_direction)) {
        add_error(errors, KB_CONFIG_ERROR_SCAN_DIODE_MISMATCH,
                  "matrix.diode_direction", -1, -1);
    }
    for (index = 0U; index < config->switch_count && index < KB_CONFIG_MAX_KEYS;
         ++index) {
        const kb_switch_config_t *item = &config->switches[index];
        size_t other;
        if (item->row >= config->matrix.rows || item->col >= config->matrix.cols) {
            add_error(errors, KB_CONFIG_ERROR_POPULATED_OUT_OF_RANGE,
                      "matrix.populated", (int)index, -1);
        }
        for (other = index + 1U; other < config->switch_count &&
                                other < KB_CONFIG_MAX_KEYS; ++other) {
            if (item->row == config->switches[other].row &&
                item->col == config->switches[other].col) {
                add_error(errors, KB_CONFIG_ERROR_DUPLICATE_SWITCH,
                          "matrix.populated", (int)index, (int)other);
            }
        }
        if (config->diode_scope == KB_DIODE_SCOPE_PER_SWITCH &&
            !expected_diode(config, item->diode_direction)) {
            add_error(errors, KB_CONFIG_ERROR_SCAN_DIODE_MISMATCH,
                      "matrix.diode_direction", (int)index, -1);
        }
        switch (item->action.type) {
        case KB_ACTION_NONE:
            break;
        case KB_ACTION_KEY:
            if (!known_key(item->action.key_name, item->action.usage_id)) {
                add_error(errors, KB_CONFIG_ERROR_HID_USAGE, "actions",
                          (int)index, -1);
            }
            break;
        case KB_ACTION_SHORTCUT: {
            size_t modifier;
            bool bad = item->action.modifier_count == 0U ||
                       item->action.modifier_count > KB_CONFIG_MAX_SHORTCUT_MODIFIERS;
            for (modifier = 0U; modifier < item->action.modifier_count &&
                                modifier < KB_CONFIG_MAX_SHORTCUT_MODIFIERS;
                 ++modifier) {
                size_t earlier;
                if (item->action.modifier_bits[modifier] >= 8U) {
                    bad = true;
                }
                for (earlier = 0U; earlier < modifier; ++earlier) {
                    if (item->action.modifier_bits[earlier] ==
                        item->action.modifier_bits[modifier]) {
                        bad = true;
                    }
                }
            }
            if (bad) {
                add_error(errors, KB_CONFIG_ERROR_SHORTCUT_MODIFIERS, "actions",
                          (int)index, -1);
            }
            if (!known_key(item->action.key_name, item->action.usage_id)) {
                add_error(errors, KB_CONFIG_ERROR_HID_USAGE, "actions",
                          (int)index, -1);
            }
            break;
        }
        case KB_ACTION_MEDIA:
            if (!known_media(item->action.key_name, item->action.usage_id)) {
                add_error(errors, KB_CONFIG_ERROR_HID_USAGE, "actions",
                          (int)index, -1);
            }
            break;
        case KB_ACTION_MODIFIER:
            if (item->action.modifier_bit >= 8U ||
                item->action.usage_id != UINT16_C(0x00e0) +
                                         item->action.modifier_bit) {
                add_error(errors, KB_CONFIG_ERROR_HID_USAGE, "actions",
                          (int)index, -1);
            }
            break;
        default:
            add_error(errors, KB_CONFIG_ERROR_ACTION_TYPE, "actions",
                      (int)index, -1);
            break;
        }
    }
    if (config->switch_count > KB_CONFIG_MAX_KEYS) {
        add_error(errors, KB_CONFIG_ERROR_POPULATED_OUT_OF_RANGE,
                  "matrix.populated", -1, -1);
    }
    if (kb_config_calculate_crc32(config, &calculated_crc) != KB_CONFIG_PARSE_OK ||
        config->crc32 != calculated_crc) {
        add_error(errors, KB_CONFIG_ERROR_CRC_MISMATCH, "crc32", -1, -1);
    }
    return errors == NULL || errors->count == 0U;
}

kb_config_parse_code_t kb_config_calculate_crc32(const kb_config_t *config,
                                                 uint32_t *crc32)
{
    json_writer_t writer;
    if (config == NULL || crc32 == NULL) {
        return KB_CONFIG_PARSE_INVALID_ARGUMENT;
    }
    memset(&writer, 0, sizeof(writer));
    writer.capacity = SIZE_MAX;
    writer.crc_enabled = true;
    writer.crc = UINT32_C(0xffffffff);
    serialize_config(&writer, config, false);
    if (writer.failed) {
        return KB_CONFIG_PARSE_BUFFER_TOO_SMALL;
    }
    *crc32 = writer.crc ^ UINT32_C(0xffffffff);
    return KB_CONFIG_PARSE_OK;
}

kb_config_parse_code_t kb_config_finalize_crc32(kb_config_t *config)
{
    uint32_t crc;
    kb_config_parse_code_t result;
    if (config == NULL) {
        return KB_CONFIG_PARSE_INVALID_ARGUMENT;
    }
    result = kb_config_calculate_crc32(config, &crc);
    if (result == KB_CONFIG_PARSE_OK) {
        config->crc32 = crc;
    }
    return result;
}

kb_config_parse_code_t kb_config_to_json(const kb_config_t *config, char *output,
                                         size_t capacity, size_t *length)
{
    json_writer_t writer;
    if (config == NULL || output == NULL || capacity == 0U || length == NULL) {
        return KB_CONFIG_PARSE_INVALID_ARGUMENT;
    }
    memset(&writer, 0, sizeof(writer));
    writer.buffer = output;
    writer.capacity = capacity;
    serialize_config(&writer, config, true);
    if (writer.failed) {
        return KB_CONFIG_PARSE_BUFFER_TOO_SMALL;
    }
    output[writer.length] = '\0';
    *length = writer.length;
    return KB_CONFIG_PARSE_OK;
}

static bool json_is_space(char value)
{
    return value == ' ' || value == '\t' || value == '\r' || value == '\n';
}

static json_token_t *new_token(json_document_t *document, json_type_t type,
                               int start, int parent)
{
    json_token_t *token;
    if (document->count >= KB_JSON_MAX_TOKENS) {
        return NULL;
    }
    token = &document->tokens[document->count++];
    token->type = type;
    token->start = start;
    token->end = -1;
    token->size = 0;
    token->parent = parent;
    if (parent >= 0) {
        ++document->tokens[parent].size;
    }
    return token;
}

static bool valid_primitive(const char *value, size_t length)
{
    size_t index = 0U;
    bool digit = false;
    if ((length == 4U && memcmp(value, "true", 4U) == 0) ||
        (length == 5U && memcmp(value, "false", 5U) == 0) ||
        (length == 4U && memcmp(value, "null", 4U) == 0)) {
        return true;
    }
    if (index < length && value[index] == '-') {
        ++index;
    }
    while (index < length && value[index] >= '0' && value[index] <= '9') {
        digit = true;
        ++index;
    }
    if (index < length && value[index] == '.') {
        ++index;
        if (index >= length || value[index] < '0' || value[index] > '9') {
            return false;
        }
        while (index < length && value[index] >= '0' && value[index] <= '9') {
            ++index;
        }
    }
    if (index < length && (value[index] == 'e' || value[index] == 'E')) {
        ++index;
        if (index < length && (value[index] == '+' || value[index] == '-')) {
            ++index;
        }
        if (index >= length || value[index] < '0' || value[index] > '9') {
            return false;
        }
        while (index < length && value[index] >= '0' && value[index] <= '9') {
            ++index;
        }
    }
    return digit && index == length;
}

static void syntax_space(const char *json, size_t length, size_t *position)
{
    while (*position < length && json_is_space(json[*position])) {
        ++*position;
    }
}

static bool syntax_string(const char *json, size_t length, size_t *position)
{
    if (*position >= length || json[*position] != '"') {
        return false;
    }
    ++*position;
    while (*position < length) {
        const unsigned char byte = (unsigned char)json[*position];
        if (byte == '"') {
            ++*position;
            return true;
        }
        if (byte < 0x20U) {
            return false;
        }
        if (byte == '\\') {
            size_t hex;
            ++*position;
            if (*position >= length ||
                strchr("\"\\/bfnrtu", json[*position]) == NULL) {
                return false;
            }
            if (json[*position] == 'u') {
                for (hex = 0U; hex < 4U; ++hex) {
                    char digit;
                    ++*position;
                    if (*position >= length) {
                        return false;
                    }
                    digit = json[*position];
                    if (!((digit >= '0' && digit <= '9') ||
                          (digit >= 'a' && digit <= 'f') ||
                          (digit >= 'A' && digit <= 'F'))) {
                        return false;
                    }
                }
            }
        }
        ++*position;
    }
    return false;
}

static bool syntax_value(const char *json, size_t length, size_t *position,
                         unsigned depth);

static bool syntax_compound(const char *json, size_t length, size_t *position,
                            unsigned depth, bool object)
{
    const char close = object ? '}' : ']';
    ++*position;
    syntax_space(json, length, position);
    if (*position < length && json[*position] == close) {
        ++*position;
        return true;
    }
    for (;;) {
        if (object) {
            if (!syntax_string(json, length, position)) {
                return false;
            }
            syntax_space(json, length, position);
            if (*position >= length || json[*position] != ':') {
                return false;
            }
            ++*position;
            syntax_space(json, length, position);
        }
        if (!syntax_value(json, length, position, depth + 1U)) {
            return false;
        }
        syntax_space(json, length, position);
        if (*position < length && json[*position] == close) {
            ++*position;
            return true;
        }
        if (*position >= length || json[*position] != ',') {
            return false;
        }
        ++*position;
        syntax_space(json, length, position);
    }
}

static bool syntax_value(const char *json, size_t length, size_t *position,
                         unsigned depth)
{
    size_t start;
    if (depth > 64U || *position >= length) {
        return false;
    }
    if (json[*position] == '"') {
        return syntax_string(json, length, position);
    }
    if (json[*position] == '{') {
        return syntax_compound(json, length, position, depth, true);
    }
    if (json[*position] == '[') {
        return syntax_compound(json, length, position, depth, false);
    }
    start = *position;
    while (*position < length && !json_is_space(json[*position]) &&
           strchr(",]}", json[*position]) == NULL) {
        ++*position;
    }
    return start != *position && valid_primitive(json + start, *position - start);
}

static bool syntax_document(const char *json, size_t length)
{
    size_t position = 0U;
    syntax_space(json, length, &position);
    if (!syntax_value(json, length, &position, 0U)) {
        return false;
    }
    syntax_space(json, length, &position);
    return position == length;
}

static kb_config_parse_code_t tokenize(json_document_t *document,
                                       const char *json, size_t length)
{
    size_t position = 0U;
    int parent = -1;
    if (!syntax_document(json, length)) {
        return KB_CONFIG_PARSE_JSON_SYNTAX;
    }
    document->json = json;
    document->length = length;
    document->count = 0U;
    while (position < length) {
        const char value = json[position];
        if (json_is_space(value) || value == ':' || value == ',') {
            ++position;
            continue;
        }
        if (value == '{' || value == '[') {
            json_token_t *token = new_token(document,
                                            value == '{' ? JSON_OBJECT : JSON_ARRAY,
                                            (int)position, parent);
            if (token == NULL) {
                return KB_CONFIG_PARSE_TOO_COMPLEX;
            }
            parent = (int)(document->count - 1U);
            ++position;
            continue;
        }
        if (value == '}' || value == ']') {
            const json_type_t expected = value == '}' ? JSON_OBJECT : JSON_ARRAY;
            if (parent < 0 || document->tokens[parent].type != expected) {
                return KB_CONFIG_PARSE_JSON_SYNTAX;
            }
            document->tokens[parent].end = (int)(position + 1U);
            parent = document->tokens[parent].parent;
            ++position;
            continue;
        }
        if (value == '"') {
            const size_t start = ++position;
            json_token_t *token;
            bool closed = false;
            while (position < length) {
                const unsigned char byte = (unsigned char)json[position];
                if (byte == '"') {
                    closed = true;
                    break;
                }
                if (byte < 0x20U) {
                    return KB_CONFIG_PARSE_JSON_SYNTAX;
                }
                if (byte == '\\') {
                    size_t escape_length = 2U;
                    if (position + 1U >= length ||
                        strchr("\"\\/bfnrtu", json[position + 1U]) == NULL) {
                        return KB_CONFIG_PARSE_JSON_SYNTAX;
                    }
                    if (json[position + 1U] == 'u') {
                        size_t hex;
                        escape_length = 6U;
                        if (position + escape_length > length) {
                            return KB_CONFIG_PARSE_JSON_SYNTAX;
                        }
                        for (hex = position + 2U; hex < position + 6U; ++hex) {
                            const char digit = json[hex];
                            if (!((digit >= '0' && digit <= '9') ||
                                  (digit >= 'a' && digit <= 'f') ||
                                  (digit >= 'A' && digit <= 'F'))) {
                                return KB_CONFIG_PARSE_JSON_SYNTAX;
                            }
                        }
                    }
                    position += escape_length;
                    continue;
                }
                ++position;
            }
            if (!closed) {
                return KB_CONFIG_PARSE_JSON_SYNTAX;
            }
            token = new_token(document, JSON_STRING, (int)start, parent);
            if (token == NULL) {
                return KB_CONFIG_PARSE_TOO_COMPLEX;
            }
            token->end = (int)position;
            ++position;
            continue;
        }
        {
            const size_t start = position;
            json_token_t *token;
            while (position < length && !json_is_space(json[position]) &&
                   strchr(",]}:", json[position]) == NULL) {
                ++position;
            }
            if (start == position || !valid_primitive(json + start, position - start)) {
                return KB_CONFIG_PARSE_JSON_SYNTAX;
            }
            token = new_token(document, JSON_PRIMITIVE, (int)start, parent);
            if (token == NULL) {
                return KB_CONFIG_PARSE_TOO_COMPLEX;
            }
            token->end = (int)position;
        }
    }
    if (parent >= 0 ||
        (document->count != 0U && document->tokens[0].end < 0)) {
        return KB_CONFIG_PARSE_JSON_SYNTAX;
    }
    if (document->count == 0U || document->tokens[0].type != JSON_OBJECT ||
        document->tokens[0].parent != -1) {
        return KB_CONFIG_PARSE_JSON_SYNTAX;
    }
    {
        size_t index;
        for (index = 1U; index < document->count; ++index) {
            if (document->tokens[index].parent == -1) {
                return KB_CONFIG_PARSE_JSON_SYNTAX;
            }
        }
    }
    return KB_CONFIG_PARSE_OK;
}

static size_t token_next(const json_document_t *document, size_t index)
{
    const int end = document->tokens[index].end;
    ++index;
    while (index < document->count && document->tokens[index].start < end) {
        ++index;
    }
    return index;
}

static bool token_equals(const json_document_t *document, size_t index,
                         const char *value)
{
    const json_token_t *token = &document->tokens[index];
    const size_t wanted = strlen(value);
    const size_t actual = (size_t)(token->end - token->start);
    return token->type == JSON_STRING && actual == wanted &&
           memcmp(document->json + token->start, value, wanted) == 0;
}

static int object_get(const json_document_t *document, size_t object,
                      const char *name)
{
    size_t cursor;
    int pair;
    const json_token_t *token = &document->tokens[object];
    if (token->type != JSON_OBJECT || token->size % 2 != 0) {
        return -1;
    }
    cursor = object + 1U;
    for (pair = 0; pair < token->size / 2; ++pair) {
        const size_t value = cursor + 1U;
        if (value >= document->count ||
            document->tokens[cursor].parent != (int)object ||
            document->tokens[value].parent != (int)object) {
            return -1;
        }
        if (token_equals(document, cursor, name)) {
            return (int)value;
        }
        cursor = token_next(document, value);
    }
    return -1;
}

static bool object_only(const json_document_t *document, size_t object,
                        const char *const *allowed, size_t allowed_count)
{
    const json_token_t *token = &document->tokens[object];
    size_t cursor = object + 1U;
    int pair;
    if (token->type != JSON_OBJECT || token->size % 2 != 0) {
        return false;
    }
    for (pair = 0; pair < token->size / 2; ++pair) {
        size_t index;
        bool found = false;
        size_t previous_cursor = object + 1U;
        int previous;
        const json_token_t *key = &document->tokens[cursor];
        for (previous = 0; previous < pair; ++previous) {
            const json_token_t *previous_key = &document->tokens[previous_cursor];
            const size_t key_length = (size_t)(key->end - key->start);
            const size_t previous_length =
                (size_t)(previous_key->end - previous_key->start);
            if (key_length == previous_length &&
                memcmp(document->json + key->start,
                       document->json + previous_key->start, key_length) == 0) {
                return false;
            }
            previous_cursor = token_next(document, previous_cursor + 1U);
        }
        for (index = 0U; index < allowed_count; ++index) {
            if (token_equals(document, cursor, allowed[index])) {
                found = true;
                break;
            }
        }
        if (!found) {
            return false;
        }
        cursor = token_next(document, cursor + 1U);
    }
    return true;
}

static bool parse_uint(const json_document_t *document, size_t index,
                       uint32_t maximum, uint32_t *result)
{
    const json_token_t *token = &document->tokens[index];
    size_t cursor;
    uint32_t value = 0U;
    if (token->type != JSON_PRIMITIVE || token->start >= token->end) {
        return false;
    }
    for (cursor = (size_t)token->start; cursor < (size_t)token->end; ++cursor) {
        const char digit = document->json[cursor];
        if (digit < '0' || digit > '9' ||
            value > (maximum - (uint32_t)(digit - '0')) / 10U) {
            return false;
        }
        value = value * 10U + (uint32_t)(digit - '0');
    }
    *result = value;
    return true;
}

static int hex_value(char value)
{
    if (value >= '0' && value <= '9') {
        return value - '0';
    }
    if (value >= 'a' && value <= 'f') {
        return value - 'a' + 10;
    }
    return value - 'A' + 10;
}

static bool copy_string(const json_document_t *document, size_t index,
                        char *output, size_t capacity)
{
    const json_token_t *token = &document->tokens[index];
    size_t source;
    size_t target = 0U;
    if (token->type != JSON_STRING || capacity == 0U) {
        return false;
    }
    for (source = (size_t)token->start; source < (size_t)token->end; ++source) {
        unsigned char value = (unsigned char)document->json[source];
        if (value == '\\') {
            const char escape = document->json[++source];
            if (escape == 'u') {
                int code;
                if (source + 4U >= (size_t)token->end) {
                    return false;
                }
                code = hex_value(document->json[source + 1U]) * 4096 +
                       hex_value(document->json[source + 2U]) * 256 +
                       hex_value(document->json[source + 3U]) * 16 +
                       hex_value(document->json[source + 4U]);
                if (code > 0x7f) {
                    return false;
                }
                value = (unsigned char)code;
                source += 4U;
            } else {
                switch (escape) {
                case 'b': value = '\b'; break;
                case 'f': value = '\f'; break;
                case 'n': value = '\n'; break;
                case 'r': value = '\r'; break;
                case 't': value = '\t'; break;
                default: value = (unsigned char)escape; break;
                }
            }
        }
        if (target + 1U >= capacity) {
            return false;
        }
        output[target++] = (char)value;
    }
    output[target] = '\0';
    return true;
}

static bool primitive_null(const json_document_t *document, size_t index)
{
    const json_token_t *token = &document->tokens[index];
    return token->type == JSON_PRIMITIVE && token->end - token->start == 4 &&
           memcmp(document->json + token->start, "null", 4U) == 0;
}

static bool lookup_usage(const usage_name_t *table, size_t count,
                         const char *name, uint16_t *usage)
{
    size_t index;
    for (index = 0U; index < count; ++index) {
        if (strcmp(table[index].name, name) == 0) {
            *usage = table[index].usage;
            return true;
        }
    }
    return false;
}

static bool lookup_modifier(const char *name, uint8_t *bit)
{
    uint8_t index;
    for (index = 0U; index < 8U; ++index) {
        if (strcmp(modifier_names[index], name) == 0) {
            *bit = index;
            return true;
        }
    }
    return false;
}

static kb_config_parse_code_t parse_action(const json_document_t *document,
                                           size_t token_index,
                                           kb_action_t *action)
{
    static const char *const key_fields[] = {"type", "key"};
    static const char *const shortcut_fields[] = {"type", "modifiers", "key"};
    static const char *const modifier_fields[] = {"type", "modifier", "event"};
    char type[16];
    int type_token;
    int key_token;
    memset(action, 0, sizeof(*action));
    if (primitive_null(document, token_index)) {
        action->type = KB_ACTION_NONE;
        return KB_CONFIG_PARSE_OK;
    }
    if (document->tokens[token_index].type != JSON_OBJECT) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    type_token = object_get(document, token_index, "type");
    if (type_token < 0 || !copy_string(document, (size_t)type_token,
                                       type, sizeof(type))) {
        return KB_CONFIG_PARSE_MISSING_FIELD;
    }
    if (strcmp(type, "key") == 0 || strcmp(type, "media") == 0) {
        const usage_name_t *table = strcmp(type, "key") == 0 ? key_usages : media_usages;
        const size_t count = strcmp(type, "key") == 0
                                 ? sizeof(key_usages) / sizeof(key_usages[0])
                                 : sizeof(media_usages) / sizeof(media_usages[0]);
        if (!object_only(document, token_index, key_fields,
                         sizeof(key_fields) / sizeof(key_fields[0]))) {
            return KB_CONFIG_PARSE_UNKNOWN_FIELD;
        }
        key_token = object_get(document, token_index, "key");
        if (key_token < 0 ||
            !copy_string(document, (size_t)key_token, action->key_name,
                         sizeof(action->key_name))) {
            return KB_CONFIG_PARSE_MISSING_FIELD;
        }
        if (!lookup_usage(table, count, action->key_name, &action->usage_id)) {
            return KB_CONFIG_PARSE_UNKNOWN_ACTION;
        }
        action->type = strcmp(type, "key") == 0 ? KB_ACTION_KEY : KB_ACTION_MEDIA;
        return KB_CONFIG_PARSE_OK;
    }
    if (strcmp(type, "shortcut") == 0) {
        int modifiers_token;
        size_t cursor;
        int count;
        if (!object_only(document, token_index, shortcut_fields,
                         sizeof(shortcut_fields) / sizeof(shortcut_fields[0]))) {
            return KB_CONFIG_PARSE_UNKNOWN_FIELD;
        }
        key_token = object_get(document, token_index, "key");
        modifiers_token = object_get(document, token_index, "modifiers");
        if (key_token < 0 || modifiers_token < 0 ||
            !copy_string(document, (size_t)key_token, action->key_name,
                         sizeof(action->key_name)) ||
            !lookup_usage(key_usages, sizeof(key_usages) / sizeof(key_usages[0]),
                          action->key_name, &action->usage_id)) {
            return KB_CONFIG_PARSE_UNKNOWN_ACTION;
        }
        if (document->tokens[modifiers_token].type != JSON_ARRAY ||
            document->tokens[modifiers_token].size < 1 ||
            document->tokens[modifiers_token].size >
                (int)KB_CONFIG_MAX_SHORTCUT_MODIFIERS) {
            return KB_CONFIG_PARSE_VALUE_RANGE;
        }
        cursor = (size_t)modifiers_token + 1U;
        for (count = 0; count < document->tokens[modifiers_token].size; ++count) {
            char name[16];
            uint8_t bit;
            int earlier;
            if (!copy_string(document, cursor, name, sizeof(name)) ||
                !lookup_modifier(name, &bit)) {
                return KB_CONFIG_PARSE_UNKNOWN_ACTION;
            }
            for (earlier = 0; earlier < count; ++earlier) {
                if (action->modifier_bits[earlier] == bit) {
                    return KB_CONFIG_PARSE_VALUE_RANGE;
                }
            }
            action->modifier_bits[count] = bit;
            cursor = token_next(document, cursor);
        }
        action->modifier_count = (uint8_t)count;
        action->type = KB_ACTION_SHORTCUT;
        return KB_CONFIG_PARSE_OK;
    }
    if (strcmp(type, "modifier") == 0) {
        int modifier_token;
        int event_token;
        char modifier[16];
        char event[8];
        if (!object_only(document, token_index, modifier_fields,
                         sizeof(modifier_fields) / sizeof(modifier_fields[0]))) {
            return KB_CONFIG_PARSE_UNKNOWN_FIELD;
        }
        modifier_token = object_get(document, token_index, "modifier");
        event_token = object_get(document, token_index, "event");
        if (modifier_token < 0 || event_token < 0 ||
            !copy_string(document, (size_t)modifier_token, modifier,
                         sizeof(modifier)) ||
            !copy_string(document, (size_t)event_token, event, sizeof(event)) ||
            !lookup_modifier(modifier, &action->modifier_bit)) {
            return KB_CONFIG_PARSE_UNKNOWN_ACTION;
        }
        if (strcmp(event, "down") != 0 && strcmp(event, "up") != 0) {
            return KB_CONFIG_PARSE_UNKNOWN_ACTION;
        }
        action->type = KB_ACTION_MODIFIER;
        action->modifier_event = strcmp(event, "up") == 0 ? KB_MODIFIER_UP
                                                            : KB_MODIFIER_DOWN;
        action->usage_id = UINT16_C(0x00e0) + action->modifier_bit;
        return KB_CONFIG_PARSE_OK;
    }
    return KB_CONFIG_PARSE_UNKNOWN_ACTION;
}

static bool key_id_matches(const json_document_t *document, size_t token,
                           uint8_t row, uint8_t col)
{
    char expected[16];
    const int count = snprintf(expected, sizeof(expected), "MX-%02u-%02u",
                               (unsigned)row, (unsigned)col);
    return count > 0 && (size_t)count < sizeof(expected) &&
           token_equals(document, token, expected);
}

static kb_config_parse_code_t parse_pin_array(const json_document_t *document,
                                              int token_index, uint8_t *pins,
                                              uint8_t *count)
{
    size_t cursor;
    int item;
    if (token_index < 0 || document->tokens[token_index].type != JSON_ARRAY) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    if (document->tokens[token_index].size > (int)KB_CONFIG_MAX_ROWS) {
        return KB_CONFIG_PARSE_VALUE_RANGE;
    }
    cursor = (size_t)token_index + 1U;
    for (item = 0; item < document->tokens[token_index].size; ++item) {
        uint32_t value;
        if (!parse_uint(document, cursor, UINT8_MAX, &value)) {
            return KB_CONFIG_PARSE_WRONG_TYPE;
        }
        pins[item] = (uint8_t)value;
        cursor = token_next(document, cursor);
    }
    *count = (uint8_t)document->tokens[token_index].size;
    return KB_CONFIG_PARSE_OK;
}

static kb_config_parse_code_t parse_populated(const json_document_t *document,
                                              int token_index,
                                              kb_config_t *config)
{
    static const char *const fields[] = {"row", "col", "key_id"};
    size_t cursor;
    int item;
    if (token_index < 0 || document->tokens[token_index].type != JSON_ARRAY) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    if (document->tokens[token_index].size > (int)KB_CONFIG_MAX_KEYS) {
        return KB_CONFIG_PARSE_VALUE_RANGE;
    }
    cursor = (size_t)token_index + 1U;
    for (item = 0; item < document->tokens[token_index].size; ++item) {
        int row_token;
        int col_token;
        int key_token;
        uint32_t row;
        uint32_t col;
        if (document->tokens[cursor].type != JSON_OBJECT) {
            return KB_CONFIG_PARSE_WRONG_TYPE;
        }
        if (!object_only(document, cursor, fields,
                         sizeof(fields) / sizeof(fields[0]))) {
            return KB_CONFIG_PARSE_UNKNOWN_FIELD;
        }
        row_token = object_get(document, cursor, "row");
        col_token = object_get(document, cursor, "col");
        key_token = object_get(document, cursor, "key_id");
        if (row_token < 0 || col_token < 0 || key_token < 0) {
            return KB_CONFIG_PARSE_MISSING_FIELD;
        }
        if (!parse_uint(document, (size_t)row_token, UINT8_MAX, &row) ||
            !parse_uint(document, (size_t)col_token, UINT8_MAX, &col)) {
            return KB_CONFIG_PARSE_WRONG_TYPE;
        }
        if (!key_id_matches(document, (size_t)key_token, (uint8_t)row,
                            (uint8_t)col)) {
            return KB_CONFIG_PARSE_VALUE_RANGE;
        }
        config->switches[item].row = (uint8_t)row;
        config->switches[item].col = (uint8_t)col;
        cursor = token_next(document, cursor);
    }
    config->switch_count = (uint16_t)document->tokens[token_index].size;
    return KB_CONFIG_PARSE_OK;
}

static kb_config_parse_code_t parse_diode(const json_document_t *document,
                                          int token_index,
                                          kb_config_t *config)
{
    char value[16];
    size_t index;
    if (token_index < 0) {
        return KB_CONFIG_PARSE_MISSING_FIELD;
    }
    if (document->tokens[token_index].type == JSON_STRING) {
        if (!copy_string(document, (size_t)token_index, value, sizeof(value))) {
            return KB_CONFIG_PARSE_WRONG_TYPE;
        }
        if (strcmp(value, "col_to_row") == 0) {
            config->board_diode_direction = KB_DIODE_COL_TO_ROW;
        } else if (strcmp(value, "row_to_col") == 0) {
            config->board_diode_direction = KB_DIODE_ROW_TO_COL;
        } else {
            return KB_CONFIG_PARSE_VALUE_RANGE;
        }
        config->diode_scope = KB_DIODE_SCOPE_BOARD;
        return KB_CONFIG_PARSE_OK;
    }
    if (document->tokens[token_index].type != JSON_OBJECT ||
        document->tokens[token_index].size != (int)config->switch_count * 2) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    config->diode_scope = KB_DIODE_SCOPE_PER_SWITCH;
    for (index = 0U; index < config->switch_count; ++index) {
        char key_id[16];
        int direction_token;
        const int count = snprintf(key_id, sizeof(key_id), "MX-%02u-%02u",
                                   (unsigned)config->switches[index].row,
                                   (unsigned)config->switches[index].col);
        if (count <= 0 || (size_t)count >= sizeof(key_id)) {
            return KB_CONFIG_PARSE_VALUE_RANGE;
        }
        direction_token = object_get(document, (size_t)token_index, key_id);
        if (direction_token < 0 ||
            !copy_string(document, (size_t)direction_token, value, sizeof(value))) {
            return KB_CONFIG_PARSE_MISSING_FIELD;
        }
        if (strcmp(value, "col_to_row") == 0) {
            config->switches[index].diode_direction = KB_DIODE_COL_TO_ROW;
        } else if (strcmp(value, "row_to_col") == 0) {
            config->switches[index].diode_direction = KB_DIODE_ROW_TO_COL;
        } else {
            return KB_CONFIG_PARSE_VALUE_RANGE;
        }
    }
    return KB_CONFIG_PARSE_OK;
}

static kb_config_parse_code_t parse_actions(const json_document_t *document,
                                            int token_index,
                                            kb_config_t *config)
{
    size_t index;
    if (token_index < 0 || document->tokens[token_index].type != JSON_OBJECT) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    if (document->tokens[token_index].size != (int)config->switch_count * 2) {
        return KB_CONFIG_PARSE_VALUE_RANGE;
    }
    for (index = 0U; index < config->switch_count; ++index) {
        char key_id[16];
        int action_token;
        kb_config_parse_code_t result;
        const int count = snprintf(key_id, sizeof(key_id), "MX-%02u-%02u",
                                   (unsigned)config->switches[index].row,
                                   (unsigned)config->switches[index].col);
        if (count <= 0 || (size_t)count >= sizeof(key_id)) {
            return KB_CONFIG_PARSE_VALUE_RANGE;
        }
        action_token = object_get(document, (size_t)token_index, key_id);
        if (action_token < 0) {
            return KB_CONFIG_PARSE_MISSING_FIELD;
        }
        result = parse_action(document, (size_t)action_token,
                              &config->switches[index].action);
        if (result != KB_CONFIG_PARSE_OK) {
            return result;
        }
    }
    return KB_CONFIG_PARSE_OK;
}

static kb_config_parse_code_t parse_matrix(const json_document_t *document,
                                           int token_index,
                                           kb_config_t *config)
{
    static const char *const fields[] = {
        "rows", "cols", "row_pins", "col_pins", "scan_mode",
        "pull_up_source", "debounce_ms", "diode_direction", "populated"
    };
    int rows_token;
    int cols_token;
    int row_pins_token;
    int col_pins_token;
    int scan_token;
    int pullup_token;
    int debounce_token;
    int diode_token;
    int populated_token;
    uint32_t value;
    char text[48];
    kb_config_parse_code_t result;
    if (token_index < 0 || document->tokens[token_index].type != JSON_OBJECT) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    if (!object_only(document, (size_t)token_index, fields,
                     sizeof(fields) / sizeof(fields[0]))) {
        return KB_CONFIG_PARSE_UNKNOWN_FIELD;
    }
    rows_token = object_get(document, (size_t)token_index, "rows");
    cols_token = object_get(document, (size_t)token_index, "cols");
    row_pins_token = object_get(document, (size_t)token_index, "row_pins");
    col_pins_token = object_get(document, (size_t)token_index, "col_pins");
    scan_token = object_get(document, (size_t)token_index, "scan_mode");
    pullup_token = object_get(document, (size_t)token_index, "pull_up_source");
    debounce_token = object_get(document, (size_t)token_index, "debounce_ms");
    diode_token = object_get(document, (size_t)token_index, "diode_direction");
    populated_token = object_get(document, (size_t)token_index, "populated");
    if (rows_token < 0 || cols_token < 0 || row_pins_token < 0 ||
        col_pins_token < 0 || scan_token < 0 || pullup_token < 0 ||
        debounce_token < 0 || diode_token < 0 || populated_token < 0) {
        return KB_CONFIG_PARSE_MISSING_FIELD;
    }
    if (!parse_uint(document, (size_t)rows_token, UINT8_MAX, &value)) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    config->matrix.rows = (uint8_t)value;
    if (!parse_uint(document, (size_t)cols_token, UINT8_MAX, &value)) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    config->matrix.cols = (uint8_t)value;
    result = parse_pin_array(document, row_pins_token, config->pinmap.row_pins,
                             &config->pinmap.row_pin_count);
    if (result != KB_CONFIG_PARSE_OK) {
        return result;
    }
    result = parse_pin_array(document, col_pins_token, config->pinmap.col_pins,
                             &config->pinmap.col_pin_count);
    if (result != KB_CONFIG_PARSE_OK) {
        return result;
    }
    if (!copy_string(document, (size_t)scan_token, text, sizeof(text))) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    if (strcmp(text, "drive_rows_low_read_cols_pullup") == 0) {
        config->pinmap.scan_mode = KB_SCAN_DRIVE_ROWS_LOW_READ_COLS_PULLUP;
    } else if (strcmp(text, "drive_cols_low_read_rows_pullup") == 0) {
        config->pinmap.scan_mode = KB_SCAN_DRIVE_COLS_LOW_READ_ROWS_PULLUP;
    } else {
        return KB_CONFIG_PARSE_VALUE_RANGE;
    }
    if (!copy_string(document, (size_t)pullup_token, text, sizeof(text))) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    if (strcmp(text, "internal") == 0) {
        config->pinmap.pull_up_source = KB_PULL_UP_INTERNAL;
    } else if (strcmp(text, "external") == 0) {
        config->pinmap.pull_up_source = KB_PULL_UP_EXTERNAL;
    } else {
        return KB_CONFIG_PARSE_VALUE_RANGE;
    }
    if (!parse_uint(document, (size_t)debounce_token, UINT16_MAX, &value)) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    config->debounce_ms = (uint16_t)value;
    result = parse_populated(document, populated_token, config);
    if (result != KB_CONFIG_PARSE_OK) {
        return result;
    }
    return parse_diode(document, diode_token, config);
}

static kb_config_parse_code_t parse_meta(const json_document_t *document,
                                         int token_index,
                                         kb_config_meta_t *meta)
{
    static const char *const fields[] = {
        "project_name", "project_version", "profile_version",
        "matrix_schema_version", "updated"
    };
    int project_name;
    int project_version;
    int profile_version;
    int matrix_schema_version;
    int updated;
    uint32_t value;
    if (token_index < 0 || document->tokens[token_index].type != JSON_OBJECT) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    if (!object_only(document, (size_t)token_index, fields,
                     sizeof(fields) / sizeof(fields[0]))) {
        return KB_CONFIG_PARSE_UNKNOWN_FIELD;
    }
    project_name = object_get(document, (size_t)token_index, "project_name");
    project_version = object_get(document, (size_t)token_index, "project_version");
    profile_version = object_get(document, (size_t)token_index, "profile_version");
    matrix_schema_version = object_get(document, (size_t)token_index,
                                       "matrix_schema_version");
    updated = object_get(document, (size_t)token_index, "updated");
    if (project_name < 0 || project_version < 0 || profile_version < 0 ||
        matrix_schema_version < 0 || updated < 0) {
        return KB_CONFIG_PARSE_MISSING_FIELD;
    }
    if (!copy_string(document, (size_t)project_name, meta->project_name,
                     sizeof(meta->project_name)) ||
        !copy_string(document, (size_t)updated, meta->updated,
                     sizeof(meta->updated))) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    if (!parse_uint(document, (size_t)project_version, UINT16_MAX, &value)) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    meta->project_version = (uint16_t)value;
    if (!parse_uint(document, (size_t)profile_version, UINT16_MAX, &value)) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    meta->profile_version = (uint16_t)value;
    if (!parse_uint(document, (size_t)matrix_schema_version, UINT16_MAX, &value)) {
        return KB_CONFIG_PARSE_WRONG_TYPE;
    }
    meta->matrix_schema_version = (uint16_t)value;
    return KB_CONFIG_PARSE_OK;
}

kb_config_parse_code_t kb_config_from_json(const char *json, size_t length,
                                           kb_config_t *output)
{
    static const char *const fields[] = {
        "protocol_version", "config_schema_version", "chip_class", "matrix",
        "actions", "meta", "extensions", "generation", "crc32"
    };
    json_document_t *document;
    kb_config_t *parsed;
    kb_config_parse_code_t result;
    int protocol_token;
    int schema_token;
    int chip_token;
    int matrix_token;
    int actions_token;
    int meta_token;
    int extensions_token;
    int generation_token;
    int crc_token;
    uint32_t value;
    if (json == NULL || output == NULL || length == 0U) {
        return KB_CONFIG_PARSE_INVALID_ARGUMENT;
    }
    document = malloc(sizeof(*document));
    parsed = malloc(sizeof(*parsed));
    if (document == NULL || parsed == NULL) {
        free(document);
        free(parsed);
        return KB_CONFIG_PARSE_NO_MEMORY;
    }
    result = tokenize(document, json, length);
    if (result != KB_CONFIG_PARSE_OK) {
        goto done;
    }
    if (!object_only(document, 0U, fields, sizeof(fields) / sizeof(fields[0]))) {
        result = KB_CONFIG_PARSE_UNKNOWN_FIELD;
        goto done;
    }
    protocol_token = object_get(document, 0U, "protocol_version");
    schema_token = object_get(document, 0U, "config_schema_version");
    chip_token = object_get(document, 0U, "chip_class");
    matrix_token = object_get(document, 0U, "matrix");
    actions_token = object_get(document, 0U, "actions");
    meta_token = object_get(document, 0U, "meta");
    extensions_token = object_get(document, 0U, "extensions");
    generation_token = object_get(document, 0U, "generation");
    crc_token = object_get(document, 0U, "crc32");
    if (protocol_token < 0 || schema_token < 0 || chip_token < 0 ||
        matrix_token < 0 || actions_token < 0 || meta_token < 0 ||
        extensions_token < 0 || generation_token < 0 || crc_token < 0) {
        result = KB_CONFIG_PARSE_MISSING_FIELD;
        goto done;
    }
    if (document->tokens[extensions_token].type != JSON_OBJECT ||
        document->tokens[extensions_token].size != 0) {
        result = KB_CONFIG_PARSE_VALUE_RANGE;
        goto done;
    }
    kb_config_init(parsed);
    if (!parse_uint(document, (size_t)protocol_token, UINT16_MAX, &value)) {
        result = KB_CONFIG_PARSE_WRONG_TYPE;
        goto done;
    }
    parsed->protocol_version = (uint16_t)value;
    if (!parse_uint(document, (size_t)schema_token, UINT16_MAX, &value)) {
        result = KB_CONFIG_PARSE_WRONG_TYPE;
        goto done;
    }
    parsed->config_schema_version = (uint16_t)value;
    if (!copy_string(document, (size_t)chip_token, parsed->chip_class,
                     sizeof(parsed->chip_class))) {
        result = KB_CONFIG_PARSE_WRONG_TYPE;
        goto done;
    }
    result = parse_matrix(document, matrix_token, parsed);
    if (result != KB_CONFIG_PARSE_OK) {
        goto done;
    }
    result = parse_actions(document, actions_token, parsed);
    if (result != KB_CONFIG_PARSE_OK) {
        goto done;
    }
    result = parse_meta(document, meta_token, &parsed->meta);
    if (result != KB_CONFIG_PARSE_OK) {
        goto done;
    }
    if (!parse_uint(document, (size_t)generation_token, UINT32_MAX, &value)) {
        result = KB_CONFIG_PARSE_WRONG_TYPE;
        goto done;
    }
    parsed->generation = value;
    if (!parse_uint(document, (size_t)crc_token, UINT32_MAX, &value)) {
        result = KB_CONFIG_PARSE_WRONG_TYPE;
        goto done;
    }
    parsed->crc32 = value;
    *output = *parsed;
    result = KB_CONFIG_PARSE_OK;

done:
    free(parsed);
    free(document);
    return result;
}
