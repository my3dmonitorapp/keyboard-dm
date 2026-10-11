"""Headless import and construction smoke test for the GUI."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from desktop_app.app import Keyboard75Window
from desktop_app.device import SimulatedESP32S3Device
from desktop_app.layouts import L06, L12, L75, make_custom_layout
from desktop_app.profile import save_profile


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
    window.assignment_edit.setText("A")
    window.apply_assignment()

    assert window.dirty is True
    assert window.windowTitle().endswith("(unsaved)")
    assert "Local profile: none — (unsaved)" == (
        window.local_profile_status_label.text()
    )

    window.close()
    application.processEvents()
    assert len(choices) == 1


def test_save_adds_json_suffix_clears_dirty_and_reports_path(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window()
    window.select_key(window.layout.keys[0])
    window.assignment_edit.setText("A")
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

    window._open_profile_dialog()

    assert len(errors) == 1
    assert errors[0][0] == "Could not open local profile"
    assert "Profile key set mismatch" in errors[0][1]
    assert "missing key IDs: K02" in errors[0][1]

    window.close()
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
    window.assignment_edit.setText("Ctrl+X")
    window.apply_assignment()

    assert window.switch_layout(L12) is True

    assignments = {key.key_id: key.assignment for key in window.layout.keys}
    assert len(warnings) == 1
    assert len(window.key_widgets) == 12
    assert assignments["K03"] == "Ctrl+X"
    assert assignments["K07"] == "NONE"
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
