#include "kb_boot.h"

#include "kb_crc32.h"

#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define KB_BOOT_METADATA_MAGIC UINT32_C(0x4b424d31)
#define KB_BOOT_METADATA_VERSION 1U
#define KB_BOOT_CONFIG_BYTES 8192U

typedef struct {
    uint32_t magic;
    uint16_t version;
    uint8_t active_slot;
    uint8_t has_last_good;
    uint32_t active_generation;
    uint8_t last_good_slot;
    uint8_t reserved[3];
    uint32_t last_good_generation;
    uint32_t crc32;
} boot_metadata_t;

typedef enum {
    SLOT_ABSENT = 0,
    SLOT_VALID,
    SLOT_INVALID,
    SLOT_IO_ERROR
} slot_result_t;

static bool hal_complete(const kb_hal_ops_t *hal)
{
    return hal != NULL && hal->hal_store_read != NULL &&
           hal->hal_store_write != NULL && hal->hal_console_send != NULL;
}

static uint32_t metadata_crc(const boot_metadata_t *metadata)
{
    return kb_crc32(metadata, offsetof(boot_metadata_t, crc32));
}

static bool metadata_valid(const boot_metadata_t *metadata, size_t length)
{
    return length == sizeof(*metadata) &&
           metadata->magic == KB_BOOT_METADATA_MAGIC &&
           metadata->version == KB_BOOT_METADATA_VERSION &&
           metadata->active_slot <= (uint8_t)KB_HAL_STORE_CONFIG_B &&
           (!metadata->has_last_good ||
            metadata->last_good_slot <= (uint8_t)KB_HAL_STORE_CONFIG_B) &&
           metadata->crc32 == metadata_crc(metadata);
}

static void metadata_build(boot_metadata_t *metadata,
                           kb_hal_store_slot_t active_slot,
                           uint32_t active_generation, bool has_last_good,
                           kb_hal_store_slot_t last_good_slot,
                           uint32_t last_good_generation)
{
    memset(metadata, 0, sizeof(*metadata));
    metadata->magic = KB_BOOT_METADATA_MAGIC;
    metadata->version = KB_BOOT_METADATA_VERSION;
    metadata->active_slot = (uint8_t)active_slot;
    metadata->active_generation = active_generation;
    metadata->has_last_good = has_last_good ? 1U : 0U;
    metadata->last_good_slot = (uint8_t)last_good_slot;
    metadata->last_good_generation = last_good_generation;
    metadata->crc32 = metadata_crc(metadata);
}

static slot_result_t load_slot(kb_boot_t *boot, kb_hal_store_slot_t slot,
                               kb_config_t *config, uint16_t *error_count)
{
    char *buffer;
    size_t length = 0U;
    kb_config_error_list_t errors;
    kb_hal_error_t result;
    slot_result_t slot_result;
    buffer = malloc(KB_BOOT_CONFIG_BYTES);
    if (buffer == NULL) {
        return SLOT_IO_ERROR;
    }
    kb_config_errors_reset(&errors);
    result = boot->hal.hal_store_read(
        boot->hal.ctx, slot, buffer, KB_BOOT_CONFIG_BYTES, &length);
    if (result == KB_HAL_ERR_NOT_FOUND) {
        free(buffer);
        return SLOT_ABSENT;
    }
    if (result != KB_HAL_OK) {
        slot_result = result == KB_HAL_ERR_CORRUPT ? SLOT_INVALID
                                                   : SLOT_IO_ERROR;
        free(buffer);
        return slot_result;
    }
    if (length == 0U ||
        kb_config_from_json(buffer, length, config) != KB_CONFIG_PARSE_OK ||
        !kb_config_validate(config, &boot->descriptor, &errors)) {
        if (error_count != NULL) {
            *error_count = length == 0U ? 1U : (uint16_t)errors.count;
            if (*error_count == 0U) {
                *error_count = 1U;
            }
        }
        free(buffer);
        return SLOT_INVALID;
    }
    free(buffer);
    return SLOT_VALID;
}

