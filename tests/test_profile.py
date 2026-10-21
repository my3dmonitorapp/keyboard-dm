"""Tests for the frozen Keyboard DM JSON profile format."""

import json

import pytest

from desktop_app.action import (
    LegacyAction,
    MediaAction,
    ModifierAction,
    ShortcutAction,
    SingleKeyAction,
)
from desktop_app.profile import (
    PROFILE_VERSION,
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
    path = tmp_path / "project.json"
    save_profile(path, _assignments())
    profile = load_profile(path)
    profile["updated"] = "2000-01-01T00:00:00+00:00"

    written = save_profile(path, profile)
    loaded = load_profile(path)

    assert loaded == written
    assert loaded["profile_version"] == 2
    assert loaded["key_count"] == 75
    assert loaded["device"] == "/keyboard-dm-profile"
    assert loaded["chip_class"] == "esp32"
    assert loaded["updated"] != "2000-01-01T00:00:00+00:00"
    assert loaded["keys"]["K75"]["assignment"] is None


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
    assert loaded["key_count"] == layout.key_count
    assert {
        key_id: key_data["assignment"]["raw"]
        for key_id, key_data in loaded["keys"].items()
    } == assignments


def test_unknown_profile_version_is_rejected(tmp_path) -> None:
    path = tmp_path / "future.json"
    profile = create_profile(_assignments())
    profile["profile_version"] = 99
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ProfileError, match="Unsupported profile_version"):
        load_profile(path, key_ids=LEGACY_KEY_IDS)


def test_device_is_validated_before_legacy_normalization(tmp_path) -> None:
    profile = create_profile({"K01": None})
    profile["device"] = "/project-esp32s3-bogus"
    bogus = tmp_path / "bogus.json"
    bogus.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(ProfileError, match="Profile device"):
        load_profile(bogus)

    profile["device"] = "/project-esp32s3"
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps(profile), encoding="utf-8")
    loaded = load_profile(legacy)
    assert loaded["device"] == "/keyboard-dm-profile"
    assert loaded["chip_class"] == "esp32"


def test_variable_key_profile_validates_without_expected_key_set() -> None:
    assignments = {f"K{number:02d}": "NONE" for number in range(1, 7)}

    profile = create_profile(assignments)

    assert validate_profile(profile) == profile
    assert profile["key_count"] == 6
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
        "assignment": {"type": "key", "key": "a"}
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
    legacy["profile_version"] = 1
    del legacy["key_count"]
    for key_data in legacy["keys"].values():
        key_data["assignment"] = "NONE"
    legacy["keys"]["K01"]["assignment"] = "Escape"
    legacy["keys"]["K75"]["assignment"] = "Enter"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = load_profile(path, key_ids=LEGACY_KEY_IDS)

    assert loaded["profile_version"] == 2
    assert loaded["key_count"] == 75
    assert loaded["keys"]["K01"]["assignment"] == {"type": "key", "key": "escape"}
    assert loaded["keys"]["K75"]["assignment"] == {"type": "key", "key": "enter"}
    assert loaded["keys"]["K02"]["assignment"] is None


def test_bad_action_payload_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad-action.json"
    profile = create_profile(_assignments())
    profile["keys"]["K07"]["assignment"] = {"type": "key", "key": "hyper"}
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ProfileError, match="Invalid assignment for K07"):
        load_profile(path)


def test_malformed_json_is_rejected(tmp_path) -> None:
    path = tmp_path / "malformed.json"
    path.write_text('{"profile_version": 1,', encoding="utf-8")

    with pytest.raises(ProfileError, match="Malformed JSON"):
        load_profile(path)


