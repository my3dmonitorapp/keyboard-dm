"""Read and write Keyboard75 assignment profiles.

Profiles use the frozen Milestone S1.2 version 2 shape and store serialized
typed actions. For compatibility with the S1.1 app/project callers,
``create_profile`` and ``save_profile`` also accept assignment strings. Known
strings are parsed to typed actions; unknown strings are retained verbatim as
``legacy`` actions. Loading a version 1 profile uses the same conversion.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .action import (
    Action,
    ActionValidationError,
    LegacyAction,
    MediaAction,
    ModifierAction,
    SingleKeyAction,
    parse_shortcut,
)


PROFILE_VERSION = 2
LEGACY_PROFILE_VERSION = 1
DEVICE = "/project-esp32s3"
# Retained for the S1.1 simulated-device compatibility surface. Profile v2
# actions themselves are validated by the action model, not this text limit.
MAX_ASSIGNMENT_LENGTH = 32
KEY_ID_PATTERN = re.compile(r"^K\d{2,3}$")


class ProfileError(ValueError):
    """Raised when a profile cannot be safely read as a version 2 profile."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_timestamp(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise ProfileError(f"Profile field '{field_name}' must be an ISO 8601 string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProfileError(
            f"Profile field '{field_name}' must be a valid ISO 8601 timestamp"
        ) from error


_MEDIA_LABELS = {
    "volume up": "vol_up",
    "volume down": "vol_down",
    "mute": "mute",
    "play/pause": "play_pause",
    "next": "next_track",
    "next track": "next_track",
    "previous": "previous_track",
    "previous track": "previous_track",
}

_KEY_LABEL_OVERRIDES = {
    "left arrow": "left",
    "right arrow": "right",
    "up arrow": "up",
    "down arrow": "down",
    "arrowleft": "left",
    "arrowright": "right",
    "arrowup": "up",
    "arrowdown": "down",
    "keypad /": "keypad_divide",
    "keypad *": "keypad_multiply",
    "keypad -": "keypad_subtract",
    "keypad +": "keypad_add",
    "keypad .": "keypad_decimal",
    "keypad =": "keypad_equal",
}


def _parse_assignment(value: str | None) -> Action | None:
    """Deterministically convert one v1/compatibility assignment."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProfileError("Legacy assignment must be a string or null")
    stripped = value.strip()
    if not stripped or stripped.casefold() == "none":
        return None

    folded = stripped.casefold()
    if folded in _KEY_LABEL_OVERRIDES:
        return SingleKeyAction(_KEY_LABEL_OVERRIDES[folded])
    if "+" in stripped:
        try:
            return parse_shortcut(stripped)
        except ActionValidationError:
            pass
    try:
        return MediaAction(_MEDIA_LABELS.get(folded, stripped))
    except ActionValidationError:
        pass
    try:
        return ModifierAction(stripped)
    except ActionValidationError:
        pass
    try:
        return SingleKeyAction(stripped)
    except ActionValidationError:
        return LegacyAction(value)


def _serialized_assignment(value: Any, key_id: str) -> dict[str, Any] | None:
    """Serialize a typed action or compatibility string for one key."""
    try:
        if value is None:
            return None
        if isinstance(value, Action):
            return value.validate().to_json()
        if isinstance(value, str):
            action = _parse_assignment(value)
            return None if action is None else action.to_json()
        return Action.from_json(value).to_json()
    except (ActionValidationError, ProfileError) as error:
        raise ProfileError(f"Invalid assignment for {key_id}: {error}") from error


def _validate_common(profile: Mapping[str, Any]) -> dict[str, Any]:
    if profile.get("device") != DEVICE:
        raise ProfileError(f"Profile device must be '{DEVICE}'")
    _validate_timestamp(profile.get("created"), "created")
    _validate_timestamp(profile.get("updated"), "updated")
    keys = profile.get("keys")
    if not isinstance(keys, dict):
        raise ProfileError("Profile field 'keys' must be a JSON object")
    if not keys:
        raise ProfileError("Profile field 'keys' must contain at least one key")
    for key_id in keys:
        if not isinstance(key_id, str) or not KEY_ID_PATTERN.fullmatch(key_id):
            raise ProfileError(
                f"Unknown profile key ID {key_id!r}; expected K followed by 2 or 3 digits"
            )
    return keys


def _migrate_v1(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Return a lossless, deterministic version 2 representation of v1."""
    keys = _validate_common(profile)
    migrated = deepcopy(dict(profile))
    migrated["profile_version"] = PROFILE_VERSION
    migrated["key_count"] = len(keys)
    migrated_keys: dict[str, dict[str, Any]] = {}
    for key_id, key_data in keys.items():
        if not isinstance(key_data, dict):
            raise ProfileError(f"Profile key {key_id} must be a JSON object")
        if "assignment" not in key_data:
            raise ProfileError(f"Profile key {key_id} is missing assignment")
        raw = key_data["assignment"]
        if raw is not None and not isinstance(raw, str):
            raise ProfileError(f"Legacy assignment for {key_id} must be a string or null")
        action = _parse_assignment(raw)
        migrated_key_data = deepcopy(key_data)
        migrated_key_data["assignment"] = None if action is None else action.to_json()
        migrated_keys[key_id] = migrated_key_data
    migrated["keys"] = migrated_keys
    return migrated


