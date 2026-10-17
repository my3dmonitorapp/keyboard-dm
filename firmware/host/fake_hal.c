#include "fake_hal.h"

#include <string.h>

static kb_hal_error_t pin_direction(void *context, uint8_t pin,
                                    kb_hal_pin_direction_t direction)
{
    fake_hal_t *fake = context;
    if (fake == NULL || pin >= FAKE_HAL_MAX_PINS ||
        (direction != KB_HAL_PIN_INPUT && direction != KB_HAL_PIN_OUTPUT)) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    fake->pin_directions[pin] = direction;
    return KB_HAL_OK;
}

static kb_hal_error_t pin_write(void *context, uint8_t pin,
                                kb_hal_pin_value_t value)
{
    fake_hal_t *fake = context;
    if (fake == NULL || pin >= FAKE_HAL_MAX_PINS ||
        fake->pin_directions[pin] != KB_HAL_PIN_OUTPUT ||
        (value != KB_HAL_PIN_LOW && value != KB_HAL_PIN_HIGH)) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    fake->pin_values[pin] = value;
    return KB_HAL_OK;
}

static kb_hal_error_t pin_read(void *context, uint8_t pin,
                               kb_hal_pin_value_t *value)
{
    fake_hal_t *fake = context;
    if (fake == NULL || value == NULL || pin >= FAKE_HAL_MAX_PINS) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    *value = fake->pin_values[pin];
    if (fake->corrupt_pin_reads) {
        *value = *value == KB_HAL_PIN_LOW ? KB_HAL_PIN_HIGH : KB_HAL_PIN_LOW;
    }
    return KB_HAL_OK;
}

static kb_hal_error_t pin_pulldown(void *context, uint8_t pin, bool enabled)
{
    fake_hal_t *fake = context;
    if (fake == NULL || pin >= FAKE_HAL_MAX_PINS) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    fake->pin_pulldowns[pin] = enabled;
    return KB_HAL_OK;
}

static kb_hal_error_t now_ms(void *context, uint64_t *value)
{
    fake_hal_t *fake = context;
    if (fake == NULL || value == NULL) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    if (fake->next_time_jump_ms < 0 &&
        (uint64_t)(-fake->next_time_jump_ms) > fake->now_ms) {
        fake->now_ms = 0U;
    } else if (fake->next_time_jump_ms < 0) {
        fake->now_ms -= (uint64_t)(-fake->next_time_jump_ms);
    } else {
        fake->now_ms += (uint64_t)fake->next_time_jump_ms;
    }
    fake->next_time_jump_ms = 0;
    *value = fake->now_ms;
    return KB_HAL_OK;
}

static kb_hal_error_t store_read(void *context, kb_hal_store_slot_t slot,
                                 void *buffer, size_t capacity, size_t *length)
{
    fake_hal_t *fake = context;
    kb_hal_error_t injected;
    if (fake == NULL || buffer == NULL || length == NULL ||
        slot < KB_HAL_STORE_CONFIG_A || slot >= KB_HAL_STORE_SLOT_COUNT) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    injected = fake->next_store_read_error;
    fake->next_store_read_error = KB_HAL_OK;
    if (injected != KB_HAL_OK) {
        return injected;
    }
    if (fake->store_lengths[slot] == 0U) {
        return KB_HAL_ERR_NOT_FOUND;
    }
    if (capacity < fake->store_lengths[slot]) {
        *length = fake->store_lengths[slot];
        return KB_HAL_ERR_NO_SPACE;
    }
    memcpy(buffer, fake->stores[slot], fake->store_lengths[slot]);
    *length = fake->store_lengths[slot];
    return KB_HAL_OK;
}

static kb_hal_error_t store_write(void *context, kb_hal_store_slot_t slot,
                                  const void *buffer, size_t length)
{
    fake_hal_t *fake = context;
    kb_hal_error_t injected;
    if (fake == NULL || buffer == NULL ||
        slot < KB_HAL_STORE_CONFIG_A || slot >= KB_HAL_STORE_SLOT_COUNT) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    injected = fake->next_store_write_error;
    fake->next_store_write_error = KB_HAL_OK;
    if (injected != KB_HAL_OK) {
        return injected;
    }
    if (length > FAKE_HAL_STORE_CAPACITY) {
        return KB_HAL_ERR_NO_SPACE;
    }
    memcpy(fake->stores[slot], buffer, length);
    fake->store_lengths[slot] = length;
    return KB_HAL_OK;
}

static kb_hal_error_t store_erase(void *context, kb_hal_store_slot_t slot)
{
    fake_hal_t *fake = context;
    kb_hal_error_t injected;
    if (fake == NULL || slot < KB_HAL_STORE_CONFIG_A ||
        slot >= KB_HAL_STORE_SLOT_COUNT) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    injected = fake->next_store_erase_error;
    fake->next_store_erase_error = KB_HAL_OK;
    if (injected != KB_HAL_OK) {
        return injected;
    }
    memset(fake->stores[slot], 0, FAKE_HAL_STORE_CAPACITY);
    fake->store_lengths[slot] = 0U;
    return KB_HAL_OK;
}

static kb_hal_error_t send_buffer(fake_hal_t *fake, const void *buffer,
                                  size_t length, bool ble)
{
    kb_hal_error_t injected = ble ? fake->next_ble_error : fake->next_console_error;
    uint8_t *destination = ble ? fake->ble_report : fake->console;
    size_t *destination_length = ble ? &fake->ble_report_length : &fake->console_length;
    if (ble) {
        fake->next_ble_error = KB_HAL_OK;
    } else {
        fake->next_console_error = KB_HAL_OK;
    }
    if (injected != KB_HAL_OK) {
        return injected;
    }
    if (length > FAKE_HAL_TRANSPORT_CAPACITY) {
        return KB_HAL_ERR_NO_SPACE;
    }
    memcpy(destination, buffer, length);
    *destination_length = length;
    return KB_HAL_OK;
}

static kb_hal_error_t console_send(void *context, const void *buffer, size_t length)
{
    if (context == NULL || (buffer == NULL && length != 0U)) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    return send_buffer(context, buffer, length, false);
}

static kb_hal_error_t ble_send(void *context, const void *buffer, size_t length)
{
    if (context == NULL || (buffer == NULL && length != 0U)) {
        return KB_HAL_ERR_INVALID_ARGUMENT;
    }
    return send_buffer(context, buffer, length, true);
}

void fake_hal_reset(fake_hal_t *fake)
{
    if (fake != NULL) {
        memset(fake, 0, sizeof(*fake));
    }
}

kb_hal_ops_t fake_hal_ops(fake_hal_t *fake)
{
    kb_hal_ops_t ops = {
        .ctx = fake,
        .hal_pin_direction = pin_direction,
        .hal_pin_write = pin_write,
        .hal_pin_read = pin_read,
        .hal_pin_input_pulldown_en = pin_pulldown,
        .hal_now_ms = now_ms,
        .hal_store_read = store_read,
        .hal_store_write = store_write,
        .hal_store_erase = store_erase,
        .hal_console_send = console_send,
        .hal_ble_send_report = ble_send
    };
    return ops;
}

void fake_hal_advance(fake_hal_t *fake, uint64_t milliseconds)
{
    if (fake != NULL) {
        fake->now_ms += milliseconds;
    }
}

void fake_hal_inject_time_jump(fake_hal_t *fake, int64_t milliseconds)
{
    if (fake != NULL) {
        fake->next_time_jump_ms = milliseconds;
    }
}
