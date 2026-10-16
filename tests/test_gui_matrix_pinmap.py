"""Offscreen coverage for live matrix GPIO pin assignment."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop_app.app import Keyboard75Window, MatrixPinmapDialog
from desktop_app.layouts import L06
from desktop_app.matrix_model import MatrixConfig


@pytest.fixture
def pinmap_window():
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    config = MatrixConfig(
        rows=3,
        cols=4,
        switches={(0, 0), (0, 3), (2, 1)},
    )
    window.matrix_config = config
    window.matrix_layout = config.to_layout()
    window._install_layout(config.to_layout())
    dialog = MatrixPinmapDialog(config, window)
    yield window, dialog, config
    dialog.close()
    window._set_dirty(False)
    window.close()
    application.processEvents()


def test_pin_edits_update_model_and_report_conflict_and_range_live(
    pinmap_window,
) -> None:
    _window, dialog, config = pinmap_window

    dialog.row_pin_inputs[0].setText("4")
    dialog.column_pin_inputs[0].setText("8")

    assert config.row_pins[0] == 4
    assert config.column_pins[0] == 8
    assert dialog.status_label.text() == "Pinmap valid"

    dialog.column_pin_inputs[1].setText("4")

    assert config.column_pins[1] == 4
    assert "GPIO pin 4 is assigned more than once (row 0 and column 1)" in (
        dialog.status_label.text()
    )

    dialog.column_pin_inputs[1].setText("40")

    assert config.column_pins[1] == 40
    assert "outside allowed range 0..39" in dialog.status_label.text()


def test_pin_range_suggest_and_clear_are_model_backed(pinmap_window) -> None:
    _window, dialog, config = pinmap_window
    dialog.min_pin_input.setValue(10)
    dialog.max_pin_input.setValue(16)

    dialog.suggest_button.click()

    assert config.min_pin == 10
    assert config.max_pin == 16
    assert config.row_pins == [10, 11, 12]
    assert config.column_pins == [13, 14, 15, 16]
    assert len(set(config.row_pins + config.column_pins)) == 7
    assert dialog.status_label.text() == "Pinmap valid"

    dialog.clear_button.click()

    assert config.row_pins == [None, None, None]
    assert config.column_pins == [None, None, None, None]
    assert all(not editor.text() for editor in dialog.row_pin_inputs)
    assert all(not editor.text() for editor in dialog.column_pin_inputs)
    assert dialog.status_label.text() == "Pinmap valid"


def test_pinmap_action_is_available_only_on_active_matrix(
    pinmap_window, monkeypatch
) -> None:
    window, _dialog, config = pinmap_window
    opened = []

    def observe(dialog: MatrixPinmapDialog):
        opened.append(dialog.config)
        return 0

    monkeypatch.setattr(MatrixPinmapDialog, "exec", observe)

    assert window.matrix_pinmap_action.isEnabled()
    window.matrix_pinmap_action.trigger()
    assert opened == [config]

    window._set_dirty(False)
    assert window.switch_layout(L06)
    assert not window.matrix_pinmap_action.isEnabled()