def validate_profile(
    profile: Any, key_ids: object | None = None
) -> dict[str, Any]:
    """Validate and return a version 2 profile, migrating version 1 input."""
    if not isinstance(profile, dict):
        raise ProfileError("Profile root must be a JSON object")
    version = profile.get("profile_version")
    if type(version) is not int or version not in {
        LEGACY_PROFILE_VERSION,
        PROFILE_VERSION,
    }:
        raise ProfileError(
            f"Unsupported profile_version {version!r}; expected 1 or {PROFILE_VERSION}"
        )
    result = _migrate_v1(profile) if version == LEGACY_PROFILE_VERSION else profile
    keys = _validate_common(result)

    if key_ids is not None:
        try:
            expected_ids = set(key_ids)
        except TypeError as error:
            raise ProfileError("Expected key IDs must be an iterable") from error
        actual_ids = set(keys)
        missing = sorted(expected_ids - actual_ids)
        additional = sorted(actual_ids - expected_ids)
        if missing or additional:
            details = []
            if missing:
                details.append(f"missing key IDs: {', '.join(missing)}")
            if additional:
                details.append(f"additional key IDs: {', '.join(additional)}")
            raise ProfileError("Profile key set mismatch (" + "; ".join(details) + ")")

    key_count = result.get("key_count")
    if type(key_count) is not int or key_count < 1:
        raise ProfileError("Profile field 'key_count' must be a positive integer")
    if key_count != len(keys):
        raise ProfileError(
            "Profile key_count does not match keys "
            f"({key_count} declared, {len(keys)} found)"
        )

    for key_id, key_data in keys.items():
        if not isinstance(key_data, dict):
            raise ProfileError(f"Profile key {key_id} must be a JSON object")
        if "assignment" not in key_data:
            raise ProfileError(f"Profile key {key_id} is missing assignment")
        assignment = key_data["assignment"]
        if assignment is None:
            continue
        try:
            Action.from_json(assignment).validate()
        except ActionValidationError as error:
            raise ProfileError(f"Invalid assignment for {key_id}: {error}") from error
    return result


def create_profile(assignments: Mapping[str, Any]) -> dict[str, Any]:
    """Create a version 2 profile from typed or compatibility assignments."""
    now = _timestamp()
    profile = {
        "profile_version": PROFILE_VERSION,
        "device": DEVICE,
        "created": now,
        "updated": now,
        "key_count": len(assignments),
        "keys": {
            key_id: {"assignment": _serialized_assignment(assignment, key_id)}
            for key_id, assignment in assignments.items()
        },
    }
    return validate_profile(profile)


def load_profile(
    path: str | Path, key_ids: object | None = None
) -> dict[str, Any]:
    """Load and validate a profile from *path* for optional *key_ids*."""
    profile_path = Path(path)
    try:
        with profile_path.open("r", encoding="utf-8") as profile_file:
            profile = json.load(profile_file)
    except json.JSONDecodeError as error:
        raise ProfileError(
            f"Malformed JSON in profile '{profile_path}': {error.msg}"
        ) from error

    return validate_profile(profile, key_ids)


def _normalize_for_save(profile: Mapping[str, Any]) -> dict[str, Any]:
    if "profile_version" not in profile:
        return create_profile(profile)
    version = profile.get("profile_version")
    if version == LEGACY_PROFILE_VERSION:
        return _migrate_v1(profile)
    if version != PROFILE_VERSION:
        return deepcopy(dict(profile))

    normalized = deepcopy(dict(profile))
    keys = normalized.get("keys")
    if isinstance(keys, dict):
        for key_id, key_data in keys.items():
            if isinstance(key_data, dict) and "assignment" in key_data:
                key_data["assignment"] = _serialized_assignment(
                    key_data["assignment"], key_id
                )
    return normalized


def save_profile(path: str | Path, profile: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and save a v2 profile, refreshing its ``updated`` timestamp."""
    profile_to_save = validate_profile(_normalize_for_save(profile))
    profile_to_save["updated"] = _timestamp()
    validate_profile(profile_to_save)

    profile_path = Path(path)
    if not str(profile_path).endswith(".json"):
        profile_path = Path(f"{profile_path}.json")
    with profile_path.open("w", encoding="utf-8") as profile_file:
        json.dump(profile_to_save, profile_file, indent=2)
        profile_file.write("\n")

    return profile_to_save
