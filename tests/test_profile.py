"""Tests for the frozen Keyboard75 JSON profile format."""

import json

import pytest

from desktop_app.profile import (
    ProfileError,
    create_profile,
    load_profile,
    save_profile,
    validate_profile,
)
from desktop_app.layouts import L06, L09, L12, L75, make_custom_layout


LEGACY_KEY_IDS = tuple(f"K{number:02d}" for number in range(1, 76))


def _assignments() -> dict[str, str]:
    return {key_id: "NONE" for key_id in LEGACY_KEY_IDS}


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


@pytest.mark.parametrize(
    ("name", "layout"),
    [
        ("l06", L06),
        ("l09", L09),
        ("l12", L12),
        ("l75", L75),
        ("custom-17", make_custom_layout(17, cols=5)),
    ],
)
def test_every_supported_key_count_round_trips_through_json(
    tmp_path, name, layout
) -> None:
    assignments = {
        key.key_id: f"Action-{index}"
        for index, key in enumerate(layout.keys, start=1)
    }
    path = tmp_path / f"{name}.json"

    written = save_profile(path, assignments)
    loaded = load_profile(path, key_ids=(key.key_id for key in layout.keys))

    assert loaded == written
    assert list(loaded["keys"]) == [key.key_id for key in layout.keys]
    assert {
        key_id: key_data["assignment"]
        for key_id, key_data in loaded["keys"].items()
    } == assignments


def test_unknown_profile_version_is_rejected(tmp_path) -> None:
    path = tmp_path / "future.json"
    profile = create_profile(_assignments())
    profile["profile_version"] = 2
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ProfileError, match="Unsupported profile_version"):
        load_profile(path, key_ids=LEGACY_KEY_IDS)


def test_variable_key_profile_validates_without_expected_key_set() -> None:
    assignments = {f"K{number:02d}": "NONE" for number in range(1, 7)}

    profile = create_profile(assignments)

    assert validate_profile(profile) == profile
    assert set(profile["keys"]) == set(assignments)


def test_expected_key_set_reports_missing_and_additional_ids() -> None:
    profile = create_profile({"K01": "NONE", "K03": "NONE"})

    with pytest.raises(
        ProfileError,
        match=r"missing key IDs: K02; additional key IDs: K03",
    ):
        validate_profile(profile, key_ids=("K01", "K02"))


def test_save_appends_json_suffix(tmp_path) -> None:
    requested_path = tmp_path / "six-key-profile"

    save_profile(requested_path, {"K01": "A"})

    assert not requested_path.exists()
    assert load_profile(tmp_path / "six-key-profile.json")["keys"]["K01"] == {
        "assignment": "A"
    }


def test_missing_key_is_rejected(tmp_path) -> None:
    path = tmp_path / "missing-key.json"
    profile = create_profile(_assignments())
    del profile["keys"]["K42"]
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ProfileError, match="missing key IDs: K42"):
        load_profile(path, key_ids=LEGACY_KEY_IDS)


def test_legacy_v1_75_key_file_loads_unchanged(tmp_path) -> None:
    path = tmp_path / "legacy-v1-75.json"
    legacy = create_profile(_assignments())
    legacy["keys"]["K01"]["assignment"] = "Escape"
    legacy["keys"]["K75"]["assignment"] = "Enter"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = load_profile(path, key_ids=LEGACY_KEY_IDS)

    assert loaded == legacy


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
