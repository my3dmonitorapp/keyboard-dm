#ifndef KB_PROTOCOL_H
#define KB_PROTOCOL_H

#include "kb_config.h"

#include <stddef.h>
#include <stdint.h>

#define KB_PROTOCOL_VERSION_STRING "0.1"
#define KB_PROTOCOL_ACTIVE_VERSION 1U
#define KB_PROTOCOL_MAX_LINE_BYTES 1536U
#define KB_PROTOCOL_MAX_ID_BYTES 64U
#define KB_PROTOCOL_MAX_RAW_CHUNK_BYTES 1024U
#define KB_PROTOCOL_MAX_REBOOT_DELAY_MS 5000U

#define KB_PROTOCOL_FIELD_ID "id"
#define KB_PROTOCOL_FIELD_CMD "cmd"
#define KB_PROTOCOL_FIELD_PARAMS "params"
#define KB_PROTOCOL_FIELD_EVENT "event"
#define KB_PROTOCOL_FIELD_OK "ok"
#define KB_PROTOCOL_FIELD_RESULT "result"
#define KB_PROTOCOL_FIELD_ERROR "error"

#define KB_PROTOCOL_CMD_VERSION "version"
#define KB_PROTOCOL_CMD_PING "ping"
#define KB_PROTOCOL_CMD_CONFIG_UPLOAD "config_upload"
#define KB_PROTOCOL_CMD_CONFIG_GET "config_get"
#define KB_PROTOCOL_CMD_CONFIG_STATUS "config_status"
#define KB_PROTOCOL_CMD_KEY_EVENT "key_event"
#define KB_PROTOCOL_CMD_GPIO_TEST "gpio_test"
#define KB_PROTOCOL_CMD_FACTORY_RESET "factory_reset"
#define KB_PROTOCOL_CMD_REBOOT "reboot"

typedef enum {
    KB_PROTOCOL_PARSE_OK = 0,
    KB_PROTOCOL_PARSE_EMPTY,
    KB_PROTOCOL_PARSE_OVERLONG,
    KB_PROTOCOL_PARSE_BAD_UTF8,
    KB_PROTOCOL_PARSE_MALFORMED_JSON,
    KB_PROTOCOL_PARSE_BAD_ENVELOPE,
    KB_PROTOCOL_PARSE_UNKNOWN_COMMAND,
    KB_PROTOCOL_PARSE_BAD_PARAMS
} kb_protocol_parse_error_t;

typedef enum {
    KB_PROTOCOL_COMMAND_VERSION = 0,
    KB_PROTOCOL_COMMAND_PING,
    KB_PROTOCOL_COMMAND_CONFIG_UPLOAD,
    KB_PROTOCOL_COMMAND_CONFIG_GET,
    KB_PROTOCOL_COMMAND_CONFIG_STATUS,
    KB_PROTOCOL_COMMAND_KEY_EVENT,
    KB_PROTOCOL_COMMAND_GPIO_TEST,
    KB_PROTOCOL_COMMAND_FACTORY_RESET,
    KB_PROTOCOL_COMMAND_REBOOT
} kb_protocol_command_type_t;

typedef struct {
    char id[KB_PROTOCOL_MAX_ID_BYTES + 1U];
    kb_protocol_command_type_t command;
    const char *params_json;
    size_t params_length;
} kb_protocol_request_t;

typedef struct kb_protocol_context kb_protocol_context_t;

/* Implemented with the F2-T3 protocol/state machine. */
kb_protocol_parse_error_t kb_protocol_parse_line(const char *line, size_t length,
                                                  kb_protocol_request_t *request);
int kb_protocol_apply(kb_protocol_context_t *context,
                      const kb_protocol_request_t *request, char *response,
                      size_t capacity, size_t *length);

#endif
