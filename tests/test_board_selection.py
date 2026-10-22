"""Board selection, target validation, and persistence regressions."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from desktop_app.app import Keyboard75Window
from desktop_app.matrix_model import MatrixConfig
from desktop_app.profile import create_profile, load_profile, save_profile
from desktop_app.project import create_project, load_project, save_project
from desktop_app.serialization import build_firmware_config


@pytest.mark.parametrize(
    ("chip_class", "row_pins", "column_pins"),
    (
        ("esp32", [4, 13], [14, 16]),
        ("esp32c3", [0, 1], [3, 4]),
    ),
)
def test_selected_board_round_trips_through_profile_and_project(
    tmp_path, chip_class, row_pins, column_pins
) -> None:
    config = MatrixConfig(
        rows=2,
        cols=2,
        switches={(0, 0), (0, 1), (1, 0), (1, 1)},
        row_pins=row_pins,
        column_pins=column_pins,
    )
    assignments = {key_id: None for key_id in config.keys()}

    profile_path = tmp_path / f"{chip_class}.json"
    save_profile(profile_path, create_profile(assignments, chip_class=chip_class))
    assert load_profile(profile_path)["chip_class"] == chip_class

    document = create_project(
        chip_class,
        config.to_layout(chip_class),
        assignments,
        profile_path,
        config,
        chip_class=chip_class,
    )
    loaded = load_project(save_project(tmp_path / chip_class, document))
    assert loaded.chip_class == chip_class
    assert build_firmware_config(loaded, chip_class=loaded.chip_class)[
        "chip_class"
    ] == chip_class


def test_legacy_device_marker_loads_as_classic_target(tmp_path) -> None:
    profile = create_profile({"K01": None})
    profile.pop("chip_class")
    profile["device"] = "/project-esp32s3"
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(profile), encoding="utf-8")

    loaded = load_profile(path)
    assert loaded["device"] == "/keyboard-dm-profile"
    assert loaded["chip_class"] == "esp32"


def test_board_selector_drives_pinmap_validation(monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    config = MatrixConfig(
        rows=1,
        cols=1,
        switches={(0, 0)},
        row_pins=[11],
        column_pins=[4],
    )
    window = Keyboard75Window(layout=config.to_layout())
    assert window.board_combo.currentData() == "esp32"
    assert [window.board_combo.itemText(index) for index in range(2)] == [
        "classic ESP32-WROOM-32",
        "ESP32-C3 Super Mini",
    ]
    window.matrix_config = config
    window.matrix_layout = config.to_layout()
    window.matrix_pinmap_action.setEnabled(True)
    window.board_combo.setCurrentIndex(window.board_combo.findData("esp32c3"))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    dialog = window.open_matrix_pinmap()

    assert window.board_combo.currentText() == "ESP32-C3 Super Mini"
    assert window._firmware_chip_class == "esp32c3"
    assert dialog is not None
    assert "not available" in dialog.row_pin_messages[0].text()
    assert dialog.column_pin_messages[0].text() == ""

    window._set_dirty(False)
    window.close()
    application.processEvents()
