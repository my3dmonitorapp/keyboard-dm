#include "kb_protocol.h"

#include "kb_crc32.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define JSON_TOKENS 128U

typedef enum { JT_OBJECT = 1, JT_ARRAY, JT_STRING, JT_PRIMITIVE } jt_type_t;
typedef struct { jt_type_t type; int start; int end; int parent; } jt_t;
typedef struct { const char *text; size_t length; jt_t tokens[JSON_TOKENS]; size_t count; } jd_t;

static bool utf8_valid(const uint8_t *data, size_t length)
{
    size_t i = 0U;
    while (i < length) {
        uint8_t c = data[i++];
        size_t continuation;
        uint32_t value;
        if (c < 0x80U) continue;
        if (c >= 0xc2U && c <= 0xdfU) { continuation = 1U; value = c & 0x1fU; }
        else if (c >= 0xe0U && c <= 0xefU) { continuation = 2U; value = c & 0x0fU; }
        else if (c >= 0xf0U && c <= 0xf4U) { continuation = 3U; value = c & 0x07U; }
        else return false;
        if (length - i < continuation) return false;
        while (continuation-- != 0U) {
            if ((data[i] & 0xc0U) != 0x80U) return false;
            value = (value << 6U) | (data[i++] & 0x3fU);
        }
        if (value > 0x10ffffU || (value >= 0xd800U && value <= 0xdfffU))
            return false;
    }
    return true;
}

static bool json_parse(jd_t *doc, const char *text, size_t length)
{
    int parent = -1;
    size_t i;
    memset(doc, 0, sizeof(*doc));
    doc->text = text;
    doc->length = length;
    for (i = 0U; i < length;) {
        const unsigned char c = (unsigned char)text[i];
        jt_t *token;
        if (c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == ':' || c == ',') { ++i; continue; }
        if (c == '{' || c == '[') {
            if (doc->count == JSON_TOKENS) return false;
            token = &doc->tokens[doc->count++];
            token->type = c == '{' ? JT_OBJECT : JT_ARRAY;
            token->start = (int)i;
            token->end = -1;
            token->parent = parent;
            parent = (int)(doc->count - 1U);
            ++i;
            continue;
        }
        if (c == '}' || c == ']') {
            if (parent < 0 || doc->tokens[parent].type != (c == '}' ? JT_OBJECT : JT_ARRAY)) return false;
            doc->tokens[parent].end = (int)(++i);
            parent = doc->tokens[parent].parent;
            continue;
        }
        if (c == '"') {
            size_t start = ++i;
            if (doc->count == JSON_TOKENS) return false;
            while (i < length && text[i] != '"') {
                if ((unsigned char)text[i] < 0x20U) return false;
                if (text[i] == '\\') {
                    ++i;
                    if (i >= length || strchr("\"\\/bfnrt", text[i]) == NULL) return false;
                }
                ++i;
            }
            if (i == length) return false;
            token = &doc->tokens[doc->count++];
            token->type = JT_STRING; token->start = (int)start; token->end = (int)i; token->parent = parent;
            ++i;
            continue;
        }
        {
            const size_t start = i;
            if (doc->count == JSON_TOKENS) return false;
            while (i < length && strchr(" \t\r\n,]}:", text[i]) == NULL) ++i;
            if (i == start) return false;
            token = &doc->tokens[doc->count++];
            token->type = JT_PRIMITIVE; token->start = (int)start; token->end = (int)i; token->parent = parent;
        }
    }
    return parent == -1 && doc->count != 0U && doc->tokens[0].type == JT_OBJECT &&
           doc->tokens[0].end == (int)length;
}

static bool token_eq(const jd_t *doc, size_t token, const char *value)
{
    const jt_t *item = &doc->tokens[token];
    const size_t length = (size_t)(item->end - item->start);
    return strlen(value) == length && memcmp(doc->text + item->start, value, length) == 0;
}

