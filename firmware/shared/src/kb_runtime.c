#include "kb_runtime.h"

#include <stdio.h>
#include <string.h>

static bool runtime_gate_open(const kb_runtime_t *runtime)
{
    return runtime != NULL && runtime->boot != NULL &&
           runtime->boot->status.state == KB_BOOT_VALID &&
           runtime->boot->status.matrix_outputs_enabled &&
           kb_boot_active_config(runtime->boot) != NULL;
}

static kb_runtime_result_t send_response(kb_runtime_t *runtime, size_t length)
{
    if (length >= sizeof(runtime->response)) {
        return KB_RUNTIME_CONSOLE_ERROR;
    }
    runtime->response[length++] = '\n';
    if (runtime->hal.hal_console_send == NULL ||
        runtime->hal.hal_console_send(runtime->hal.ctx, runtime->response,
                                      length) != KB_HAL_OK) {
        return KB_RUNTIME_CONSOLE_ERROR;
    }
    return KB_RUNTIME_OK;
}

static kb_runtime_result_t send_parse_error(kb_runtime_t *runtime)
{
    static const char response[] =
        "{\"id\":\"\",\"ok\":false,\"error\":{\"code\":\"invalid_command\"," 
        "\"message\":\"command rejected\",\"details\":{}}}";
    const size_t length = sizeof(response) - 1U;
    memcpy(runtime->response, response, length);
    return send_response(runtime, length);
}

static void stop_scanner(kb_runtime_t *runtime)
{
    memset(&runtime->scanner, 0, sizeof(runtime->scanner));
    kb_events_init(&runtime->events);
    runtime->scanner_started = false;
    runtime->scanner_generation = 0U;
    runtime->have_scan_time = false;
}

static bool hid_has_active_usages(const kb_hid_state_t *hid)
{
    size_t index;
    if (hid->modifiers != 0U || hid->consumer_count != 0U) {
        return true;
    }
    for (index = 0U; index < KB_HID_MAX_KEYS; ++index) {
        if (hid->keys[index] != 0U) {
            return true;
        }
    }
    return false;
}

static kb_runtime_result_t release_hid(kb_runtime_t *runtime)
{
    kb_hid_state_t released;
    kb_hid_result_t result;
    if (!hid_has_active_usages(&runtime->hid)) {
        return KB_RUNTIME_OK;
    }
    kb_hid_init(&released);
    result = kb_hid_emit_if_changed(&released, &runtime->hal);
    runtime->hid = released;
    runtime->hid_retry_pending = result == KB_HID_HAL_ERROR;
    return result == KB_HID_OK ? KB_RUNTIME_OK : KB_RUNTIME_HID_ERROR;
}

static kb_runtime_result_t sync_scanner(kb_runtime_t *runtime)
{
    const kb_config_t *config;
    kb_scanner_result_t result;

    if (!runtime_gate_open(runtime)) {
        kb_runtime_result_t hid_result = KB_RUNTIME_OK;
        if (runtime->scanner_started) {
            hid_result = release_hid(runtime);
        }
        stop_scanner(runtime);
        return hid_result;
    }
    config = kb_boot_active_config(runtime->boot);
    if (runtime->scanner_started &&
        runtime->scanner_generation == config->generation &&
        runtime->scanner.config.crc32 == config->crc32) {
        return KB_RUNTIME_OK;
    }
    if (runtime->scanner_started && release_hid(runtime) != KB_RUNTIME_OK) {
        stop_scanner(runtime);
        return KB_RUNTIME_HID_ERROR;
    }
    stop_scanner(runtime);
    result = kb_scanner_init(config, &runtime->boot->descriptor,
                             &runtime->hal, &runtime->scanner);
    if (result != KB_SCANNER_OK) {
        stop_scanner(runtime);
        return KB_RUNTIME_SCANNER_ERROR;
    }
    runtime->scanner_started = true;
    runtime->scanner_generation = config->generation;
    return KB_RUNTIME_OK;
}

static kb_runtime_result_t dispatch_events(kb_runtime_t *runtime)
{
    kb_event_t event;
    if (runtime->hid_retry_pending) {
        const kb_hid_result_t retry =
            kb_hid_emit_if_changed(&runtime->hid, &runtime->hal);
        if (retry == KB_HID_HAL_ERROR) {
            return KB_RUNTIME_HID_ERROR;
        }
        runtime->hid_retry_pending = false;
    }
    while (kb_events_pop(&runtime->events, &event)) {
        const kb_config_t *config = kb_boot_active_config(runtime->boot);
        char key_id[16];
        kb_key_action_t entry;
        kb_action_profile_t profile;
        kb_typed_action_t action;
        kb_hid_result_t hid_result;

        if (!runtime_gate_open(runtime) || config == NULL ||
            event.switch_id >= config->switch_count) {
            continue;
        }
        (void)snprintf(key_id, sizeof(key_id), "MX-%02u-%02u",
                       (unsigned)event.row, (unsigned)event.col);
        entry.key_id = key_id;
        entry.desktop_action = &config->switches[event.switch_id].action;
        profile.key_actions = &entry;
        profile.key_action_count = 1U;
        if (kb_action_resolve(&profile, key_id,
                              event.type == KB_EVENT_KEY_DOWN,
                              &action) != KB_ACTION_OK) {
            continue;
        }
        hid_result = kb_hid_apply_and_emit(&runtime->hid, &runtime->hal,
                                           &action);
        if (hid_result != KB_HID_OK && hid_result != KB_HID_NO_CHANGE &&
            hid_result != KB_HID_ROLLOVER) {
            runtime->hid_retry_pending = hid_result == KB_HID_HAL_ERROR;
            return KB_RUNTIME_HID_ERROR;
        }
    }
    return KB_RUNTIME_OK;
}

