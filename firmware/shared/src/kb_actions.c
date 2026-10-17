#include "kb_actions.h"

#include <stdio.h>
#include <string.h>

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

static bool lookup(const usage_name_t *items, size_t count, const char *name,
                   uint16_t *usage_id)
{
    size_t index;
    if (name == NULL || usage_id == NULL) {
        return false;
    }
    for (index = 0U; index < count; ++index) {
        if (strcmp(items[index].name, name) == 0) {
            *usage_id = items[index].usage;
            return true;
        }
    }
    return false;
}

bool kb_action_lookup_key(const char *name, uint16_t *usage_id)
{
    return lookup(key_usages, sizeof(key_usages) / sizeof(key_usages[0]),
                  name, usage_id);
}

bool kb_action_lookup_media(const char *name, uint16_t *usage_id)
{
    return lookup(media_usages, sizeof(media_usages) / sizeof(media_usages[0]),
                  name, usage_id);
}

bool kb_action_lookup_modifier(const char *name, uint8_t *bit_number)
{
    uint8_t index;
    if (name == NULL || bit_number == NULL) {
        return false;
    }
    for (index = 0U; index < 8U; ++index) {
        if (strcmp(modifier_names[index], name) == 0) {
            *bit_number = index;
            return true;
        }
    }
    return false;
}

const char *kb_action_modifier_name(uint8_t bit_number)
{
    return bit_number < 8U ? modifier_names[bit_number] : NULL;
}

typedef struct {
    const char *text;
    size_t length;
    size_t pos;
} cursor_t;

static void skip_ws(cursor_t *cursor)
{
    while (cursor->pos < cursor->length) {
        const char value = cursor->text[cursor->pos];
        if (value != ' ' && value != '\t' && value != '\r' && value != '\n') {
            break;
        }
        ++cursor->pos;
    }
}

static int hex_value(char value)
{
    if (value >= '0' && value <= '9') {
        return value - '0';
    }
    if (value >= 'a' && value <= 'f') {
        return value - 'a' + 10;
    }
    if (value >= 'A' && value <= 'F') {
        return value - 'A' + 10;
    }
    return -1;
}

static bool parse_string(cursor_t *cursor, char *output, size_t capacity)
{
    size_t used = 0U;
    skip_ws(cursor);
    if (cursor->pos >= cursor->length || cursor->text[cursor->pos++] != '"') {
        return false;
    }
    while (cursor->pos < cursor->length) {
        unsigned char value = (unsigned char)cursor->text[cursor->pos++];
        if (value == '"') {
            if (output == NULL || capacity == 0U || used >= capacity) {
                return false;
            }
            output[used] = '\0';
            return true;
        }
        if (value < 0x20U) {
            return false;
        }
        if (value == '\\') {
            unsigned code = 0U;
            size_t index;
            if (cursor->pos >= cursor->length) {
                return false;
            }
            value = (unsigned char)cursor->text[cursor->pos++];
            switch (value) {
            case '"': case '\\': case '/': break;
            case 'b': value = '\b'; break;
            case 'f': value = '\f'; break;
            case 'n': value = '\n'; break;
            case 'r': value = '\r'; break;
            case 't': value = '\t'; break;
            case 'u':
                if (cursor->length - cursor->pos < 4U) {
                    return false;
                }
                for (index = 0U; index < 4U; ++index) {
                    const int digit = hex_value(cursor->text[cursor->pos++]);
                    if (digit < 0) {
                        return false;
                    }
                    code = (code << 4U) | (unsigned)digit;
                }
                if (code > 0x7fU || code == 0U) {
                    return false;
                }
                value = (unsigned char)code;
                break;
            default:
                return false;
            }
        }
        if (output == NULL || used + 1U >= capacity) {
            return false;
        }
        output[used++] = (char)value;
    }
    return false;
}

static bool take(cursor_t *cursor, char expected)
{
    skip_ws(cursor);
    if (cursor->pos >= cursor->length || cursor->text[cursor->pos] != expected) {
        return false;
    }
    ++cursor->pos;
    return true;
}

enum {
    FIELD_TYPE = 1U << 0,
    FIELD_KEY = 1U << 1,
    FIELD_MODIFIERS = 1U << 2,
    FIELD_MODIFIER = 1U << 3,
    FIELD_EVENT = 1U << 4,
    FIELD_RAW = 1U << 5
};

