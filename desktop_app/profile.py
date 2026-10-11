"""Read and write Keyboard75 assignment profiles.

The JSON schema in this module is the frozen Milestone S1 profile format.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROFILE_VERSION = 1
DEVICE = "/project-esp32s3"
KEY_IDS = tuple(f"K{number:02d}" for number in range(1, 76))
MAX_ASSIGNMENT_LENGTH = 32


class ProfileError(ValueError):
    """Raised when a profile does not match the frozen format."""


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


def validate_profile(profile: Any) -> dict[str, Any]:
    """Validate and return *profile* using the frozen version 1 schema."""
    if not isinstance(profile, dict):
        raise ProfileError("Profile root must be a JSON object")

    version = profile.get("profile_version")
    if type(version) is not int or version != PROFILE_VERSION:
        raise ProfileError(
            f"Unsupported profile_version {version!r}; expected {PROFILE_VERSION}"
        )

    if profile.get("device") != DEVICE:
        raise ProfileError(f"Profile device must be '{DEVICE}'")

    _validate_timestamp(profile.get("created"), "created")
    _validate_timestamp(profile.get("updated"), "updated")

    keys = profile.get("keys")
    if not isinstance(keys, dict):
        raise ProfileError("Profile field 'keys' must be a JSON object")

    expected_ids = set(KEY_IDS)
    actual_ids = set(keys)
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if missing:
        raise ProfileError(f"Profile is missing key IDs: {', '.join(missing)}")
    if extra:
        raise ProfileError(f"Profile contains unknown key IDs: {', '.join(extra)}")

    for key_id in KEY_IDS:
        key_data = keys[key_id]
        if not isinstance(key_data, dict):
            raise ProfileError(f"Profile key {key_id} must be a JSON object")
        assignment = key_data.get("assignment")
        if not isinstance(assignment, str):
            raise ProfileError(f"Assignment for {key_id} must be a string")
        if len(assignment) > MAX_ASSIGNMENT_LENGTH:
            raise ProfileError(
                f"Assignment for {key_id} exceeds {MAX_ASSIGNMENT_LENGTH} characters"
            )

    return profile


def create_profile(assignments: Mapping[str, str]) -> dict[str, Any]:
    """Create a new version 1 profile from all 75 key assignments."""
    now = _timestamp()
    profile = {
        "profile_version": PROFILE_VERSION,
        "device": DEVICE,
        "created": now,
        "updated": now,
        "keys": {
            key_id: {"assignment": assignment}
            for key_id, assignment in assignments.items()
        },
    }
    return validate_profile(profile)


def load_profile(path: str | Path) -> dict[str, Any]:
    """Load and validate a profile from *path*."""
    profile_path = Path(path)
    try:
        with profile_path.open("r", encoding="utf-8") as profile_file:
            profile = json.load(profile_file)
    except json.JSONDecodeError as error:
        raise ProfileError(
            f"Malformed JSON in profile '{profile_path}': {error.msg}"
        ) from error

    return validate_profile(profile)


def save_profile(path: str | Path, profile: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and save a profile, refreshing its ``updated`` timestamp.

    *profile* may be a complete profile returned by :func:`create_profile` or
    :func:`load_profile`, or a mapping of all 75 key IDs to assignment strings.
    The returned dictionary contains the timestamp written to disk; the
    caller's mapping is not mutated.
    """
    if "profile_version" in profile:
        profile_to_save = deepcopy(dict(profile))
    else:
        profile_to_save = create_profile(profile)
    validate_profile(profile_to_save)
    profile_to_save["updated"] = _timestamp()
    validate_profile(profile_to_save)

    profile_path = Path(path)
    with profile_path.open("w", encoding="utf-8") as profile_file:
        json.dump(profile_to_save, profile_file, indent=2)
        profile_file.write("\n")

    return profile_to_save
