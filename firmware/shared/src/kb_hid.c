#include "kb_hid.h"

#include <string.h>

void kb_hid_init(kb_hid_state_t *state)
{
    if (state != NULL) memset(state, 0, sizeof(*state));
}

static int find_u8(const uint8_t *items, size_t count, uint8_t value)
{
    size_t index;
    for (index = 0U; index < count; ++index)
        if (items[index] == value) return (int)index;
    return -1;
}

static int find_u16(const uint16_t *items, size_t count, uint16_t value)
{
    size_t index;
    for (index = 0U; index < count; ++index)
        if (items[index] == value) return (int)index;
    return -1;
}

kb_hid_result_t kb_hid_apply(kb_hid_state_t *state,
                             const kb_typed_action_t *action)
{
    bool press;
    int found;
    if (state == NULL || action == NULL) return KB_HID_INVALID_ARGUMENT;
    if (action->type == KB_TYPED_ACTION_CUSTOM) {
        return action->payload_length <= KB_ACTION_CUSTOM_PAYLOAD_MAX
                   ? KB_HID_NO_CHANGE : KB_HID_UNSUPPORTED_ACTION;
    }
    press = action->type == KB_TYPED_ACTION_KEY_PRESS ||
            action->type == KB_TYPED_ACTION_CONSUMER_PRESS;
    if (action->type == KB_TYPED_ACTION_KEY_PRESS ||
        action->type == KB_TYPED_ACTION_KEY_RELEASE) {
        const uint8_t usage = (uint8_t)action->usage;
        size_t index;
        if (action->usage_page != UINT16_C(0x0007) || action->usage > 0xffU ||
            action->usage == 0U) return KB_HID_UNSUPPORTED_ACTION;
        if (usage >= 0xe0U && usage <= 0xe7U) {
            const uint8_t mask = (uint8_t)(1U << (usage - 0xe0U));
            const uint8_t before = state->modifiers;
            if (press) state->modifiers |= mask;
            else state->modifiers &= (uint8_t)~mask;
            return before == state->modifiers ? KB_HID_NO_CHANGE : KB_HID_OK;
        }
        found = find_u8(state->keys, KB_HID_MAX_KEYS, usage);
        if (press) {
            if (found >= 0) return KB_HID_NO_CHANGE;
            for (index = 0U; index < KB_HID_MAX_KEYS; ++index) {
                if (state->keys[index] == 0U) {
                    state->keys[index] = usage;
                    state->modifiers |= action->modifiers;
                    return KB_HID_OK;
                }
            }
            return KB_HID_ROLLOVER;
        }
        if (found < 0) return KB_HID_NO_CHANGE;
        if ((size_t)found + 1U < KB_HID_MAX_KEYS)
            memmove(&state->keys[found], &state->keys[found + 1],
                    KB_HID_MAX_KEYS - (size_t)found - 1U);
        state->keys[KB_HID_MAX_KEYS - 1U] = 0U;
        state->modifiers &= (uint8_t)~action->modifiers;
        return KB_HID_OK;
    }
    if (action->type == KB_TYPED_ACTION_CONSUMER_PRESS ||
        action->type == KB_TYPED_ACTION_CONSUMER_RELEASE) {
        if (action->usage_page != KB_ACTION_CONSUMER_USAGE_PAGE ||
            action->usage == 0U) return KB_HID_UNSUPPORTED_ACTION;
        found = find_u16(state->consumer_usages, state->consumer_count,
                         action->usage);
        if (press) {
            if (found >= 0) return KB_HID_NO_CHANGE;
            if (state->consumer_count == KB_HID_MAX_CONSUMER_USAGES)
                return KB_HID_ROLLOVER;
            state->consumer_usages[state->consumer_count++] = action->usage;
            return KB_HID_OK;
        }
        if (found < 0) return KB_HID_NO_CHANGE;
        if ((size_t)found + 1U < state->consumer_count)
            memmove(&state->consumer_usages[found],
                    &state->consumer_usages[found + 1],
                    (state->consumer_count - (size_t)found - 1U) *
                        sizeof(state->consumer_usages[0]));
        --state->consumer_count;
        state->consumer_usages[state->consumer_count] = 0U;
        return KB_HID_OK;
    }
    return KB_HID_UNSUPPORTED_ACTION;
}

void kb_hid_build_boot_report(const kb_hid_state_t *state,
                              uint8_t report[KB_HID_BOOT_REPORT_BYTES])
{
    if (state == NULL || report == NULL) return;
    memset(report, 0, KB_HID_BOOT_REPORT_BYTES);
    report[0] = state->modifiers;
    memcpy(&report[2], state->keys, KB_HID_MAX_KEYS);
}

void kb_hid_build_ble_report(const kb_hid_state_t *state,
                             uint8_t report[KB_HID_BLE_REPORT_BYTES])
{
    size_t index;
    if (state == NULL || report == NULL) return;
    memset(report, 0, KB_HID_BLE_REPORT_BYTES);
    kb_hid_build_boot_report(state, report);
    for (index = 0U; index < state->consumer_count; ++index) {
        const size_t offset = KB_HID_BOOT_REPORT_BYTES + index * 4U;
        report[offset] = (uint8_t)(KB_ACTION_CONSUMER_USAGE_PAGE & 0xffU);
        report[offset + 1U] = (uint8_t)(KB_ACTION_CONSUMER_USAGE_PAGE >> 8U);
        report[offset + 2U] =
            (uint8_t)(state->consumer_usages[index] & 0xffU);
        report[offset + 3U] =
            (uint8_t)(state->consumer_usages[index] >> 8U);
    }
}

kb_hid_result_t kb_hid_emit_if_changed(kb_hid_state_t *state,
                                       const kb_hal_ops_t *hal)
{
    uint8_t report[KB_HID_BLE_REPORT_BYTES];
    if (state == NULL || hal == NULL || hal->hal_ble_send_report == NULL)
        return KB_HID_INVALID_ARGUMENT;
    kb_hid_build_ble_report(state, report);
    if (state->has_last_report &&
        memcmp(report, state->last_report, sizeof(report)) == 0)
        return KB_HID_NO_CHANGE;
    if (hal->hal_ble_send_report(hal->ctx, report, sizeof(report)) != KB_HAL_OK)
        return KB_HID_HAL_ERROR;
    memcpy(state->last_report, report, sizeof(report));
    state->has_last_report = true;
    return KB_HID_OK;
}

kb_hid_result_t kb_hid_apply_and_emit(kb_hid_state_t *state,
                                      const kb_hal_ops_t *hal,
                                      const kb_typed_action_t *action)
{
    const kb_hid_result_t result = kb_hid_apply(state, action);
    if (result != KB_HID_OK) return result;
    return kb_hid_emit_if_changed(state, hal);
}
