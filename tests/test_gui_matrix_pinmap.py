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

    for editor, pin in zip(
        dialog.row_pin_inputs + dialog.column_pin_inputs,
        [4, 13, 14, 16, 17, 18, 19],
    ):
        editor.setText(str(pin))

    assert config.row_pins[0] == 4
    assert config.column_pins[0] == 16
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
    assert config.row_pins == [13, 14, 16]
    assert config.column_pins == [None, None, None, None]
    assigned = [
        pin for pin in config.row_pins + config.column_pins if pin is not None
    ]
    assert len(set(assigned)) == 3
    assert set(assigned) <= {
        4, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33,
    }
    assert "GPIO assignment is required" in dialog.status_label.text()

    dialog.clear_button.click()

    assert config.row_pins == [None, None, None]
    assert config.column_pins == [None, None, None, None]
    assert all(not editor.text() for editor in dialog.row_pin_inputs)
    assert all(not editor.text() for editor in dialog.column_pin_inputs)
    assert "GPIO assignment is required" in dialog.status_label.text()


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