static int object_field(const jd_t *doc, size_t object, const char *name)
{
    size_t i;
    for (i = object + 1U; i + 1U < doc->count; ++i) {
        if (doc->tokens[i].parent == (int)object && doc->tokens[i].type == JT_STRING && token_eq(doc, i, name))
            return doc->tokens[i + 1U].parent == (int)object ? (int)(i + 1U) : -1;
    }
    return -1;
}

static bool fields_only(const jd_t *doc, size_t object,
                        const char *const *names, size_t name_count)
{
    size_t i;
    bool expecting_key = true;
    for (i = object + 1U; i < doc->count; ++i) {
        size_t n;
        bool known = false;
        if (doc->tokens[i].parent != (int)object) continue;
        if (!expecting_key) { expecting_key = true; continue; }
        if (doc->tokens[i].type != JT_STRING) return false;
        for (n = 0U; n < name_count; ++n) if (token_eq(doc, i, names[n])) { known = true; break; }
        if (!known) return false;
        expecting_key = false;
    }
    return expecting_key;
}

static bool copy_string(const jd_t *doc, int token, char *out, size_t capacity)
{
    size_t length;
    if (token < 0 || doc->tokens[token].type != JT_STRING) return false;
    length = (size_t)(doc->tokens[token].end - doc->tokens[token].start);
    if (length == 0U || length >= capacity || memchr(doc->text + doc->tokens[token].start, '\\', length) != NULL) return false;
    memcpy(out, doc->text + doc->tokens[token].start, length);
    out[length] = '\0';
    return true;
}

static bool uint_value(const jd_t *doc, int token, uint64_t max, uint64_t *out)
{
    uint64_t value = 0U;
    int i;
    if (token < 0 || doc->tokens[token].type != JT_PRIMITIVE || doc->tokens[token].start == doc->tokens[token].end) return false;
    for (i = doc->tokens[token].start; i < doc->tokens[token].end; ++i) {
        const char c = doc->text[i];
        if (c < '0' || c > '9' || value > (max - (uint64_t)(c - '0')) / 10U) return false;
        value = value * 10U + (uint64_t)(c - '0');
    }
    *out = value;
    return true;
}

static bool bool_value(const jd_t *doc, int token, bool *out)
{
    if (token < 0 || doc->tokens[token].type != JT_PRIMITIVE) return false;
    if (token_eq(doc, (size_t)token, "true")) { *out = true; return true; }
    if (token_eq(doc, (size_t)token, "false")) { *out = false; return true; }
    return false;
}

