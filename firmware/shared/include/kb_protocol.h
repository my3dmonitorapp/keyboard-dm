#ifndef KB_PROTOCOL_H
#define KB_PROTOCOL_H

#include "kb_boot.h"
#include "kb_events.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KB_PROTOCOL_VERSION_STRING "0.1"
#define KB_PROTOCOL_ACTIVE_VERSION 1U
#define KB_PROTOCOL_MAX_LINE_BYTES 1536U
#define KB_PROTOCOL_MAX_ID_BYTES 64U
#define KB_PROTOCOL_MAX_RAW_CHUNK_BYTES 1024U
#define KB_PROTOCOL_MAX_UPLOAD_BYTES 8192U
#define KB_PROTOCOL_MAX_REBOOT_DELAY_MS 5000U
#define KB_PROTOCOL_MAX_GPIO_SAMPLES 16U
#define KB_PROTOCOL_UPLOAD_ID_BYTES 32U

#define KB_PROTOCOL_FIELD_ID "id"
#define KB_PROTOCOL_FIELD_CMD "cmd"
#define KB_PROTOCOL_FIELD_PARAMS "params"
#define KB_PROTOCOL_FIELD_EVENT "event"
#define KB_PROTOCOL_FIELD_OK "ok"
#define KB_PROTOCOL_FIELD_RESULT "result"
#define KB_PROTOCOL_FIELD_ERROR "error"
#define KB_PROTOCOL_FIELD_CRC32 "crc32"

#define KB_PROTOCOL_CMD_VERSION "version"
#define KB_PROTOCOL_CMD_PING "ping"
#define KB_PROTOCOL_CMD_CONFIG_UPLOAD "config_upload"
#define KB_PROTOCOL_CMD_CONFIG_COMMIT "config_commit"
#define KB_PROTOCOL_CMD_CONFIG_GET "config_get"
#define KB_PROTOCOL_CMD_CONFIG_STATUS "config_status"
#define KB_PROTOCOL_CMD_KEY_EVENT "key_event"
#define KB_PROTOCOL_CMD_GPIO_TEST "gpio_test"
#define KB_PROTOCOL_CMD_FACTORY_RESET "factory_reset"
#define KB_PROTOCOL_CMD_BOOT_STATUS "boot_status"
#define KB_PROTOCOL_CMD_REBOOT "reboot"

typedef enum {
    KB_PROTOCOL_PARSE_OK = 0,
    KB_PROTOCOL_PARSE_EMPTY,
    KB_PROTOCOL_PARSE_OVERLONG,
    KB_PROTOCOL_PARSE_BAD_UTF8,
    KB_PROTOCOL_PARSE_MALFORMED_JSON,
    KB_PROTOCOL_PARSE_BAD_ENVELOPE,
    KB_PROTOCOL_PARSE_UNKNOWN_COMMAND,
    KB_PROTOCOL_PARSE_BAD_PARAMS,
    KB_PROTOCOL_PARSE_CRC_MISSING,
    KB_PROTOCOL_PARSE_CRC_MISMATCH
} kb_protocol_parse_error_t;

typedef enum {
    KB_PROTOCOL_COMMAND_VERSION = 0,
    KB_PROTOCOL_COMMAND_PING,
    KB_PROTOCOL_COMMAND_CONFIG_UPLOAD,
    KB_PROTOCOL_COMMAND_CONFIG_COMMIT,
    KB_PROTOCOL_COMMAND_CONFIG_GET,
    KB_PROTOCOL_COMMAND_CONFIG_STATUS,
    KB_PROTOCOL_COMMAND_KEY_EVENT,
    KB_PROTOCOL_COMMAND_GPIO_TEST,
    KB_PROTOCOL_COMMAND_FACTORY_RESET,
    KB_PROTOCOL_COMMAND_BOOT_STATUS,
    KB_PROTOCOL_COMMAND_REBOOT
} kb_protocol_command_type_t;

typedef enum {
    KB_PROTOCOL_UPLOAD_START = 0,
    KB_PROTOCOL_UPLOAD_CHUNK,
    KB_PROTOCOL_UPLOAD_COMMIT,
    KB_PROTOCOL_UPLOAD_ABORT
} kb_protocol_upload_phase_t;

