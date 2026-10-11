"""Structured action-editor coverage for Milestone S1.2 T3."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop_app.action import (
    Action,
    MEDIA_KEYS,
    ModifierAction,
    ShortcutAction,
    SingleKeyAction,
)
from desktop_app.app import Keyboard75Window
from desktop_app.layouts import L06, L09


def _choose(combo, value: str) -> None:
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


@pytest.fixture
def action_window():
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    window.select_key(window.layout.keys[0])
    yield window
    window._set_dirty(False)
    window.close()
    application.processEvents()


def test_single_key_apply_is_typed_labeled_and_reloads_into_editor(
    action_window,
) -> None:
    _choose(action_window.action_type_combo, "key")
    _choose(action_window.single_key_combo, "f5")

    action_window.apply_button.click()

    expected = SingleKeyAction("f5").to_json()
    assert action_window.layout.keys[0].assignment == expected
    assert action_window.key_widgets["K01"].text() == "K01\nF5"
    action_window.select_key(action_window.layout.keys[1])
    action_window.select_key(action_window.layout.keys[0])
    assert action_window.action_type_combo.currentData() == "key"
    assert action_window.single_key_combo.currentData() == "f5"


@pytest.mark.parametrize(
    "modifier",
    ("lctrl", "rctrl", "lshift", "rshift", "lalt", "ralt", "lsuper", "rsuper"),
)
def test_each_sided_modifier_serializes_as_modifier_action(
    action_window, modifier
) -> None:
    _choose(action_window.action_type_combo, "modifier")
    action_window.modifier_checkboxes[modifier].setChecked(True)

    action_window.apply_button.click()

    assert action_window.layout.keys[0].assignment == ModifierAction(modifier).to_json()


@pytest.mark.parametrize(
    ("modifiers", "key"),
    (
        (("lctrl",), "c"),
        (("lctrl",), "v"),
        (("lctrl", "lshift"), "s"),
        (("lalt",), "tab"),
    ),
)
def test_shortcuts_serialize_exactly_with_simultaneous_modifiers(
    action_window, modifiers, key
) -> None:
    _choose(action_window.action_type_combo, "shortcut")
    for modifier in modifiers:
        action_window.modifier_checkboxes[modifier].setChecked(True)
    _choose(action_window.shortcut_key_combo, key)

    action_window.apply_button.click()

    expected = ShortcutAction(modifiers, key)
    assert action_window.layout.keys[0].assignment == expected.to_json()
    assert expected.label in action_window.key_widgets["K01"].text()


@pytest.mark.parametrize("media_key", tuple(MEDIA_KEYS))
def test_each_media_key_serializes_with_consumer_hid_usage(
    action_window, media_key
) -> None:
    _choose(action_window.action_type_combo, "media")
    _choose(action_window.media_key_combo, media_key)

    action_window.apply_button.click()

    payload = action_window.layout.keys[0].assignment
    restored = Action.from_json(payload)
    assert payload == {"type": "media", "key": media_key}
    assert restored.usage_id == MEDIA_KEYS[media_key].usage_id


def test_none_and_clear_remove_action_and_restore_base_keycap(action_window) -> None:
    _choose(action_window.action_type_combo, "key")
    _choose(action_window.single_key_combo, "a")
    action_window.apply_button.click()

    action_window.clear_button.click()

    assert action_window.layout.keys[0].assignment is None
    assert action_window.action_type_combo.currentData() == "none"
    assert action_window.key_widgets["K01"].text() == "K01"
    assert action_window.key_widgets["K01"].toolTip() == "K01"


def test_gui_typed_actions_save_and_reload_round_trip(tmp_path, action_window) -> None:
    _choose(action_window.action_type_combo, "shortcut")
    action_window.modifier_checkboxes["rctrl"].setChecked(True)
    action_window.modifier_checkboxes["rshift"].setChecked(True)
    _choose(action_window.shortcut_key_combo, "s")
    action_window.apply_button.click()
    expected = ShortcutAction(("rctrl", "rshift"), "s").to_json()
    path = action_window.save_profile(tmp_path / "typed-actions")

    reopened = Keyboard75Window(layout=L06)
    assert reopened.load_profile(path)
    assert reopened.layout.keys[0].assignment == expected
    reopened.select_key(reopened.layout.keys[0])
    assert reopened.action_type_combo.currentData() == "shortcut"
    assert reopened.modifier_checkboxes["rctrl"].isChecked()
    assert reopened.modifier_checkboxes["rshift"].isChecked()
    assert reopened.shortcut_key_combo.currentData() == "s"
    reopened._set_dirty(False)
    reopened.close()


@pytest.mark.parametrize("layout", (L06, L09), ids=("6-key", "9-key"))
def test_action_editor_fits_small_layouts(layout) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=layout)
    window.show()
    application.processEvents()

    assert window.inspector.width() == 250
    assert window.inspector.sizeHint().width() <= 250
    assert window.inspector.height() <= window.centralWidget().height()
    assert window.width() <= 700

    window.close()
    application.processEvents()