kb_action_result_t kb_action_from_json(const char *json, size_t length,
                                       kb_action_t *action)
{
    cursor_t cursor;
    kb_action_t parsed;
    char type[16] = "";
    char event[8] = "";
    char modifier[16] = "";
    unsigned fields = 0U;
    if (json == NULL || action == NULL) {
        return KB_ACTION_INVALID_ARGUMENT;
    }
    cursor.text = json;
    cursor.length = length;
    cursor.pos = 0U;
    memset(&parsed, 0, sizeof(parsed));
    skip_ws(&cursor);
    if (length - cursor.pos >= 4U &&
        memcmp(json + cursor.pos, "null", 4U) == 0) {
        cursor.pos += 4U;
        skip_ws(&cursor);
        if (cursor.pos != length) {
            return KB_ACTION_MALFORMED_JSON;
        }
        *action = parsed;
        return KB_ACTION_OK;
    }
    if (!take(&cursor, '{')) {
        return KB_ACTION_MALFORMED_JSON;
    }
    skip_ws(&cursor);
    while (cursor.pos < length && cursor.text[cursor.pos] != '}') {
        char field[16];
        unsigned bit = 0U;
        if (!parse_string(&cursor, field, sizeof(field)) || !take(&cursor, ':')) {
            return KB_ACTION_MALFORMED_JSON;
        }
        if (strcmp(field, "type") == 0) bit = FIELD_TYPE;
        else if (strcmp(field, "key") == 0) bit = FIELD_KEY;
        else if (strcmp(field, "modifiers") == 0) bit = FIELD_MODIFIERS;
        else if (strcmp(field, "modifier") == 0) bit = FIELD_MODIFIER;
        else if (strcmp(field, "event") == 0) bit = FIELD_EVENT;
        else if (strcmp(field, "raw") == 0) bit = FIELD_RAW;
        else return KB_ACTION_UNKNOWN_FIELD;
        if ((fields & bit) != 0U) {
            return KB_ACTION_UNKNOWN_FIELD;
        }
        fields |= bit;
        if (bit == FIELD_TYPE) {
            if (!parse_string(&cursor, type, sizeof(type))) return KB_ACTION_WRONG_TYPE;
        } else if (bit == FIELD_KEY) {
            if (!parse_string(&cursor, parsed.key_name, sizeof(parsed.key_name))) return KB_ACTION_WRONG_TYPE;
        } else if (bit == FIELD_MODIFIER) {
            if (!parse_string(&cursor, modifier, sizeof(modifier))) return KB_ACTION_WRONG_TYPE;
        } else if (bit == FIELD_EVENT) {
            if (!parse_string(&cursor, event, sizeof(event))) return KB_ACTION_WRONG_TYPE;
        } else if (bit == FIELD_RAW) {
            if (!parse_string(&cursor, parsed.legacy_raw, sizeof(parsed.legacy_raw))) return KB_ACTION_WRONG_TYPE;
        } else {
            if (!take(&cursor, '[')) return KB_ACTION_WRONG_TYPE;
            skip_ws(&cursor);
            while (cursor.pos < length && cursor.text[cursor.pos] != ']') {
                char name[16];
                uint8_t modifier_bit;
                size_t earlier;
                if (parsed.modifier_count >= KB_ACTION_MAX_SHORTCUT_MODIFIERS) return KB_ACTION_VALUE_RANGE;
                if (!parse_string(&cursor, name, sizeof(name)) ||
                    !kb_action_lookup_modifier(name, &modifier_bit)) return KB_ACTION_UNKNOWN_NAME;
                for (earlier = 0U; earlier < parsed.modifier_count; ++earlier) {
                    if (parsed.modifier_bits[earlier] == modifier_bit) return KB_ACTION_VALUE_RANGE;
                }
                parsed.modifier_bits[parsed.modifier_count++] = modifier_bit;
                skip_ws(&cursor);
                if (cursor.pos < length && cursor.text[cursor.pos] == ',') {
                    ++cursor.pos;
                } else {
                    break;
                }
            }
            if (!take(&cursor, ']')) return KB_ACTION_MALFORMED_JSON;
        }
        skip_ws(&cursor);
        if (cursor.pos < length && cursor.text[cursor.pos] == ',') {
            ++cursor.pos;
            skip_ws(&cursor);
        } else {
            break;
        }
    }
    if (!take(&cursor, '}')) return KB_ACTION_MALFORMED_JSON;
    skip_ws(&cursor);
    if (cursor.pos != length) return KB_ACTION_MALFORMED_JSON;
    if ((fields & FIELD_TYPE) == 0U) return KB_ACTION_MISSING_FIELD;
    if (strcmp(type, "key") == 0 || strcmp(type, "media") == 0) {
        if (fields != (FIELD_TYPE | FIELD_KEY)) return KB_ACTION_UNKNOWN_FIELD;
        if (!(strcmp(type, "key") == 0
                  ? kb_action_lookup_key(parsed.key_name, &parsed.usage_id)
                  : kb_action_lookup_media(parsed.key_name, &parsed.usage_id))) {
            return KB_ACTION_UNKNOWN_NAME;
        }
        parsed.type = strcmp(type, "key") == 0 ? KB_ACTION_KEY : KB_ACTION_MEDIA;
    } else if (strcmp(type, "shortcut") == 0) {
        if (fields != (FIELD_TYPE | FIELD_KEY | FIELD_MODIFIERS)) return KB_ACTION_UNKNOWN_FIELD;
        if (parsed.modifier_count == 0U) return KB_ACTION_VALUE_RANGE;
        if (!kb_action_lookup_key(parsed.key_name, &parsed.usage_id)) return KB_ACTION_UNKNOWN_NAME;
        parsed.type = KB_ACTION_SHORTCUT;
    } else if (strcmp(type, "modifier") == 0) {
        if (fields != (FIELD_TYPE | FIELD_MODIFIER | FIELD_EVENT)) return KB_ACTION_UNKNOWN_FIELD;
        if (!kb_action_lookup_modifier(modifier, &parsed.modifier_bit)) return KB_ACTION_UNKNOWN_NAME;
        if (strcmp(event, "down") != 0 && strcmp(event, "up") != 0) return KB_ACTION_UNKNOWN_NAME;
        parsed.type = KB_ACTION_MODIFIER;
        parsed.modifier_event = strcmp(event, "up") == 0 ? KB_MODIFIER_UP : KB_MODIFIER_DOWN;
        parsed.usage_id = UINT16_C(0xe0) + parsed.modifier_bit;
    } else if (strcmp(type, "legacy") == 0) {
        if (fields != (FIELD_TYPE | FIELD_RAW)) return KB_ACTION_UNKNOWN_FIELD;
        parsed.type = KB_ACTION_LEGACY;
    } else {
        return KB_ACTION_UNKNOWN_TYPE;
    }
    *action = parsed;
    return KB_ACTION_OK;
}

