"""Headless import and construction smoke test for the GUI."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from desktop_app.app import Keyboard75Window
from desktop_app.action import ShortcutAction, SingleKeyAction
from desktop_app.device import SimulatedESP32S3Device
from desktop_app.layouts import BUILT_IN_LAYOUTS, L06, L12, L75, make_custom_layout
from desktop_app.profile import save_profile
from desktop_app.project import create_project, save_project


def _choose(combo, value: str) -> None:
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def _set_single_key(window: Keyboard75Window, key: str) -> None:
    _choose(window.action_type_combo, "key")
    _choose(window.single_key_combo, key)


def _set_shortcut(
    window: Keyboard75Window, modifiers: tuple[str, ...], key: str
) -> None:
    _choose(window.action_type_combo, "shortcut")
    for modifier in modifiers:
        window.modifier_checkboxes[modifier].setChecked(True)
    _choose(window.shortcut_key_combo, key)


def test_window_constructs_with_75_key_widgets() -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window()

    assert len(window.key_widgets) == 75

    window.close()
    application.processEvents()


def test_assignment_marks_dirty_and_close_offers_discard(monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window()
    choices = []

    def discard(*args, **kwargs):
        choices.append((args, kwargs))
        return QMessageBox.StandardButton.Discard

    monkeypatch.setattr(QMessageBox, "warning", discard)
    window.select_key(window.layout.keys[0])
    _set_single_key(window, "a")
    window.apply_assignment()

    assert window.dirty is True
    assert window.windowTitle().endswith("(unsaved)")
    assert "Local profile: none — (unsaved)" == (
        window.local_profile_status_label.text()
    )

    window.close()
    application.processEvents()
    assert len(choices) == 1


def test_clean_close_does_not_show_unsaved_changes_warning(monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append((args, kwargs)),
    )

    assert window.close() is True
    application.processEvents()

    assert warnings == []


def test_save_adds_json_suffix_clears_dirty_and_reports_path(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window()
    window.select_key(window.layout.keys[0])
    _set_single_key(window, "a")
    window.apply_assignment()

    saved_path = window.save_profile(tmp_path / "local-profile")

    assert saved_path == tmp_path / "local-profile.json"
    assert saved_path.exists()
    assert window.dirty is False
    assert window.local_profile_status_label.text().endswith("local-profile.json")
    assert window.statusBar().currentMessage() == f"Saved to {saved_path}"

    window.close()
    application.processEvents()


def test_wrong_key_set_is_shown_as_profile_error_without_keyerror(
    tmp_path, monkeypatch
) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window()
    path = tmp_path / "one-key.json"
    save_profile(path, {"K01": "A"})
    errors = []

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(path), "JSON profiles (*.json)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, message: errors.append((title, message)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )

    window._open_profile_dialog()

    assert len(errors) == 1
    assert errors[0][0] == "Could not open local profile"
    assert "Profile key set mismatch" in errors[0][1]
    assert "missing key IDs: K02" in errors[0][1]

    window.close()
    application.processEvents()


def test_wrong_key_set_error_preserves_current_profile_and_assignments(
    tmp_path, monkeypatch
) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    valid_path = tmp_path / "valid-six.json"
    mismatched_path = tmp_path / "wrong-nine.json"
    assignments = {key.key_id: "NONE" for key in L06.keys}
    assignments["K03"] = "Ctrl+X"
    save_profile(valid_path, assignments)
    save_profile(
        mismatched_path,
        {key.key_id: "NONE" for key in BUILT_IN_LAYOUTS[1].keys},
    )
    assert window.load_profile(valid_path)
    before = {key.key_id: key.assignment for key in window.layout.keys}
    errors = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(mismatched_path), "JSON profiles (*.json)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, message: errors.append((title, message)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )

    window._open_profile_dialog()

    assert errors and errors[0][0] == "Could not open local profile"
    assert "Profile key set mismatch" in errors[0][1]
    assert "additional key IDs: K07, K08, K09" in errors[0][1]
    assert window.current_profile_path == valid_path
    assert {key.key_id: key.assignment for key in window.layout.keys} == before
    assert window.layout.keys[2].assignment == ShortcutAction(("lctrl",), "x").to_json()

    window._set_dirty(False)
    window.close()
    application.processEvents()


@pytest.mark.parametrize(
    "layout",
    BUILT_IN_LAYOUTS,
    ids=[layout.name for layout in BUILT_IN_LAYOUTS],
)
def test_layout_menu_selection_save_and_reopen_has_stable_widgets(
    tmp_path, layout
) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window()
    action = window.findChild(QAction, f"layoutAction_{layout.name}")

    assert action is not None
    action.trigger()
    application.processEvents()
    expected_ids = [f"K{number:02d}" for number in range(1, layout.key_count + 1)]
    assert list(window.key_widgets) == expected_ids
    assert len(window.key_widgets) == layout.key_count

    last_id = expected_ids[-1]
    window.key_widgets[last_id].click()
    _set_single_key(window, "a")
    window.apply_button.click()
    path = window.save_profile(tmp_path / f"{layout.name.lower()}-gui.json")
    window.close()
    application.processEvents()

    reopened = Keyboard75Window(layout=layout)
    assert reopened.load_profile(path)
    assert list(reopened.key_widgets) == expected_ids
    assert len(reopened.key_widgets) == layout.key_count
    assert reopened.layout.keys[-1].key_id == last_id
    assert reopened.layout.keys[-1].assignment == SingleKeyAction("a").to_json()

    reopened._set_dirty(False)
    reopened.close()
    application.processEvents()


def test_layout_switch_preserves_shared_assignments_and_defaults_new_keys(
    monkeypatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: (
            warnings.append((args, kwargs)) or QMessageBox.StandardButton.Discard
        ),
    )
    window.connect_device()
    window.select_key(window.layout.keys[2])
    _set_shortcut(window, ("lctrl",), "x")
    window.apply_assignment()

    assert window.switch_layout(L12) is True

    assignments = {key.key_id: key.assignment for key in window.layout.keys}
    assert len(warnings) == 1
    assert len(window.key_widgets) == 12
    assert assignments["K03"] == ShortcutAction(("lctrl",), "x").to_json()
    assert assignments["K07"] is None
    assert window.dirty is True
    assert len(window.device.get_key_states()) == 12
    assert window.device.get_key_states()["K03"] == "Ctrl+X"
    assert window.device.get_key_states()["K07"] == "NONE"

    window._set_dirty(False)
    window.close()
    application.processEvents()


def test_initial_layout_sets_injected_device_key_set() -> None:
    application = QApplication.instance() or QApplication([])
    device = SimulatedESP32S3Device()
    window = Keyboard75Window(layout=L06, device=device)
    window.connect_device()

    assert list(device.get_key_states()) == [f"K{number:02d}" for number in range(1, 7)]

    window.disconnect_device()
    window.close()
    application.processEvents()


def test_layout_geometry_and_provisional_strip_follow_active_layout() -> None:
    application = QApplication.instance() or QApplication([])
    small_window = Keyboard75Window(layout=L06)
    large_window = Keyboard75Window(layout=L75)
    custom_window = Keyboard75Window(layout=make_custom_layout(6, cols=3))

    small_window.show()
    large_window.show()
    custom_window.show()
    application.processEvents()

    assert small_window.size() != large_window.size()
    assert small_window.width() < large_window.width()
    assert large_window.layout_banner.isVisible()
    assert not custom_window.layout_banner.isVisible()

    small_window.close()
    large_window.close()
    custom_window.close()
    application.processEvents()


def test_switching_projects_preserves_independent_assignments_and_device_state(
    tmp_path,
) -> None:
    application = QApplication.instance() or QApplication([])
    first_assignments = {key.key_id: "NONE" for key in L06.keys}
    second_assignments = {key.key_id: "NONE" for key in L12.keys}
    first_assignments["K01"] = "A"
    second_assignments["K01"] = "B"
    first_path = save_project(
        tmp_path / "first",
        create_project("First", L06, first_assignments),
    )
    second_path = save_project(
        tmp_path / "second",
        create_project("Second", L12, second_assignments),
    )
    window = Keyboard75Window(layout=L06)
    window.connect_device()

    assert window.load_project(first_path)
    assert window.layout.key_count == 6
    assert window.layout.keys[0].assignment == SingleKeyAction("a").to_json()
    assert window.device.get_key_states()["K01"] == "A"
    assert "L06 (6 keys)" in window.simulated_device_status_label.text()

    assert window.load_project(second_path)
    assert window.layout.key_count == 12
    assert window.layout.keys[0].assignment == SingleKeyAction("b").to_json()
    assert window.device.get_key_states()["K01"] == "B"
    assert "L12 (12 keys)" in window.simulated_device_status_label.text()

    assert window.load_project(first_path)
    assert window.layout.keys[0].assignment == SingleKeyAction("a").to_json()
    assert len(window.key_widgets) == 6

    window.disconnect_device()
    window.close()
    application.processEvents()
