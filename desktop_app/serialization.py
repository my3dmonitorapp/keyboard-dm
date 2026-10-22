"""Deterministic bridge from desktop projects to firmware ``kb_config`` JSON.

The bridge is chip-family neutral.  Board selection and probing happen before
this boundary through GPIO capability-profile/probe indirection; no family
conditional is embedded in the shared schema conversion.
"""

from __future__ import annotations

import json
import zlib
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .action import Action
from .esp32_gpio import PinRole, get_gpio_profile, validate_gpio_pin
from .matrix_model import MatrixConfig
from .profile import _parse_assignment
from .project import KeyboardProject, validate_project

FIRMWARE_PROTOCOL_VERSION = 1
FIRMWARE_CONFIG_SCHEMA_VERSION = 1
FIRMWARE_MAX_ROWS = 16
FIRMWARE_MAX_COLS = 16
FIRMWARE_MAX_KEYS = 256
DEFAULT_SCAN_MODE = "drive_rows_low_read_cols_pullup"
DEFAULT_PULL_UP_SOURCE = "internal"
DEFAULT_DIODE_DIRECTION = "col_to_row"
DEFAULT_DEBOUNCE_MS = 25


class SerializationError(ValueError):
    """Raised when a desktop project cannot become an activatable config."""


def _project(value: KeyboardProject | Mapping[str, Any]) -> KeyboardProject:
    if isinstance(value, KeyboardProject):
        return value
    try:
        return validate_project(dict(value))
    except (TypeError, ValueError) as error:
        raise SerializationError(str(error)) from error


def _action_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        if isinstance(value, Action):
            action = value.validate()
        elif isinstance(value, str):
            action = _parse_assignment(value)
        else:
            action = Action.from_json(value).validate()
    except (TypeError, ValueError) as error:
        raise SerializationError(f"Invalid key action: {error}") from error
    if action is None:
        return None
    return action.to_json()


def action_to_firmware(value: Any) -> dict[str, Any] | None:
    """Convert one desktop assignment, preserving unknown strings as LEGACY."""
    return _action_payload(value)


def _require_pins(matrix: MatrixConfig) -> tuple[list[int], list[int]]:
    ok, errors = matrix.validate()
    if not ok:
        raise SerializationError("Invalid project matrix: " + "; ".join(errors))
    if matrix.rows > FIRMWARE_MAX_ROWS or matrix.cols > FIRMWARE_MAX_COLS:
        raise SerializationError("Firmware matrix dimensions cannot exceed 16x16")
    if len(matrix.switches) > FIRMWARE_MAX_KEYS:
        raise SerializationError("Firmware supports at most 256 populated switches")
    if any(pin is None for pin in (*matrix.row_pins, *matrix.column_pins)):
        raise SerializationError("Every firmware matrix row and column needs a GPIO pin")
    return list(matrix.row_pins), list(matrix.column_pins)  # type: ignore[arg-type]