typedef struct {
    char *output;
    size_t capacity;
    size_t length;
    bool failed;
} writer_t;

static void write_bytes(writer_t *writer, const char *value, size_t length)
{
    if (writer->failed || length > SIZE_MAX - writer->length ||
        writer->length + length >= writer->capacity) {
        writer->failed = true;
        return;
    }
    memcpy(writer->output + writer->length, value, length);
    writer->length += length;
}

static void write_text(writer_t *writer, const char *value)
{
    write_bytes(writer, value, strlen(value));
}

static void write_string(writer_t *writer, const char *value)
{
    const unsigned char *cursor = (const unsigned char *)value;
    write_text(writer, "\"");
    while (*cursor != 0U) {
        char escape[7];
        if (*cursor == '"' || *cursor == '\\') {
            escape[0] = '\\';
            escape[1] = (char)*cursor;
            write_bytes(writer, escape, 2U);
        } else if (*cursor < 0x20U) {
            const int count = snprintf(escape, sizeof(escape), "\\u%04x", *cursor);
            if (count != 6) writer->failed = true;
            else write_bytes(writer, escape, 6U);
        } else {
            write_bytes(writer, (const char *)cursor, 1U);
        }
        ++cursor;
    }
    write_text(writer, "\"");
}

static bool action_valid(const kb_action_t *action)
{
    uint16_t usage;
    size_t index;
    if (action == NULL) return false;
    switch (action->type) {
    case KB_ACTION_NONE: return true;
    case KB_ACTION_KEY:
        return kb_action_lookup_key(action->key_name, &usage) && usage == action->usage_id;
    case KB_ACTION_MEDIA:
        return kb_action_lookup_media(action->key_name, &usage) && usage == action->usage_id;
    case KB_ACTION_SHORTCUT:
        if (!kb_action_lookup_key(action->key_name, &usage) || usage != action->usage_id ||
            action->modifier_count == 0U || action->modifier_count > KB_ACTION_MAX_SHORTCUT_MODIFIERS) return false;
        for (index = 0U; index < action->modifier_count; ++index) {
            size_t prior;
            if (action->modifier_bits[index] >= 8U) return false;
            for (prior = 0U; prior < index; ++prior) if (action->modifier_bits[prior] == action->modifier_bits[index]) return false;
        }
        return true;
    case KB_ACTION_MODIFIER:
        return action->modifier_bit < 8U && action->usage_id == UINT16_C(0xe0) + action->modifier_bit &&
               (action->modifier_event == KB_MODIFIER_DOWN || action->modifier_event == KB_MODIFIER_UP);
    case KB_ACTION_LEGACY: return true;
    default: return false;
    }
}