typedef enum {
    KB_PROTOCOL_KEY_EVENT_ENABLE = 0,
    KB_PROTOCOL_KEY_EVENT_INJECT
} kb_protocol_key_event_mode_t;

typedef struct {
    kb_protocol_upload_phase_t phase;
    char upload_id[KB_PROTOCOL_UPLOAD_ID_BYTES + 1U];
    size_t total_bytes;
    uint32_t config_crc32;
    uint32_t seq;
    char data[((KB_PROTOCOL_MAX_RAW_CHUNK_BYTES + 2U) / 3U) * 4U + 1U];
} kb_protocol_upload_args_t;

typedef struct {
    char id[KB_PROTOCOL_MAX_ID_BYTES + 1U];
    kb_protocol_command_type_t command;
    char params_json[KB_PROTOCOL_MAX_LINE_BYTES + 1U];
    size_t params_length;
    uint32_t crc32;
    union {
        struct { char nonce[65]; bool has_nonce; } ping;
        kb_protocol_upload_args_t upload;
        struct { uint32_t config_crc32; bool has_crc32; } commit;
        struct { bool last_good; } config_get;
        struct {
            kb_protocol_key_event_mode_t mode;
            bool enabled;
            uint8_t row;
            uint8_t col;
            bool pressed;
            uint64_t timestamp_ms;
        } key_event;
        struct { uint8_t pin; uint8_t samples; uint8_t pull; } gpio_test;
        struct { bool confirmed; } factory_reset;
        struct { uint16_t delay_ms; } reboot;
    } args;
} kb_protocol_request_t;

typedef enum {
    KB_PROTOCOL_READ_MORE = 0,
    KB_PROTOCOL_READ_COMMAND,
    KB_PROTOCOL_READ_ERROR
} kb_protocol_read_result_t;

typedef struct {
    char line[KB_PROTOCOL_MAX_LINE_BYTES + 1U];
    size_t length;
    bool discarding_overlong;
} kb_protocol_reader_t;

typedef enum {
    KB_PROTOCOL_APPLY_OK = 0,
    KB_PROTOCOL_APPLY_INVALID_ARGUMENT,
    KB_PROTOCOL_APPLY_BAD_STATE,
    KB_PROTOCOL_APPLY_BAD_CONFIG,
    KB_PROTOCOL_APPLY_HAL_ERROR,
    KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL
} kb_protocol_apply_result_t;

typedef struct kb_protocol_context {
    kb_boot_t *boot;
    kb_event_ring_t *events;
    bool key_events_enabled;
    bool upload_active;
    char upload_id[KB_PROTOCOL_UPLOAD_ID_BYTES + 1U];
    size_t upload_total;
    size_t upload_length;
    uint32_t upload_expected_crc32;
    uint32_t upload_next_seq;
    uint8_t upload_bytes[KB_PROTOCOL_MAX_UPLOAD_BYTES];
} kb_protocol_context_t;

void kb_protocol_context_init(kb_protocol_context_t *context, kb_boot_t *boot,
                              kb_event_ring_t *events);
void kb_protocol_reader_init(kb_protocol_reader_t *reader);

/* CRC32 covers prefix bytes followed by the closing object brace. */
uint32_t kb_protocol_line_crc32(const char *prefix, size_t prefix_length);
kb_protocol_parse_error_t kb_protocol_parse_line(const char *line, size_t length,
                                                  kb_protocol_request_t *request);
kb_protocol_read_result_t kb_protocol_read_one_cmd(
    kb_protocol_reader_t *reader, const uint8_t *bytes, size_t length,
    size_t *consumed, kb_protocol_request_t *request,
    kb_protocol_parse_error_t *error);

kb_protocol_apply_result_t kb_protocol_apply_cmd(
    kb_protocol_context_t *context, const kb_protocol_request_t *request,
    char *response, size_t capacity, size_t *length);
kb_protocol_apply_result_t kb_protocol_process_line(
    kb_protocol_context_t *context, const char *line, size_t line_length,
    char *response, size_t capacity, size_t *response_length);

/* Compatibility entry point retained from T1. */
int kb_protocol_apply(kb_protocol_context_t *context,
                      const kb_protocol_request_t *request, char *response,
                      size_t capacity, size_t *length);

#endif