static void banner(kb_boot_t *boot, const char *state, const char *reason)
{
    char line[160];
    const int length = snprintf(line, sizeof(line),
                                "{\"event\":\"boot\",\"state\":\"%s\","
                                "\"reason\":\"%s\"}\n",
                                state, reason);
    if (length > 0 && (size_t)length < sizeof(line)) {
        (void)boot->hal.hal_console_send(boot->hal.ctx, line, (size_t)length);
    }
}

static void select_active(kb_boot_t *boot, kb_hal_store_slot_t slot,
                          const kb_config_t *config)
{
    boot->active_slot = slot;
    boot->active_config = *config;
    boot->has_active = true;
    boot->status.state = KB_BOOT_VALID;
    boot->status.active_generation = config->generation;
    boot->status.matrix_outputs_enabled = true;
}

kb_boot_result_t kb_boot_start(kb_boot_t *boot,
                               const kb_hal_probe_t *descriptor,
                               const kb_hal_ops_t *hal)
{
    boot_metadata_t metadata;
    size_t metadata_length = 0U;
    kb_hal_error_t metadata_result;
    bool have_metadata;
    kb_config_t *first;
    kb_config_t *second;
    slot_result_t first_result;
    slot_result_t second_result;
    kb_hal_store_slot_t first_slot = KB_HAL_STORE_CONFIG_A;
    kb_hal_store_slot_t second_slot = KB_HAL_STORE_CONFIG_B;

    if (boot == NULL || descriptor == NULL || !hal_complete(hal)) {
        return KB_BOOT_INVALID_ARGUMENT;
    }
    memset(boot, 0, sizeof(*boot));
    boot->descriptor = *descriptor;
    boot->hal = *hal;
    boot->status.state = KB_BOOT_LOADING;
    first = malloc(sizeof(*first));
    second = malloc(sizeof(*second));
    if (first == NULL || second == NULL) {
        free(first);
        free(second);
        boot->status.state = KB_BOOT_SAFE_MODE;
        boot->status.matrix_outputs_enabled = false;
        boot->reason = KB_BOOT_REASON_STORAGE_ERROR;
        banner(boot, "safe_mode", "no_memory");
        return KB_BOOT_STORAGE_ERROR;
    }
    metadata_result = boot->hal.hal_store_read(
        boot->hal.ctx, KB_HAL_STORE_METADATA, &metadata, sizeof(metadata),
        &metadata_length);
    have_metadata = metadata_result == KB_HAL_OK &&
                    metadata_valid(&metadata, metadata_length);
    if (have_metadata) {
        first_slot = (kb_hal_store_slot_t)metadata.active_slot;
        second_slot = first_slot == KB_HAL_STORE_CONFIG_A
                          ? KB_HAL_STORE_CONFIG_B
                          : KB_HAL_STORE_CONFIG_A;
    }
    first_result = load_slot(boot, first_slot, first,
                             &boot->status.validation_error_count);
    second_result = load_slot(boot, second_slot, second,
                              &boot->status.validation_error_count);

    /* A present but unreadable marker can be an interrupted publication. */
    if (!have_metadata && metadata_result != KB_HAL_ERR_NOT_FOUND) {
        boot->status.state = KB_BOOT_SAFE_MODE;
        boot->status.matrix_outputs_enabled = false;
        boot->reason = KB_BOOT_REASON_STORAGE_ERROR;
        banner(boot, "safe_mode", "metadata_invalid");
        free(first);
        free(second);
        return KB_BOOT_OK;
    }

    if (first_result == SLOT_VALID &&
        (!have_metadata || first->generation == metadata.active_generation) &&
        (have_metadata || second_result != SLOT_VALID ||
         first->generation >= second->generation)) {
        select_active(boot, first_slot, first);
        if (have_metadata && metadata.has_last_good &&
            metadata.last_good_slot != metadata.active_slot) {
            const kb_config_t *candidate = second_slot ==
                                                   (kb_hal_store_slot_t)
                                                       metadata.last_good_slot
                                               ? second
                                               : NULL;
            if (candidate != NULL && second_result == SLOT_VALID &&
                candidate->generation == metadata.last_good_generation) {
                boot->has_last_good = true;
                boot->last_good_slot = second_slot;
                boot->status.last_good_generation = candidate->generation;
            }
        }
        banner(boot, "valid", "active_valid");
        free(first);
        free(second);
        return KB_BOOT_OK;
    }
    if (second_result == SLOT_VALID) {
        boot_metadata_t repaired;
        select_active(boot, second_slot, second);
        boot->status.rollback_used = have_metadata;
        boot->reason = have_metadata ? KB_BOOT_REASON_ACTIVE_INVALID_ROLLBACK
                                     : KB_BOOT_REASON_NONE;
        metadata_build(&repaired, second_slot, second->generation, false,
                       second_slot, second->generation);
        (void)boot->hal.hal_store_write(boot->hal.ctx, KB_HAL_STORE_METADATA,
                                        &repaired, sizeof(repaired));
        banner(boot, "valid", have_metadata ? "active_invalid_rollback"
                                             : "discovered_valid_slot");
        free(first);
        free(second);
        return KB_BOOT_OK;
    }
    boot->status.matrix_outputs_enabled = false;
    if (first_result == SLOT_ABSENT && second_result == SLOT_ABSENT &&
        metadata_result == KB_HAL_ERR_NOT_FOUND) {
        boot->status.state = KB_BOOT_NO_CONFIG;
        boot->reason = KB_BOOT_REASON_NO_CONFIG;
        banner(boot, "no_config", "no_config");
        free(first);
        free(second);
        return KB_BOOT_OK;
    }
    boot->status.state = KB_BOOT_SAFE_MODE;
    boot->reason = (first_result == SLOT_IO_ERROR || second_result == SLOT_IO_ERROR)
                       ? KB_BOOT_REASON_STORAGE_ERROR
                       : KB_BOOT_REASON_BOTH_SLOTS_INVALID;
    banner(boot, "safe_mode",
           boot->reason == KB_BOOT_REASON_STORAGE_ERROR ? "storage_error"
                                                        : "both_slots_invalid");
    free(first);
    free(second);
    return KB_BOOT_OK;
}