kb_action_result_t kb_action_to_json(const kb_action_t *action, char *output,
                                     size_t capacity, size_t *length)
{
    writer_t writer;
    size_t index;
    if (action == NULL || output == NULL || capacity == 0U || length == NULL) return KB_ACTION_INVALID_ARGUMENT;
    if (!action_valid(action)) return KB_ACTION_UNKNOWN_NAME;
    memset(&writer, 0, sizeof(writer));
    writer.output = output;
    writer.capacity = capacity;
    switch (action->type) {
    case KB_ACTION_NONE: write_text(&writer, "null"); break;
    case KB_ACTION_KEY:
        write_text(&writer, "{\"type\":\"key\",\"key\":"); write_string(&writer, action->key_name); write_text(&writer, "}"); break;
    case KB_ACTION_MEDIA:
        write_text(&writer, "{\"type\":\"media\",\"key\":"); write_string(&writer, action->key_name); write_text(&writer, "}"); break;
    case KB_ACTION_SHORTCUT:
        write_text(&writer, "{\"type\":\"shortcut\",\"modifiers\":[");
        for (index = 0U; index < action->modifier_count; ++index) {
            if (index != 0U) write_text(&writer, ",");
            write_string(&writer, modifier_names[action->modifier_bits[index]]);
        }
        write_text(&writer, "],\"key\":"); write_string(&writer, action->key_name); write_text(&writer, "}"); break;
    case KB_ACTION_MODIFIER:
        write_text(&writer, "{\"type\":\"modifier\",\"modifier\":");
        write_string(&writer, modifier_names[action->modifier_bit]);
        write_text(&writer, ",\"event\":");
        write_string(&writer, action->modifier_event == KB_MODIFIER_UP ? "up" : "down"); write_text(&writer, "}"); break;
    case KB_ACTION_LEGACY:
        write_text(&writer, "{\"type\":\"legacy\",\"raw\":"); write_string(&writer, action->legacy_raw); write_text(&writer, "}"); break;
    default: return KB_ACTION_UNKNOWN_TYPE;
    }
    if (writer.failed) return KB_ACTION_BUFFER_TOO_SMALL;
    writer.output[writer.length] = '\0';
    *length = writer.length;
    return KB_ACTION_OK;
}

kb_action_result_t kb_action_keyboard_report(const kb_action_t *action,
                                             bool pressed,
                                             kb_keyboard_report_t *report)
{
    size_t index;
    if (action == NULL || report == NULL) return KB_ACTION_INVALID_ARGUMENT;
    memset(report, 0, sizeof(*report));
    if (!action_valid(action)) return KB_ACTION_UNKNOWN_NAME;
    if (action->type == KB_ACTION_KEY) {
        if (pressed) report->keycodes[0] = (uint8_t)action->usage_id;
    } else if (action->type == KB_ACTION_SHORTCUT) {
        if (pressed) {
            for (index = 0U; index < action->modifier_count; ++index) report->modifiers |= (uint8_t)(1U << action->modifier_bits[index]);
            report->keycodes[0] = (uint8_t)action->usage_id;
        }
    } else if (action->type == KB_ACTION_MODIFIER) {
        if (pressed && action->modifier_event == KB_MODIFIER_DOWN) report->modifiers = (uint8_t)(1U << action->modifier_bit);
    } else if (action->type != KB_ACTION_NONE) {
        return KB_ACTION_NOT_HID;
    }
    return KB_ACTION_OK;
}