static kb_protocol_parse_error_t parse_params(const char *cmd, const char *json,
                                               size_t length,
                                               kb_protocol_request_t *request)
{
    jd_t doc;
    int token;
    uint64_t number;
    static const char *const upload_fields[] = {"phase", "upload_id", "encoding", "total_bytes", "crc32", "seq", "data"};
    if (!json_parse(&doc, json, length)) return KB_PROTOCOL_PARSE_BAD_PARAMS;
    if (strcmp(cmd, KB_PROTOCOL_CMD_CONFIG_UPLOAD) == 0) {
        char phase[8];
        if (!fields_only(&doc, 0U, upload_fields, 7U))
            return KB_PROTOCOL_PARSE_BAD_PARAMS;
        if (!copy_string(&doc, object_field(&doc, 0U, "phase"), phase, sizeof(phase)) ||
            !copy_string(&doc, object_field(&doc, 0U, "upload_id"), request->args.upload.upload_id, sizeof(request->args.upload.upload_id)))
            return KB_PROTOCOL_PARSE_BAD_PARAMS;
        if (strcmp(phase, "start") == 0) {
            char encoding[8];
            request->args.upload.phase = KB_PROTOCOL_UPLOAD_START;
            if (!copy_string(&doc, object_field(&doc, 0U, "encoding"), encoding, sizeof(encoding)) || strcmp(encoding, "base64") != 0 ||
                !uint_value(&doc, object_field(&doc, 0U, "total_bytes"), KB_PROTOCOL_MAX_UPLOAD_BYTES, &number) || number == 0U)
                return KB_PROTOCOL_PARSE_BAD_PARAMS;
            request->args.upload.total_bytes = (size_t)number;
            if (!uint_value(&doc, object_field(&doc, 0U, "crc32"), UINT32_MAX, &number)) return KB_PROTOCOL_PARSE_CRC_MISSING;
            request->args.upload.config_crc32 = (uint32_t)number;
        } else if (strcmp(phase, "chunk") == 0) {
            request->args.upload.phase = KB_PROTOCOL_UPLOAD_CHUNK;
            if (!uint_value(&doc, object_field(&doc, 0U, "seq"), UINT32_MAX, &number) ||
                !copy_string(&doc, object_field(&doc, 0U, "data"), request->args.upload.data, sizeof(request->args.upload.data)))
                return KB_PROTOCOL_PARSE_BAD_PARAMS;
            request->args.upload.seq = (uint32_t)number;
        } else if (strcmp(phase, "commit") == 0) request->args.upload.phase = KB_PROTOCOL_UPLOAD_COMMIT;
        else if (strcmp(phase, "abort") == 0) request->args.upload.phase = KB_PROTOCOL_UPLOAD_ABORT;
        else return KB_PROTOCOL_PARSE_BAD_PARAMS;
        return KB_PROTOCOL_PARSE_OK;
    }
    if (strcmp(cmd, KB_PROTOCOL_CMD_CONFIG_COMMIT) == 0) {
        static const char *const names[] = {"upload_id", "crc32"};
        if (!fields_only(&doc, 0U, names, 2U)) return KB_PROTOCOL_PARSE_BAD_PARAMS;
        token = object_field(&doc, 0U, "crc32");
        if (token >= 0) {
            if (!uint_value(&doc, token, UINT32_MAX, &number)) return KB_PROTOCOL_PARSE_BAD_PARAMS;
            request->args.commit.config_crc32 = (uint32_t)number;
            request->args.commit.has_crc32 = true;
        }
        return KB_PROTOCOL_PARSE_OK;
    }
    if (strcmp(cmd, KB_PROTOCOL_CMD_KEY_EVENT) == 0) {
        static const char *const names[] = {"enabled"};
        if (!fields_only(&doc, 0U, names, 1U) || !bool_value(&doc, object_field(&doc, 0U, "enabled"), &request->args.key_event.enabled))
            return KB_PROTOCOL_PARSE_BAD_PARAMS;
        request->args.key_event.mode = KB_PROTOCOL_KEY_EVENT_ENABLE;
        return KB_PROTOCOL_PARSE_OK;
    }
    if (strcmp(cmd, KB_PROTOCOL_CMD_FACTORY_RESET) == 0) {
        static const char *const names[] = {"confirm"};
        char confirm[32];
        if (!fields_only(&doc, 0U, names, 1U) || !copy_string(&doc, object_field(&doc, 0U, "confirm"), confirm, sizeof(confirm)) ||
            strcmp(confirm, "ERASE_CONFIG_AND_BONDS") != 0) return KB_PROTOCOL_PARSE_BAD_PARAMS;
        request->args.factory_reset.confirmed = true;
        return KB_PROTOCOL_PARSE_OK;
    }
    if (strcmp(cmd, KB_PROTOCOL_CMD_CONFIG_GET) == 0) {
        static const char *const names[] = {"source"};
        char source[16];
        if (!fields_only(&doc, 0U, names, 1U)) return KB_PROTOCOL_PARSE_BAD_PARAMS;
        token = object_field(&doc, 0U, "source");
        if (token >= 0) {
            if (!copy_string(&doc, token, source, sizeof(source)) || (strcmp(source, "active") != 0 && strcmp(source, "last_good") != 0)) return KB_PROTOCOL_PARSE_BAD_PARAMS;
            request->args.config_get.last_good = strcmp(source, "last_good") == 0;
        }
        return KB_PROTOCOL_PARSE_OK;
    }
    /* The remaining implemented status/version commands require {}. */
    if (doc.count != 1U) return KB_PROTOCOL_PARSE_BAD_PARAMS;
    return KB_PROTOCOL_PARSE_OK;
}

