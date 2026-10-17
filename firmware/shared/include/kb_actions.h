#ifndef KB_ACTIONS_H
#define KB_ACTIONS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KB_ACTION_KEY_NAME_MAX 24U
#define KB_ACTION_LEGACY_RAW_MAX 64U
#define KB_ACTION_MAX_SHORTCUT_MODIFIERS 4U
#define KB_ACTION_KEYCODE_SLOTS 6U
#define KB_ACTION_CUSTOM_PAYLOAD_MAX 16U
#define KB_ACTION_CONSUMER_USAGE_PAGE UINT16_C(0x000c)

typedef enum {
    KB_ACTION_NONE = 0,
    KB_ACTION_KEY,
    KB_ACTION_SHORTCUT,
    KB_ACTION_MEDIA,
    KB_ACTION_MODIFIER,
    KB_ACTION_LEGACY
} kb_action_type_t;

typedef enum {
    KB_MODIFIER_DOWN = 0,
    KB_MODIFIER_UP
} kb_modifier_event_t;

/* Matches desktop_app.action's serialized variants without field renaming. */
typedef struct {
    kb_action_type_t type;
    char key_name[KB_ACTION_KEY_NAME_MAX];
    uint16_t usage_id;
    uint8_t modifier_count;
    uint8_t modifier_bits[KB_ACTION_MAX_SHORTCUT_MODIFIERS];
    uint8_t modifier_bit;
    kb_modifier_event_t modifier_event;
    char legacy_raw[KB_ACTION_LEGACY_RAW_MAX];
} kb_action_t;

/* Runtime actions are deliberately data only. Custom actions are passed to
 * callers unchanged; the shared core never executes their payload. */
typedef enum {
    KB_TYPED_ACTION_KEY_PRESS = 0,
    KB_TYPED_ACTION_KEY_RELEASE,
    KB_TYPED_ACTION_CONSUMER_PRESS,
    KB_TYPED_ACTION_CONSUMER_RELEASE,
    KB_TYPED_ACTION_CUSTOM
} kb_typed_action_type_t;

typedef struct {
    kb_typed_action_type_t type;
    uint16_t usage_page;
    uint16_t usage;
    uint8_t modifiers;
    uint8_t payload[KB_ACTION_CUSTOM_PAYLOAD_MAX];
    size_t payload_length;
} kb_typed_action_t;

typedef struct {
    const char *key_id;
    const kb_action_t *desktop_action;
} kb_key_action_t;

typedef struct {
    const kb_key_action_t *key_actions;
    size_t key_action_count;
} kb_action_profile_t;

typedef enum {
    KB_ACTION_OK = 0,
    KB_ACTION_INVALID_ARGUMENT,
    KB_ACTION_MALFORMED_JSON,
    KB_ACTION_MISSING_FIELD,
    KB_ACTION_UNKNOWN_FIELD,
    KB_ACTION_WRONG_TYPE,
    KB_ACTION_UNKNOWN_TYPE,
    KB_ACTION_UNKNOWN_NAME,
    KB_ACTION_VALUE_RANGE,
    KB_ACTION_BUFFER_TOO_SMALL,
    KB_ACTION_NOT_HID
} kb_action_result_t;

typedef struct {
    uint8_t modifiers;
    uint8_t reserved;
    uint8_t keycodes[KB_ACTION_KEYCODE_SLOTS];
} kb_keyboard_report_t;

bool kb_action_lookup_key(const char *name, uint16_t *usage_id);
bool kb_action_lookup_modifier(const char *name, uint8_t *bit_number);
bool kb_action_lookup_media(const char *name, uint16_t *usage_id);
const char *kb_action_modifier_name(uint8_t bit_number);

kb_action_result_t kb_action_from_json(const char *json, size_t length,
                                       kb_action_t *action);
kb_action_result_t kb_action_to_json(const kb_action_t *action, char *output,
                                     size_t capacity, size_t *length);
kb_action_result_t kb_action_keyboard_report(const kb_action_t *action,
                                             bool pressed,
                                             kb_keyboard_report_t *report);
kb_action_result_t kb_action_consumer_usage(const kb_action_t *action,
                                            bool pressed, uint16_t *usage_id);
kb_action_result_t kb_action_make_custom(const uint8_t *payload,
                                         size_t payload_length,
                                         kb_typed_action_t *output);
kb_action_result_t kb_action_resolve(const kb_action_profile_t *profile,
                                     const char *key_id, bool pressed,
                                     kb_typed_action_t *output);

#endif