static kb_boot_result_t store_config(kb_boot_t *boot,
                                     kb_hal_store_slot_t slot,
                                     const kb_config_t *config)
{
    char *buffer;
    size_t length;
    kb_config_t *verified;
    uint16_t ignored_errors = 0U;
    kb_boot_result_t result = KB_BOOT_STORAGE_ERROR;
    buffer = malloc(KB_BOOT_CONFIG_BYTES);
    verified = malloc(sizeof(*verified));
    if (buffer == NULL || verified == NULL) {
        free(buffer);
        free(verified);
        return KB_BOOT_STORAGE_ERROR;
    }
    if (kb_config_to_json(config, buffer, KB_BOOT_CONFIG_BYTES, &length) !=
        KB_CONFIG_PARSE_OK) {
        goto done;
    }
    if (boot->hal.hal_store_write(boot->hal.ctx, slot, buffer, length) !=
        KB_HAL_OK) {
        goto done;
    }
    if (load_slot(boot, slot, verified, &ignored_errors) != SLOT_VALID ||
        verified->generation != config->generation ||
        verified->crc32 != config->crc32) {
        goto done;
    }
    result = KB_BOOT_OK;
done:
    free(buffer);
    free(verified);
    return result;
}

kb_boot_result_t kb_boot_apply_config(kb_boot_t *boot,
                                      const kb_config_t *config)
{
    kb_config_t *candidate;
    kb_config_error_list_t errors;
    kb_hal_store_slot_t target;
    boot_metadata_t metadata;
    uint32_t generation;
    if (boot == NULL || config == NULL || !hal_complete(&boot->hal)) {
        return KB_BOOT_INVALID_ARGUMENT;
    }
    if (boot->has_active && boot->active_config.generation == UINT32_MAX) {
        return KB_BOOT_NO_CHANGE;
    }
    candidate = malloc(sizeof(*candidate));
    if (candidate == NULL) {
        return KB_BOOT_STORAGE_ERROR;
    }
    *candidate = *config;
    generation = boot->has_active ? boot->active_config.generation + 1U : 1U;
    candidate->generation = generation;
    if (kb_config_finalize_crc32(candidate) != KB_CONFIG_PARSE_OK ||
        !kb_config_validate(candidate, &boot->descriptor, &errors)) {
        free(candidate);
        return KB_BOOT_INVALID_CONFIG;
    }
    target = !boot->has_active || boot->active_slot == KB_HAL_STORE_CONFIG_B
                 ? KB_HAL_STORE_CONFIG_A
                 : KB_HAL_STORE_CONFIG_B;
    if (store_config(boot, target, candidate) != KB_BOOT_OK) {
        free(candidate);
        return KB_BOOT_STORAGE_ERROR;
    }
    metadata_build(&metadata, target, generation, boot->has_active,
                   boot->has_active ? boot->active_slot : target,
                   boot->has_active ? boot->active_config.generation : generation);
    if (boot->hal.hal_store_write(boot->hal.ctx, KB_HAL_STORE_METADATA,
                                  &metadata, sizeof(metadata)) != KB_HAL_OK) {
        free(candidate);
        return KB_BOOT_STORAGE_ERROR;
    }
    if (boot->has_active) {
        boot->has_last_good = true;
        boot->last_good_slot = boot->active_slot;
        boot->status.last_good_generation = boot->active_config.generation;
    } else {
        boot->has_last_good = false;
        boot->status.last_good_generation = 0U;
    }
    select_active(boot, target, candidate);
    free(candidate);
    boot->status.rollback_used = false;
    boot->reason = KB_BOOT_REASON_NONE;
    return KB_BOOT_OK;
}