kb_action_result_t kb_action_consumer_usage(const kb_action_t *action,
                                            bool pressed, uint16_t *usage_id)
{
    if (action == NULL || usage_id == NULL) return KB_ACTION_INVALID_ARGUMENT;
    if (!action_valid(action)) return KB_ACTION_UNKNOWN_NAME;
    if (action->type != KB_ACTION_MEDIA) return KB_ACTION_NOT_HID;
    *usage_id = pressed ? action->usage_id : 0U;
    return KB_ACTION_OK;
}

kb_action_result_t kb_action_make_custom(const uint8_t *payload,
                                         size_t payload_length,
                                         kb_typed_action_t *output)
{
    kb_typed_action_t candidate;
    if (output == NULL || (payload == NULL && payload_length != 0U)) {
        return KB_ACTION_INVALID_ARGUMENT;
    }
    if (payload_length > KB_ACTION_CUSTOM_PAYLOAD_MAX) {
        return KB_ACTION_VALUE_RANGE;
    }
    memset(&candidate, 0, sizeof(candidate));
    candidate.type = KB_TYPED_ACTION_CUSTOM;
    candidate.payload_length = payload_length;
    if (payload_length != 0U) {
        memcpy(candidate.payload, payload, payload_length);
    }
    *output = candidate;
    return KB_ACTION_OK;
}

kb_action_result_t kb_action_resolve(const kb_action_profile_t *profile,
                                     const char *key_id, bool pressed,
                                     kb_typed_action_t *output)
{
    size_t index;
    kb_typed_action_t candidate;
    const kb_action_t *desktop = NULL;
    if (profile == NULL || key_id == NULL || output == NULL ||
        profile->key_actions == NULL) {
        return KB_ACTION_INVALID_ARGUMENT;
    }
    for (index = 0U; index < profile->key_action_count; ++index) {
        if (profile->key_actions[index].key_id != NULL &&
            strcmp(profile->key_actions[index].key_id, key_id) == 0) {
            desktop = profile->key_actions[index].desktop_action;
            break;
        }
    }
    if (desktop == NULL || !action_valid(desktop)) {
        return desktop == NULL ? KB_ACTION_MISSING_FIELD : KB_ACTION_UNKNOWN_NAME;
    }
    memset(&candidate, 0, sizeof(candidate));
    switch (desktop->type) {
    case KB_ACTION_KEY:
        candidate.type = pressed ? KB_TYPED_ACTION_KEY_PRESS
                                 : KB_TYPED_ACTION_KEY_RELEASE;
        candidate.usage_page = UINT16_C(0x0007);
        candidate.usage = desktop->usage_id;
        break;
    case KB_ACTION_MEDIA:
        candidate.type = pressed ? KB_TYPED_ACTION_CONSUMER_PRESS
                                 : KB_TYPED_ACTION_CONSUMER_RELEASE;
        candidate.usage_page = KB_ACTION_CONSUMER_USAGE_PAGE;
        candidate.usage = desktop->usage_id;
        break;
    case KB_ACTION_MODIFIER:
        candidate.type = pressed && desktop->modifier_event == KB_MODIFIER_DOWN
                             ? KB_TYPED_ACTION_KEY_PRESS
                             : KB_TYPED_ACTION_KEY_RELEASE;
        candidate.usage_page = UINT16_C(0x0007);
        candidate.usage = desktop->usage_id;
        break;
    case KB_ACTION_SHORTCUT:
        candidate.type = pressed ? KB_TYPED_ACTION_KEY_PRESS
                                 : KB_TYPED_ACTION_KEY_RELEASE;
        candidate.usage_page = UINT16_C(0x0007);
        candidate.usage = desktop->usage_id;
        for (index = 0U; index < desktop->modifier_count; ++index)
            candidate.modifiers |=
                (uint8_t)(1U << desktop->modifier_bits[index]);
        break;
    case KB_ACTION_NONE:
    case KB_ACTION_LEGACY:
    default:
        return KB_ACTION_NOT_HID;
    }
    *output = candidate;
    return KB_ACTION_OK;
}