def _v1_profile(assignments: dict[str, str | None]) -> dict:
    profile = create_profile({key_id: None for key_id in assignments})
    profile["profile_version"] = 1
    del profile["key_count"]
    for key_id, assignment in assignments.items():
        profile["keys"][key_id]["assignment"] = assignment
    return profile


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("A", SingleKeyAction("a").to_json()),
        ("9", SingleKeyAction("9").to_json()),
        ("F24", SingleKeyAction("f24").to_json()),
        ("PageDown", SingleKeyAction("page_down").to_json()),
        ("Left Arrow", SingleKeyAction("left").to_json()),
        ("Keypad +", SingleKeyAction("keypad_add").to_json()),
        ("Ctrl", ModifierAction("lctrl").to_json()),
        ("Right Alt", ModifierAction("ralt").to_json()),
        ("Ctrl+C", ShortcutAction(("lctrl",), "c").to_json()),
        ("Ctrl+Shift+S", ShortcutAction(("lctrl", "lshift"), "s").to_json()),
        ("Alt+Tab", ShortcutAction(("lalt",), "tab").to_json()),
        ("Volume Up", MediaAction("vol_up").to_json()),
        ("Mute", MediaAction("mute").to_json()),
        ("Play/Pause", MediaAction("play_pause").to_json()),
        ("Next", MediaAction("next_track").to_json()),
        ("Previous", MediaAction("previous_track").to_json()),
        ("NONE", None),
        ("", None),
        ("  \t", None),
        (None, None),
    ],
)
def test_v1_known_assignment_forms_migrate(raw, expected, tmp_path) -> None:
    path = tmp_path / "v1.json"
    path.write_text(json.dumps(_v1_profile({"K01": raw})), encoding="utf-8")

    loaded = load_profile(path)

    assert loaded["profile_version"] == PROFILE_VERSION
    assert loaded["keys"]["K01"]["assignment"] == expected


def test_v1_unparsable_value_is_preserved_verbatim_and_migration_is_stable(
    tmp_path,
) -> None:
    original = "  launch 🚀 custom-mode  "
    source = tmp_path / "v1.json"
    target = tmp_path / "v2.json"
    source.write_text(
        json.dumps(_v1_profile({"K01": original, "K02": "Ctrl+X"})),
        encoding="utf-8",
    )

    migrated = load_profile(source)
    written = save_profile(target, migrated)

    assert migrated["keys"]["K01"]["assignment"] == LegacyAction(original).to_json()
    assert load_profile(target) == written


@pytest.mark.parametrize(
    "action",
    [
        SingleKeyAction("enter"),
        ModifierAction("rctrl", "up"),
        ShortcutAction(("lctrl",), "c"),
        ShortcutAction(("lctrl", "lshift", "ralt"), "delete"),
        MediaAction("vol_up"),
        MediaAction("vol_down"),
        MediaAction("mute"),
        MediaAction("play_pause"),
        MediaAction("next_track"),
        MediaAction("previous_track"),
        LegacyAction("exact unknown text"),
    ],
)
def test_every_typed_action_kind_round_trips(action, tmp_path) -> None:
    path = tmp_path / f"{action.action_type}.json"

    written = save_profile(path, {"K01": action})
    loaded = load_profile(path)

    assert loaded == written
    assert loaded["keys"]["K01"]["assignment"] == action.to_json()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda profile: profile.pop("key_count"), "key_count"),
        (lambda profile: profile.update(key_count=2), "does not match keys"),
        (
            lambda profile: profile["keys"].update(BAD={"assignment": None}),
            "Unknown profile key ID",
        ),
        (
            lambda profile: profile["keys"]["K01"].pop("assignment"),
            "missing assignment",
        ),
        (
            lambda profile: profile["keys"]["K01"].update(
                assignment={"type": "nope"}
            ),
            "Unknown action type",
        ),
    ],
)
def test_invalid_v2_profiles_are_rejected(change, message) -> None:
    profile = create_profile({"K01": None})
    change(profile)

    with pytest.raises(ProfileError, match=message):
        validate_profile(profile)


def test_v1_non_string_assignment_is_rejected_cleanly() -> None:
    profile = _v1_profile({"K01": "A"})
    profile["keys"]["K01"]["assignment"] = ["A"]

    with pytest.raises(ProfileError, match="string or null"):
        validate_profile(profile)
