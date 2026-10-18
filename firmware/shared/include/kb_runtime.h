#ifndef KB_RUNTIME_H
#define KB_RUNTIME_H

#include "kb_boot.h"
#include "kb_events.h"
#include "kb_hid.h"
#include "kb_protocol.h"
#include "kb_scanner.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KB_RUNTIME_DEFAULT_SCAN_PERIOD_MS 1U
#define KB_RUNTIME_CONSOLE_TIMEOUT_MS 1000U
#define KB_RUNTIME_RESPONSE_BYTES (KB_PROTOCOL_MAX_UPLOAD_BYTES + 512U)

typedef enum {
    KB_RUNTIME_OK = 0,
    KB_RUNTIME_INVALID_ARGUMENT,
    KB_RUNTIME_SCANNER_ERROR,
    KB_RUNTIME_HID_ERROR,
    KB_RUNTIME_CONSOLE_ERROR
} kb_runtime_result_t;

typedef struct {
    kb_boot_t *boot;
    kb_hal_ops_t hal;
    kb_scanner_t scanner;
    kb_event_ring_t events;
    kb_hid_state_t hid;
    kb_protocol_context_t protocol;
    kb_protocol_reader_t reader;
    uint32_t scan_period_ms;
    uint32_t scanner_generation;
    uint64_t last_scan_ms;
    uint64_t last_console_byte_ms;
    bool scanner_started;
    bool have_scan_time;
    bool have_console_time;
    bool hid_retry_pending;
    char response[KB_RUNTIME_RESPONSE_BYTES];
} kb_runtime_t;

/* Initialization never touches GPIO. The boot/config gate is evaluated by
 * every poll before scanner initialization or matrix access. */
kb_runtime_result_t kb_runtime_init(kb_runtime_t *runtime, kb_boot_t *boot,
                                    const kb_hal_ops_t *hal,
                                    uint32_t scan_period_ms);

/* Pumps one deterministic runtime iteration. Input may be split at arbitrary
 * byte boundaries. consumed may be NULL; otherwise it receives bytes handled. */
kb_runtime_result_t kb_runtime_poll(kb_runtime_t *runtime, uint64_t now_ms,
                                    const uint8_t *input, size_t input_length,
                                    size_t *consumed);

bool kb_runtime_scanner_started(const kb_runtime_t *runtime);

#endif