void kb_protocol_context_init(kb_protocol_context_t *context, kb_boot_t *boot,
                              kb_event_ring_t *events)
{
    if (context != NULL) { memset(context, 0, sizeof(*context)); context->boot = boot; context->events = events; }
}

void kb_protocol_reader_init(kb_protocol_reader_t *reader)
{
    if (reader != NULL) memset(reader, 0, sizeof(*reader));
}

uint32_t kb_protocol_line_crc32(const char *prefix, size_t prefix_length)
{
    char bytes[KB_PROTOCOL_MAX_LINE_BYTES + 1U];
    if (prefix == NULL && prefix_length != 0U) return 0U;
    if (prefix_length > KB_PROTOCOL_MAX_LINE_BYTES) return 0U;
    if (prefix_length != 0U) memcpy(bytes, prefix, prefix_length);
    bytes[prefix_length] = '}';
    return kb_crc32(bytes, prefix_length + 1U);
}

kb_protocol_parse_error_t kb_protocol_parse_line(const char *line, size_t length,
                                                  kb_protocol_request_t *request)
{
    jd_t doc;
    kb_protocol_request_t parsed;
    int id, cmd, params, version;
    char command[32];
    static const char *const envelope[] = {"id", "cmd", "params", "version", "crc32"};
    uint64_t number;
    if (line == NULL || request == NULL) return KB_PROTOCOL_PARSE_BAD_ENVELOPE;
    while (length != 0U && (line[length - 1U] == '\n' || line[length - 1U] == '\r')) --length;
    if (length == 0U) return KB_PROTOCOL_PARSE_EMPTY;
    if (length > KB_PROTOCOL_MAX_LINE_BYTES) return KB_PROTOCOL_PARSE_OVERLONG;
    if (!utf8_valid((const uint8_t *)line, length)) return KB_PROTOCOL_PARSE_BAD_UTF8;
    if (!json_parse(&doc, line, length)) return KB_PROTOCOL_PARSE_MALFORMED_JSON;
    if (!fields_only(&doc, 0U, envelope, 5U)) return KB_PROTOCOL_PARSE_BAD_ENVELOPE;
    memset(&parsed, 0, sizeof(parsed));
    id = object_field(&doc, 0U, "id"); cmd = object_field(&doc, 0U, "cmd"); params = object_field(&doc, 0U, "params");
    if (!copy_string(&doc, id, parsed.id, sizeof(parsed.id)) ||
        !copy_string(&doc, cmd, command, sizeof(command)) || params < 0 || doc.tokens[params].type != JT_OBJECT)
        return KB_PROTOCOL_PARSE_BAD_ENVELOPE;
    version = object_field(&doc, 0U, "version");
    if (version >= 0 && !((doc.tokens[version].type == JT_STRING && token_eq(&doc, (size_t)version, KB_PROTOCOL_VERSION_STRING)) ||
        (uint_value(&doc, version, UINT32_MAX, &number) && number == KB_PROTOCOL_ACTIVE_VERSION)))
        return KB_PROTOCOL_PARSE_BAD_ENVELOPE;
#define COMMAND(name, value) if (strcmp(command, name) == 0) parsed.command = value; else
    COMMAND(KB_PROTOCOL_CMD_VERSION, KB_PROTOCOL_COMMAND_VERSION)
    COMMAND(KB_PROTOCOL_CMD_PING, KB_PROTOCOL_COMMAND_PING)
    COMMAND(KB_PROTOCOL_CMD_CONFIG_UPLOAD, KB_PROTOCOL_COMMAND_CONFIG_UPLOAD)
    COMMAND(KB_PROTOCOL_CMD_CONFIG_COMMIT, KB_PROTOCOL_COMMAND_CONFIG_COMMIT)
    COMMAND(KB_PROTOCOL_CMD_CONFIG_GET, KB_PROTOCOL_COMMAND_CONFIG_GET)
    COMMAND(KB_PROTOCOL_CMD_CONFIG_STATUS, KB_PROTOCOL_COMMAND_CONFIG_STATUS)
    COMMAND(KB_PROTOCOL_CMD_KEY_EVENT, KB_PROTOCOL_COMMAND_KEY_EVENT)
    COMMAND(KB_PROTOCOL_CMD_FACTORY_RESET, KB_PROTOCOL_COMMAND_FACTORY_RESET)
    COMMAND(KB_PROTOCOL_CMD_BOOT_STATUS, KB_PROTOCOL_COMMAND_BOOT_STATUS)
    return KB_PROTOCOL_PARSE_UNKNOWN_COMMAND;
#undef COMMAND
    parsed.params_length = (size_t)(doc.tokens[params].end - doc.tokens[params].start);
    if (parsed.params_length > KB_PROTOCOL_MAX_LINE_BYTES) return KB_PROTOCOL_PARSE_BAD_PARAMS;
    memcpy(parsed.params_json, line + doc.tokens[params].start, parsed.params_length);
    parsed.params_json[parsed.params_length] = '\0';
    {
        const kb_protocol_parse_error_t result = parse_params(command, parsed.params_json, parsed.params_length, &parsed);
        if (result != KB_PROTOCOL_PARSE_OK) return result;
    }
    *request = parsed;
    return KB_PROTOCOL_PARSE_OK;
}