static kb_runtime_result_t pump_scanner(kb_runtime_t *runtime, uint64_t now_ms)
{
    bool due;
    size_t produced = 0U;
    kb_runtime_result_t result = sync_scanner(runtime);

    if (result != KB_RUNTIME_OK || !runtime->scanner_started) {
        return result;
    }
    due = !runtime->have_scan_time || now_ms < runtime->last_scan_ms ||
          now_ms - runtime->last_scan_ms >= runtime->scan_period_ms;
    if (due) {
        if (kb_scanner_process(&runtime->scanner, &runtime->hal, now_ms,
                               &runtime->events, &produced) != KB_SCANNER_OK) {
            return KB_RUNTIME_SCANNER_ERROR;
        }
        runtime->last_scan_ms = now_ms;
        runtime->have_scan_time = true;
    }
    return dispatch_events(runtime);
}

static kb_runtime_result_t pump_console(kb_runtime_t *runtime, uint64_t now_ms,
                                        const uint8_t *input,
                                        size_t input_length, size_t *consumed)
{
    size_t offset = 0U;

    if (runtime->have_console_time &&
        (runtime->reader.length != 0U || runtime->reader.discarding_overlong)) {
        if (now_ms < runtime->last_console_byte_ms) {
            runtime->last_console_byte_ms = now_ms;
        } else if (now_ms - runtime->last_console_byte_ms >=
                   KB_RUNTIME_CONSOLE_TIMEOUT_MS) {
            kb_protocol_reader_init(&runtime->reader);
            runtime->have_console_time = false;
            if (send_parse_error(runtime) != KB_RUNTIME_OK) {
                return KB_RUNTIME_CONSOLE_ERROR;
            }
        }
    }
    while (offset < input_length) {
        kb_protocol_request_t request;
        kb_protocol_parse_error_t error = KB_PROTOCOL_PARSE_OK;
        kb_protocol_read_result_t read_result;
        size_t used = 0U;
        size_t response_length = 0U;

        read_result = kb_protocol_read_one_cmd(
            &runtime->reader, input + offset, input_length - offset, &used,
            &request, &error);
        offset += used;
        runtime->last_console_byte_ms = now_ms;
        runtime->have_console_time = runtime->reader.length != 0U ||
                                     runtime->reader.discarding_overlong;
        if (read_result == KB_PROTOCOL_READ_MORE) {
            break;
        }
        runtime->have_console_time = false;
        if (read_result == KB_PROTOCOL_READ_ERROR) {
            (void)error;
            if (send_parse_error(runtime) != KB_RUNTIME_OK) {
                return KB_RUNTIME_CONSOLE_ERROR;
            }
            continue;
        }
        (void)kb_protocol_apply_cmd(&runtime->protocol, &request,
                                    runtime->response,
                                    sizeof(runtime->response) - 1U,
                                    &response_length);
        if (response_length == 0U ||
            send_response(runtime, response_length) != KB_RUNTIME_OK) {
            return KB_RUNTIME_CONSOLE_ERROR;
        }
        if (sync_scanner(runtime) != KB_RUNTIME_OK) {
            return KB_RUNTIME_SCANNER_ERROR;
        }
    }
    if (consumed != NULL) {
        *consumed = offset;
    }
    return KB_RUNTIME_OK;
}

kb_runtime_result_t kb_runtime_init(kb_runtime_t *runtime, kb_boot_t *boot,
                                    const kb_hal_ops_t *hal,
                                    uint32_t scan_period_ms)
{
    if (runtime == NULL || boot == NULL || hal == NULL ||
        scan_period_ms == 0U) {
        return KB_RUNTIME_INVALID_ARGUMENT;
    }
    memset(runtime, 0, sizeof(*runtime));
    runtime->boot = boot;
    runtime->hal = *hal;
    runtime->scan_period_ms = scan_period_ms;
    kb_events_init(&runtime->events);
    kb_hid_init(&runtime->hid);
    kb_protocol_context_init(&runtime->protocol, boot, &runtime->events);
    kb_protocol_reader_init(&runtime->reader);
    return KB_RUNTIME_OK;
}

kb_runtime_result_t kb_runtime_poll(kb_runtime_t *runtime, uint64_t now_ms,
                                    const uint8_t *input, size_t input_length,
                                    size_t *consumed)
{
    kb_runtime_result_t scan_result;
    kb_runtime_result_t console_result;
    if (consumed != NULL) {
        *consumed = 0U;
    }
    if (runtime == NULL || (input == NULL && input_length != 0U)) {
        return KB_RUNTIME_INVALID_ARGUMENT;
    }
    scan_result = pump_scanner(runtime, now_ms);
    console_result = pump_console(runtime, now_ms, input, input_length,
                                  consumed);
    return console_result != KB_RUNTIME_OK ? console_result : scan_result;
}

bool kb_runtime_scanner_started(const kb_runtime_t *runtime)
{
    return runtime != NULL && runtime->scanner_started;
}
