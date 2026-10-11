"""Tests for the typed keyboard action model."""

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping

import pytest

from desktop_app.action import (
    Action,
    ActionValidationError,
    MEDIA_KEYS,
    MODIFIERS,
    MediaAction,
    ModifierAction,
    ShortcutAction,
    SingleKeyAction,
    parse_shortcut,
    register_action_type,
    validate_action,
)


def test_single_key_construction_exposes_stable_hid_metadata() -> None:
    key = SingleKeyAction("a")

    assert key.id == "key:a"
    assert key.label == "A"
    assert key.usage_id == 0x04
    assert SingleKeyAction("PageUp").key == "page_up"
    assert SingleKeyAction("F24").usage_id == 0x73


@pytest.mark.parametrize(
    "action",
    [
        SingleKeyAction("Enter"),
        ModifierAction("RCtrl", "up"),
        ShortcutAction(("lctrl", "rshift"), "s"),
        MediaAction("play_pause"),
    ],
)
def test_serialization_round_trip(action: Action) -> None:
    restored = Action.from_json(action.to_json())

    assert restored == action
    assert restored.id == action.id
    assert restored.label == action.label


@pytest.mark.parametrize(
    ("label", "modifiers", "key", "canonical_label", "action_id"),
    [
        ("Ctrl+Shift+S", ("lctrl", "lshift"), "s", "Ctrl+Shift+S", "combo:ctrl+shift+s"),
        ("alt+TAB", ("lalt",), "tab", "Alt+Tab", "combo:alt+tab"),
        (
            "LCtrl+RShift+LAlt+RSuper+Delete",
            ("lctrl", "rshift", "lalt", "rsuper"),
            "delete",
            "Ctrl+RShift+Alt+RSuper+Delete",
            "combo:ctrl+rshift+alt+rsuper+delete",
        ),
        ("rCtRl + a", ("rctrl",), "a", "RCtrl+A", "combo:rctrl+a"),
    ],
)
def test_shortcut_parser_is_case_insensitive_and_preserves_sides(
    label: str,
    modifiers: tuple[str, ...],
    key: str,
    canonical_label: str,
    action_id: str,
) -> None:
    shortcut = parse_shortcut(label)

    assert shortcut.modifiers == modifiers
    assert shortcut.key == key
    assert shortcut.label == canonical_label
    assert shortcut.id == action_id


def test_multiple_simultaneous_modifiers_have_combined_hid_mask() -> None:
    shortcut = ShortcutAction(("lctrl", "lshift", "ralt"), "escape")

    assert shortcut.modifier_mask == 0x01 | 0x02 | 0x40
    assert shortcut.usage_id == 0x29


@pytest.mark.parametrize(
    ("modifier", "expected_bit", "expected_usage"),
    [
        ("lctrl", 0x01, 0xE0),
        ("lshift", 0x02, 0xE1),
        ("lalt", 0x04, 0xE2),
        ("lsuper", 0x08, 0xE3),
        ("rctrl", 0x10, 0xE4),
        ("rshift", 0x20, 0xE5),
        ("ralt", 0x40, 0xE6),
        ("rsuper", 0x80, 0xE7),
    ],
)
def test_every_modifier_has_hid_bit_and_usage(
    modifier: str, expected_bit: int, expected_usage: int
) -> None:
    action = ModifierAction(modifier)

    assert action.bit_mask == expected_bit
    assert action.usage_id == expected_usage
    assert MODIFIERS[modifier].bit_mask == expected_bit


def test_modifier_down_and_up_are_explicitly_serialized() -> None:
    down = ModifierAction("LShift", "down")
    up = ModifierAction("LShift", "up")

    assert down.is_key_down
    assert not up.is_key_down
    assert down.id == "mod:lshift"
    assert up.id == "mod:lshift:up"
    assert down.to_json()["event"] == "down"
    assert up.to_json()["event"] == "up"
    assert Action.from_json(up.to_json()) == up


@pytest.mark.parametrize(
    ("media_key", "usage_id"),
    [
        ("vol_up", 0xE9),
        ("vol_down", 0xEA),
        ("mute", 0xE2),
        ("play_pause", 0xCD),
        ("next_track", 0xB0),
        ("previous_track", 0xB2),
    ],
)
def test_media_actions_use_consumer_hid_domain(media_key: str, usage_id: int) -> None:
    action = MediaAction(media_key)

    assert action.id == f"media:{media_key}"
    assert action.usage_id == usage_id
    assert MEDIA_KEYS[media_key].usage_id == usage_id
    assert Action.from_json(action.to_json()) == action


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "",
        {},
        {"type": ""},
        {"type": "unknown"},
        {"type": "key", "key": "not-a-key"},
        {"type": "modifier", "modifier": "hyper", "event": "down"},
        {"type": "modifier", "modifier": "lctrl", "event": "tap"},
        {"type": "shortcut", "modifiers": [], "key": "a"},
        {
            "type": "shortcut",
            "modifiers": ["lctrl", "lshift", "lalt", "lsuper", "rctrl"],
            "key": "a",
        },
        {"type": "shortcut", "modifiers": ["lctrl"], "key": "vol_up"},
        {"type": "media", "key": "unknown"},
    ],
)
def test_invalid_serialized_actions_are_rejected(payload: Any) -> None:
    with pytest.raises(ActionValidationError):
        validate_action(payload)


@pytest.mark.parametrize(
    "label",
    [
        "",
        "A",
        "Ctrl",
        "Ctrl+Mute",
        "Ctrl+Shift+Alt+Super+RCtrl+A",
        "Ctrl++A",
    ],
)
def test_invalid_shortcut_labels_are_rejected(label: str) -> None:
    with pytest.raises(ActionValidationError):
        parse_shortcut(label)


def test_action_type_registry_supports_future_namespaces() -> None:
    @register_action_type
    @dataclass(frozen=True)
    class TestFutureAction(Action):
        value: str
        action_type: ClassVar[str] = "test.future"

        @property
        def id(self) -> str:
            return f"test.future:{self.value}"

        @property
        def label(self) -> str:
            return self.value

        def validate(self) -> "TestFutureAction":
            if not self.value:
                raise ActionValidationError("value cannot be empty")
            return self

        def to_json(self) -> dict[str, Any]:
            return {"type": self.action_type, "value": self.value}

        @classmethod
        def _from_json(cls, value: Mapping[str, Any]) -> "TestFutureAction":
            return cls(value["value"]).validate()

    action = Action.from_json({"type": "test.future", "value": "ready"})

    assert isinstance(action, TestFutureAction)
    assert action.to_json() == {"type": "test.future", "value": "ready"}