kb_protocol_read_result_t kb_protocol_read_one_cmd(
    kb_protocol_reader_t *reader, const uint8_t *bytes, size_t length,
    size_t *consumed, kb_protocol_request_t *request,
    kb_protocol_parse_error_t *error)
{
    size_t i;
    if (reader == NULL || bytes == NULL || consumed == NULL || request == NULL || error == NULL) return KB_PROTOCOL_READ_ERROR;
    *consumed = 0U;
    for (i = 0U; i < length; ++i) {
        *consumed = i + 1U;
        if (bytes[i] == '\n') {
            kb_protocol_parse_error_t result;
            if (reader->discarding_overlong) { kb_protocol_reader_init(reader); *error = KB_PROTOCOL_PARSE_OVERLONG; return KB_PROTOCOL_READ_ERROR; }
            result = kb_protocol_parse_line(reader->line, reader->length, request);
            kb_protocol_reader_init(reader);
            *error = result;
            return result == KB_PROTOCOL_PARSE_OK ? KB_PROTOCOL_READ_COMMAND : KB_PROTOCOL_READ_ERROR;
        }
        if (reader->discarding_overlong) continue;
        if (reader->length == KB_PROTOCOL_MAX_LINE_BYTES) { reader->discarding_overlong = true; continue; }
        reader->line[reader->length++] = (char)bytes[i];
    }
    return KB_PROTOCOL_READ_MORE;
}

static bool response_write(char *response, size_t capacity, size_t *length,
                           const char *format, ...)
{
    int count;
    va_list args;
    if (response == NULL || length == NULL || capacity == 0U) return false;
    va_start(args, format); count = vsnprintf(response, capacity, format, args); va_end(args);
    if (count < 0 || (size_t)count >= capacity) { response[0] = '\0'; *length = 0U; return false; }
    *length = (size_t)count;
    return true;
}