def project_to_firmware_config(
    project: KeyboardProject | Mapping[str, Any],
    *,
    chip_class: str,
    scan_mode: str = DEFAULT_SCAN_MODE,
    pull_up_source: str = DEFAULT_PULL_UP_SOURCE,
    diode_direction: str | Mapping[str, str] = DEFAULT_DIODE_DIRECTION,
    debounce_ms: int = DEFAULT_DEBOUNCE_MS,
    generation: int = 0,
) -> dict[str, Any]:
    """Return the exact schema-v1 object consumed by ``kb_config_from_json``."""
    source = _project(project)
    matrix = source.matrix_config
    if matrix is None:
        raise SerializationError("Firmware configuration requires a matrix project")
    row_pins, col_pins = _require_pins(matrix)
    if not isinstance(chip_class, str) or not chip_class or len(chip_class.encode()) >= 16:
        raise SerializationError("chip_class must be 1..15 UTF-8 bytes")
    if scan_mode not in {
        "drive_rows_low_read_cols_pullup",
        "drive_cols_low_read_rows_pullup",
    }:
        raise SerializationError("Unknown matrix scan mode")
    if pull_up_source not in {"internal", "external"}:
        raise SerializationError("pull_up_source must be 'internal' or 'external'")
    if type(debounce_ms) is not int or not 5 <= debounce_ms <= 100:
        raise SerializationError("debounce_ms must be an integer from 5 to 100")
    if type(generation) is not int or not 0 <= generation <= 0xFFFFFFFF:
        raise SerializationError("generation must be an unsigned 32-bit integer")
    try:
        capabilities = get_gpio_profile(chip_class)
    except ValueError as error:
        raise SerializationError(str(error)) from error
    row_role, col_role = (
        (PinRole.OUTPUT, PinRole.INPUT)
        if scan_mode == DEFAULT_SCAN_MODE
        else (PinRole.INPUT, PinRole.OUTPUT)
    )
    for pin, role in (
        *((pin, row_role) for pin in row_pins),
        *((pin, col_role) for pin in col_pins),
    ):
        result = validate_gpio_pin(pin, role, profile=capabilities)
        if not result.valid:
            raise SerializationError(result.error or f"Invalid GPIO {pin}")
        if (
            role is PinRole.INPUT
            and pull_up_source == DEFAULT_PULL_UP_SOURCE
            and pin in capabilities.input_only_pins
        ):
            raise SerializationError(
                f"GPIO {pin} requires an external pull-up for matrix input"
            )
    if len(source.name.encode("utf-8")) >= 64:
        raise SerializationError("project name must be at most 63 UTF-8 bytes")
    updated = source.profile["updated"]
    if not isinstance(updated, str) or len(updated.encode("utf-8")) >= 40:
        raise SerializationError("updated timestamp must be at most 39 UTF-8 bytes")

    cells = sorted(matrix.switches)
    key_ids = [f"MX-{row:02d}-{col:02d}" for row, col in cells]
    actions = {
        key_id: _action_payload(source.assignments[key_id])
        for key_id in key_ids
    }
    if isinstance(diode_direction, Mapping):
        if set(diode_direction) != set(key_ids):
            raise SerializationError("Per-switch diode directions must match populated keys")
        diode: str | dict[str, str] = {
            key_id: diode_direction[key_id] for key_id in key_ids
        }
    else:
        diode = diode_direction
    valid_diodes = {"col_to_row", "row_to_col"}
    if (isinstance(diode, str) and diode not in valid_diodes) or (
        isinstance(diode, dict) and any(value not in valid_diodes for value in diode.values())
    ):
        raise SerializationError("Unknown diode direction")

    config: dict[str, Any] = {
        "protocol_version": FIRMWARE_PROTOCOL_VERSION,
        "config_schema_version": FIRMWARE_CONFIG_SCHEMA_VERSION,
        "chip_class": chip_class,
        "matrix": {
            "rows": matrix.rows,
            "cols": matrix.cols,
            "row_pins": row_pins,
            "col_pins": col_pins,
            "scan_mode": scan_mode,
            "pull_up_source": pull_up_source,
            "debounce_ms": debounce_ms,
            "diode_direction": diode,
            "populated": [
                {"row": row, "col": col, "key_id": key_id}
                for (row, col), key_id in zip(cells, key_ids)
            ],
        },
        "actions": actions,
        "meta": {
            "project_name": source.name,
            "project_version": 3,
            "profile_version": source.profile["profile_version"],
            "matrix_schema_version": 1,
            "updated": updated,
        },
        "extensions": {},
        "generation": generation,
    }
    raw_without_crc = stable_json_bytes(config)
    config["crc32"] = zlib.crc32(raw_without_crc) & 0xFFFFFFFF
    return config


def stable_json_bytes(value: Any) -> bytes:
    """Encode compact insertion-ordered UTF-8 JSON without ASCII escaping."""
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def firmware_config_json(
    project: KeyboardProject | Mapping[str, Any], **options: Any
) -> bytes:
    """Build canonical firmware JSON bytes, including the embedded CRC32."""
    return stable_json_bytes(project_to_firmware_config(project, **options))


# Compatibility-friendly names for headless callers.
serialize_project = firmware_config_json
serialize_project_to_firmware = firmware_config_json
build_firmware_config = project_to_firmware_config


def firmware_config_text(
    project: KeyboardProject | Mapping[str, Any], **options: Any
) -> str:
    """Text form of :func:`firmware_config_json` for serial libraries."""
    return firmware_config_json(project, **options).decode("utf-8")


def verify_firmware_config_crc(config: Mapping[str, Any]) -> bool:
    """Check the embedded CRC using the canonical firmware member order."""
    if type(config.get("crc32")) is not int:
        return False
    without_crc = deepcopy(dict(config))
    expected = without_crc.pop("crc32")
    return (zlib.crc32(stable_json_bytes(without_crc)) & 0xFFFFFFFF) == expected
