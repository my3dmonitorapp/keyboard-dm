"""Offscreen GUI coverage for sparse matrix layout generation."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from desktop_app.app import Keyboard75Window, MatrixSetupDialog
from desktop_app.layouts import L06


def test_matrix_setup_action_opens_dimensioned_sparse_cell_editor(monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    observed = {}

    def inspect_dialog(dialog: MatrixSetupDialog) -> QDialog.DialogCode:
        observed["dialog"] = dialog
        observed["row_range"] = (dialog.rows_input.minimum(), dialog.rows_input.maximum())
        observed["col_range"] = (dialog.cols_input.minimum(), dialog.cols_input.maximum())
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(MatrixSetupDialog, "exec", inspect_dialog)
    action = window.findChild(QAction, "matrixLayoutAction")

    assert action is not None
    action.trigger()
    application.processEvents()
    assert observed["dialog"] is window.matrix_setup_dialog
    assert observed["row_range"] == (2, 32)
    assert observed["col_range"] == (2, 64)
    assert window.matrix_setup_dialog.cell_checkboxes

    window.close()
    application.processEvents()


def test_generate_sparse_matrix_and_switch_layout_sources_preserves_state(
    monkeypatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    populated = {(0, 0), (0, 3), (2, 1)}

    def populate_dialog(dialog: MatrixSetupDialog) -> QDialog.DialogCode:
        dialog.rows_input.setValue(3)
        dialog.cols_input.setValue(4)
        for cell in populated:
            dialog.cell_checkboxes[cell].setChecked(True)
        dialog.cell_checkboxes[(2, 1)].click()
        dialog.cell_checkboxes[(2, 1)].click()
        dialog.width_input.setValue(5)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(MatrixSetupDialog, "exec", populate_dialog)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )

    window.findChild(QAction, "matrixLayoutAction").trigger()
    application.processEvents()

    assert window.matrix_config is not None
    assert window.matrix_config.switches == populated
    assert window.matrix_config.key_widths == {(2, 1): 5}
    assert [key.key_id for key in window.layout.keys] == [
        "MX-00-00",
        "MX-00-03",
        "MX-02-01",
    ]
    assert window.layout.keys[-1].w == 5
    assert list(window.key_widgets) == ["MX-00-00", "MX-00-03", "MX-02-01"]

    assert window.switch_layout(L06)
    assert window.layout.name == "L06"
    assert window.switch_to_matrix_layout()
    assert window.matrix_config.switches == populated
    assert [key.key_id for key in window.layout.keys] == [
        "MX-00-00",
        "MX-00-03",
        "MX-02-01",
    ]
    assert window.layout.keys[-1].w == 5

    window._set_dirty(False)
    window.close()
    application.processEvents()