static kb_protocol_apply_result_t error_response(const char *id, const char *code,
                                                  char *response, size_t capacity,
                                                  size_t *length,
                                                  kb_protocol_apply_result_t result)
{
    return response_write(response, capacity, length,
        "{\"id\":\"%s\",\"ok\":false,\"error\":{\"code\":\"%s\",\"message\":\"command rejected\",\"details\":{}}}", id, code)
        ? result : KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL;
}

static int base64_value(char c)
{
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    return c == '+' ? 62 : c == '/' ? 63 : -1;
}

static bool base64_decode(const char *input, uint8_t *output, size_t capacity,
                          size_t *length)
{
    size_t in = 0U, out = 0U, input_length = strlen(input);
    if (input_length % 4U != 0U) return false;
    while (in < input_length) {
        int a = base64_value(input[in++]); int b = base64_value(input[in++]);
        int c = input[in] == '=' ? -2 : base64_value(input[in]); ++in;
        int d = input[in] == '=' ? -2 : base64_value(input[in]); ++in;
        if (a < 0 || b < 0 || c == -1 || d == -1 || (c == -2 && d != -2) || out >= capacity) return false;
        output[out++] = (uint8_t)((a << 2) | (b >> 4));
        if (c >= 0) { if (out >= capacity) return false; output[out++] = (uint8_t)((b << 4) | (c >> 2)); }
        if (d >= 0) { if (c < 0 || out >= capacity) return false; output[out++] = (uint8_t)((c << 6) | d); }
        if ((c == -2 || d == -2) && in != input_length) return false;
    }
    *length = out;
    return true;
}

static kb_protocol_apply_result_t commit_upload(kb_protocol_context_t *context,
                                                const kb_protocol_request_t *request,
                                                char *response, size_t capacity,
                                                size_t *length)
{
    kb_config_t *config;
    uint32_t expected = context->upload_expected_crc32;
    kb_boot_result_t boot_result;
    if (!context->upload_active || context->boot == NULL)
        return error_response(request->id, "bad_state", response, capacity, length, KB_PROTOCOL_APPLY_BAD_STATE);
    config = malloc(sizeof(*config));
    if (config == NULL) {
        context->upload_active = false;
        return error_response(request->id, "hal_error", response, capacity,
                              length, KB_PROTOCOL_APPLY_HAL_ERROR);
    }
    if (request->command == KB_PROTOCOL_COMMAND_CONFIG_COMMIT && request->args.commit.has_crc32)
        expected = request->args.commit.config_crc32;
    if (context->upload_length != context->upload_total || kb_crc32(context->upload_bytes, context->upload_length) != expected) {
        context->upload_active = false;
        free(config);
        return error_response(request->id, "bad_crc", response, capacity, length, KB_PROTOCOL_APPLY_BAD_CONFIG);
    }
    if (kb_config_from_json((const char *)context->upload_bytes,
                            context->upload_length, config) !=
        KB_CONFIG_PARSE_OK) {
        context->upload_active = false;
        free(config);
        return error_response(request->id, "bad_config", response, capacity, length, KB_PROTOCOL_APPLY_BAD_CONFIG);
    }
    boot_result = kb_boot_apply_config(context->boot, config);
    free(config);
    context->upload_active = false;
    if (boot_result != KB_BOOT_OK)
        return error_response(request->id, boot_result == KB_BOOT_STORAGE_ERROR ? "hal_error" : "bad_config", response, capacity, length,
                              boot_result == KB_BOOT_STORAGE_ERROR ? KB_PROTOCOL_APPLY_HAL_ERROR : KB_PROTOCOL_APPLY_BAD_CONFIG);
    return response_write(response, capacity, length,
        "{\"id\":\"%s\",\"ok\":true,\"result\":{\"generation\":%lu,\"status\":\"validated\"}}",
        request->id, (unsigned long)context->boot->status.active_generation)
        ? KB_PROTOCOL_APPLY_OK : KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL;
}