kb_boot_result_t kb_boot_recover(kb_boot_t *boot)
{
    boot_metadata_t metadata;
    size_t length = 0U;
    kb_config_t *recovered;
    uint16_t error_count = 0U;
    boot_metadata_t consumed;
    if (boot == NULL || !boot->has_active || !hal_complete(&boot->hal)) {
        return KB_BOOT_INVALID_ARGUMENT;
    }
    recovered = malloc(sizeof(*recovered));
    if (recovered == NULL) {
        return KB_BOOT_STORAGE_ERROR;
    }
    if (boot->hal.hal_store_read(boot->hal.ctx, KB_HAL_STORE_METADATA,
                                 &metadata, sizeof(metadata), &length) !=
            KB_HAL_OK ||
        !metadata_valid(&metadata, length)) {
        free(recovered);
        return KB_BOOT_STORAGE_ERROR;
    }
    if (!metadata.has_last_good ||
        metadata.last_good_generation == boot->active_config.generation) {
        free(recovered);
        return KB_BOOT_NO_CHANGE;
    }
    boot->status.state = KB_BOOT_RECOVERING;
    if (load_slot(boot, (kb_hal_store_slot_t)metadata.last_good_slot,
                  recovered, &error_count) != SLOT_VALID ||
        recovered->generation != metadata.last_good_generation) {
        boot->status.state = KB_BOOT_VALID;
        free(recovered);
        return KB_BOOT_NO_RECOVERY;
    }
    metadata_build(&consumed,
                   (kb_hal_store_slot_t)metadata.last_good_slot,
                   recovered->generation, false,
                   (kb_hal_store_slot_t)metadata.last_good_slot,
                   recovered->generation);
    if (boot->hal.hal_store_write(boot->hal.ctx, KB_HAL_STORE_METADATA,
                                  &consumed, sizeof(consumed)) != KB_HAL_OK) {
        boot->status.state = KB_BOOT_VALID;
        free(recovered);
        return KB_BOOT_STORAGE_ERROR;
    }
    select_active(boot, (kb_hal_store_slot_t)metadata.last_good_slot,
                  recovered);
    free(recovered);
    boot->has_last_good = false;
    boot->status.last_good_generation = boot->active_config.generation;
    boot->status.rollback_used = true;
    boot->reason = KB_BOOT_REASON_ACTIVE_INVALID_ROLLBACK;
    return KB_BOOT_OK;
}

const kb_config_t *kb_boot_active_config(const kb_boot_t *boot)
{
    return boot != NULL && boot->has_active ? &boot->active_config : NULL;
}
