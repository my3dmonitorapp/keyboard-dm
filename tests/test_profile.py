"""Tests for the frozen Keyboard75 JSON profile format."""

import json

import pytest

from desktop_app.profile import (
    KEY_IDS,
    ProfileError,
    create_profile,
    load_profile,
    save_profile,
)


def _assignments() -> dict[str, str]:
    return {key_id: "NONE" for key_id in KEY_IDS}


def test_profile_round_trip_refreshes_updated_timestamp(tmp_path) -> None:
    path = tmp_path / "/project.json"
    save_profile(path, _assignments())
    profile = load_profile(path)
    profile["updated"] = "2000-01-01T00:00:00+00:00"

    written = save_profile(path, profile)
    loaded = load_profile(path)

    assert loaded == written
    assert loaded["profile_version"] == 1
    assert loaded["device"] == "/project-esp32s3"
    assert loaded["updated"] != "2000-01-01T00:00:00+00:00"
    assert loaded["keys"]["K75"]["assignment"] == "NONE"


def test_unknown_profile_version_is_rejected(tmp_path) -> None:
    path = tmp_path / "future.json"
    profile = create_profile(_assignments())
    profile["profile_version"] = 2
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ProfileError, match="Unsupported profile_version"):
        load_profile(path)


def test_missing_key_is_rejected(tmp_path) -> None:
    path = tmp_path / "missing-key.json"
    profile = create_profile(_assignments())
    del profile["keys"]["K42"]
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ProfileError, match="missing key IDs: K42"):
        load_profile(path)


def test_assignment_over_32_characters_is_rejected(tmp_path) -> None:
    path = tmp_path / "long-assignment.json"
    profile = create_profile(_assignments())
    profile["keys"]["K07"]["assignment"] = "A" * 33
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ProfileError, match="K07 exceeds 32 characters"):
        load_profile(path)


def test_malformed_json_is_rejected(tmp_path) -> None:
    path = tmp_path / "malformed.json"
    path.write_text('{"profile_version": 1,', encoding="utf-8")

    with pytest.raises(ProfileError, match="Malformed JSON"):
        load_profile(path)