kb_protocol_apply_result_t kb_protocol_apply_cmd(
    kb_protocol_context_t *context, const kb_protocol_request_t *request,
    char *response, size_t capacity, size_t *length)
{
    if (context == NULL || request == NULL || response == NULL || length == NULL)
        return KB_PROTOCOL_APPLY_INVALID_ARGUMENT;
    *length = 0U;
    switch (request->command) {
    case KB_PROTOCOL_COMMAND_VERSION: {
        const char *board = context->boot == NULL ? NULL : context->boot->descriptor.board;
        if (board == NULL || board[0] == '\0')
            return error_response(request->id, "hal_error", response, capacity,
                                  length, KB_PROTOCOL_APPLY_HAL_ERROR);
        return response_write(response, capacity, length,
            "{\"id\":\"%s\",\"ok\":true,\"result\":{\"protocol\":\"0.1\",\"active_protocol\":1,\"board\":\"%s\"}}",
            request->id, board) ? KB_PROTOCOL_APPLY_OK : KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL;
    }
    case KB_PROTOCOL_COMMAND_CONFIG_UPLOAD:
        if (request->args.upload.phase == KB_PROTOCOL_UPLOAD_START) {
            memset(context->upload_bytes, 0, sizeof(context->upload_bytes));
            context->upload_active = true; context->upload_total = request->args.upload.total_bytes; context->upload_length = 0U;
            context->upload_expected_crc32 = request->args.upload.config_crc32; context->upload_next_seq = 0U;
            (void)strcpy(context->upload_id, request->args.upload.upload_id);
        } else if (request->args.upload.phase == KB_PROTOCOL_UPLOAD_CHUNK) {
            uint8_t decoded[KB_PROTOCOL_MAX_RAW_CHUNK_BYTES]; size_t decoded_length;
            if (!context->upload_active || strcmp(context->upload_id, request->args.upload.upload_id) != 0 ||
                request->args.upload.seq != context->upload_next_seq ||
                !base64_decode(request->args.upload.data, decoded, sizeof(decoded), &decoded_length) ||
                decoded_length > context->upload_total - context->upload_length)
                return error_response(request->id, "bad_state", response, capacity, length, KB_PROTOCOL_APPLY_BAD_STATE);
            memcpy(context->upload_bytes + context->upload_length, decoded, decoded_length);
            context->upload_length += decoded_length; ++context->upload_next_seq;
        } else if (request->args.upload.phase == KB_PROTOCOL_UPLOAD_ABORT) {
            context->upload_active = false;
        } else return commit_upload(context, request, response, capacity, length);
        return response_write(response, capacity, length,
            "{\"id\":\"%s\",\"ok\":true,\"result\":{\"accepted\":true,\"next_seq\":%lu}}",
            request->id, (unsigned long)context->upload_next_seq) ? KB_PROTOCOL_APPLY_OK : KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL;
    case KB_PROTOCOL_COMMAND_CONFIG_COMMIT:
        return commit_upload(context, request, response, capacity, length);
    case KB_PROTOCOL_COMMAND_CONFIG_GET: {
        const kb_config_t *config = context->boot == NULL ? NULL : kb_boot_active_config(context->boot);
        char *json; size_t json_length;
        if (config == NULL || request->args.config_get.last_good)
            return error_response(request->id, "not_found", response, capacity, length, KB_PROTOCOL_APPLY_BAD_STATE);
        json = malloc(KB_PROTOCOL_MAX_UPLOAD_BYTES + 1U);
        if (json == NULL)
            return error_response(request->id, "hal_error", response, capacity, length, KB_PROTOCOL_APPLY_HAL_ERROR);
        if (kb_config_to_json(config, json, KB_PROTOCOL_MAX_UPLOAD_BYTES + 1U,
                              &json_length) != KB_CONFIG_PARSE_OK) {
            free(json);
            return error_response(request->id, "bad_config", response, capacity, length, KB_PROTOCOL_APPLY_BAD_CONFIG);
        }
        {
            const bool written = response_write(response, capacity, length,
                "{\"id\":\"%s\",\"ok\":true,\"result\":{\"config\":%s}}",
                request->id, json);
            free(json);
            return written ? KB_PROTOCOL_APPLY_OK
                           : KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL;
        }
    }
    case KB_PROTOCOL_COMMAND_KEY_EVENT:
        context->key_events_enabled = request->args.key_event.enabled;
        return response_write(response, capacity, length, "{\"id\":\"%s\",\"ok\":true,\"result\":{\"enabled\":%s}}", request->id, context->key_events_enabled ? "true" : "false") ? KB_PROTOCOL_APPLY_OK : KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL;
    case KB_PROTOCOL_COMMAND_FACTORY_RESET: {
        kb_hal_store_slot_t slot;
        if (!request->args.factory_reset.confirmed || context->boot == NULL || context->boot->hal.hal_store_erase == NULL)
            return error_response(request->id, "bad_params", response, capacity, length, KB_PROTOCOL_APPLY_BAD_STATE);
        for (slot = KB_HAL_STORE_CONFIG_A; slot < KB_HAL_STORE_SLOT_COUNT; slot = (kb_hal_store_slot_t)(slot + 1))
            if (context->boot->hal.hal_store_erase(context->boot->hal.ctx, slot) != KB_HAL_OK)
                return error_response(request->id, "hal_error", response, capacity, length, KB_PROTOCOL_APPLY_HAL_ERROR);
        context->boot->has_active = false; context->boot->has_last_good = false;
        memset(&context->boot->active_config, 0, sizeof(context->boot->active_config));
        context->boot->status.state = KB_BOOT_NO_CONFIG; context->boot->status.matrix_outputs_enabled = false;
        return response_write(response, capacity, length, "{\"id\":\"%s\",\"ok\":true,\"result\":{\"accepted\":true,\"reboot_required\":true}}", request->id) ? KB_PROTOCOL_APPLY_OK : KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL;
    }
    case KB_PROTOCOL_COMMAND_CONFIG_STATUS:
    case KB_PROTOCOL_COMMAND_BOOT_STATUS:
        return response_write(response, capacity, length, "{\"id\":\"%s\",\"ok\":true,\"result\":{\"state\":%u,\"active_generation\":%lu}}", request->id,
            context->boot == NULL ? 0U : (unsigned)context->boot->status.state,
            context->boot == NULL ? 0UL : (unsigned long)context->boot->status.active_generation) ? KB_PROTOCOL_APPLY_OK : KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL;
    default:
        return error_response(request->id, "unsupported", response, capacity, length, KB_PROTOCOL_APPLY_BAD_STATE);
    }
}

kb_protocol_apply_result_t kb_protocol_process_line(
    kb_protocol_context_t *context, const char *line, size_t line_length,
    char *response, size_t capacity, size_t *response_length)
{
    kb_protocol_request_t request;
    const kb_protocol_parse_error_t parsed = kb_protocol_parse_line(line, line_length, &request);
    if (parsed != KB_PROTOCOL_PARSE_OK) {
        const char *code = parsed == KB_PROTOCOL_PARSE_UNKNOWN_COMMAND ? "unknown_command" :
                           parsed == KB_PROTOCOL_PARSE_CRC_MISMATCH ? "bad_crc" :
                           parsed == KB_PROTOCOL_PARSE_BAD_ENVELOPE ? "bad_version_or_envelope" : "invalid_command";
        return error_response("", code, response, capacity, response_length, KB_PROTOCOL_APPLY_BAD_CONFIG);
    }
    return kb_protocol_apply_cmd(context, &request, response, capacity, response_length);
}

int kb_protocol_apply(kb_protocol_context_t *context,
                      const kb_protocol_request_t *request, char *response,
                      size_t capacity, size_t *length)
{
    return (int)kb_protocol_apply_cmd(context, request, response, capacity, length);
}
