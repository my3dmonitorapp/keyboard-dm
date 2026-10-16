"""Offscreen coverage for per-key matrix editing."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from desktop_app.action import ShortcutAction
from desktop_app.app import Keyboard75Window
from desktop_app.layouts import L06
from desktop_app.matrix_model import MatrixConfig


@pytest.fixture
def matrix_window():
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    config = MatrixConfig(rows=2, cols=3, switches={(0, 0), (0, 1)})
    window.matrix_config = config
    window.matrix_layout = config.to_layout()
    window._install_layout(config.to_layout())
    window.select_key(window.layout.keys[0])
    yield window
    window._set_dirty(False)
    window.close()
    application.processEvents()


def _choose_width(window: Keyboard75Window, half_units: int) -> None:
    index = window.matrix_width_input.findData(half_units)
    assert index >= 0
    window.matrix_width_input.setCurrentIndex(index)


def test_matrix_key_width_and_label_update_layout_and_visual(matrix_window) -> None:
    key_id = matrix_window.selected_key.key_id
    original_width = matrix_window.key_widgets[key_id].width()

    _choose_width(matrix_window, 4)
    matrix_window.matrix_label_input.setText("Wide")

    assert matrix_window.matrix_config.key_widths[(0, 0)] == 4
    assert matrix_window.matrix_config.key_labels[(0, 0)] == "Wide"
    assert matrix_window.selected_key.key_id == key_id
    assert matrix_window.selected_key.w == 4
    assert matrix_window.selected_key.label == "Wide"
    assert matrix_window.key_widgets[key_id].width() > original_width
    assert matrix_window.key_widgets[key_id].text() == "Wide"

    _choose_width(matrix_window, 2)
    matrix_window.matrix_label_input.clear()

    assert (0, 0) not in matrix_window.matrix_config.key_widths
    assert (0, 0) not in matrix_window.matrix_config.key_labels
    assert matrix_window.selected_key.key_id == key_id
    assert matrix_window.key_widgets[key_id].width() == original_width


def test_visual_position_edit_keeps_electrical_identity(matrix_window) -> None:
    key_id = matrix_window.selected_key.key_id
    mapping = matrix_window.matrix_config.cell_to_key_id()
    matrix_window.matrix_dx_input.setValue(3)
    matrix_window.matrix_dy_input.setValue(1)

    assert matrix_window.apply_selected_matrix_visual_offset()

    assert matrix_window.selected_key.key_id == key_id
    assert matrix_window.matrix_config.cell_to_key_id() == mapping
    assert matrix_window.matrix_config.key_visual_offsets[(0, 0)] == (3, 1)
    assert (matrix_window.selected_key.x, matrix_window.selected_key.y) == (0, 0)
    assert (matrix_window.selected_key.dx, matrix_window.selected_key.dy) == (3, 1)


def test_move_matrix_key_migrates_metadata_assignment_and_rejects_occupied(
    matrix_window, monkeypatch
) -> None:
    shortcut = ShortcutAction(("lctrl",), "c").to_json()
    matrix_window.selected_key.assignment = shortcut
    _choose_width(matrix_window, 4)
    matrix_window.matrix_label_input.setText("Copy")

    matrix_window.matrix_row_input.setValue(1)
    matrix_window.matrix_col_input.setValue(2)
    assert matrix_window.move_selected_matrix_key()

    assert (0, 0) not in matrix_window.matrix_config.switches
    assert (1, 2) in matrix_window.matrix_config.switches
    assert matrix_window.matrix_config.key_widths[(1, 2)] == 4
    assert matrix_window.matrix_config.key_labels[(1, 2)] == "Copy"
    assert "MX-00-00" not in matrix_window.key_widgets
    assert matrix_window.selected_key.key_id == "MX-01-02"
    assert matrix_window.selected_key.assignment == shortcut
    assert matrix_window.action_type_combo.currentData() == "shortcut"
    assert matrix_window.shortcut_key_combo.currentData() == "c"
    assert matrix_window.modifier_checkboxes["lctrl"].isChecked()

    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append(args[2]),
    )
    matrix_window.matrix_row_input.setValue(0)
    matrix_window.matrix_col_input.setValue(1)

    assert not matrix_window.move_selected_matrix_key()
    assert warnings and "already occupied" in warnings[0]
    assert matrix_window.selected_key.key_id == "MX-01-02"
    assert matrix_window.matrix_config.switches == {(0, 1), (1, 2)}

    matrix_window.matrix_row_input.setValue(2)
    matrix_window.matrix_col_input.setValue(0)
    assert not matrix_window.move_selected_matrix_key()
    assert "outside the matrix bounds" in warnings[-1]
    assert matrix_window.matrix_config.switches == {(0, 1), (1, 2)}
