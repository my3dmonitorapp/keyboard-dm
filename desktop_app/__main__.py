"""Command-line entry point for the Keyboard DM desktop application."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence


def _display_is_available() -> bool:
    """Return whether Qt can reasonably start a GUI in this environment."""
    if sys.platform.startswith("linux"):
        if os.environ.get("QT_QPA_PLATFORM") in {"offscreen", "minimal"}:
            return True
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def _require(condition: bool, message: str) -> None:
    """Raise a readable smoke-test failure when *condition* is false."""
    if not condition:
        raise RuntimeError(message)


def _run_matrix_smoke_flow(project_path: Path) -> None:
    """Exercise matrix conversion, v3 persistence, actions, and simulation."""
    from .action import MediaAction, ModifierAction, ShortcutAction
    from .device import SimulatedESP32S3Device
    from .matrix_model import MatrixConfig
    from .project import PROJECT_VERSION, create_project, load_project, save_project

    small = MatrixConfig(
        rows=3,
        cols=4,
        switches={(0, 0), (0, 3), (1, 1), (2, 0), (2, 2)},
        key_widths={(0, 0): 3, (1, 1): 4, (2, 2): 7},
        key_labels={(0, 0): "Esc", (1, 1): "Fn", (2, 2): "Space"},
        row_pins=[1, 3, 5],
        column_pins=[7, 9, 11, 13],
    )
    large_switches = set().union(
        ((0, column) for column in range(14)),
        ((1, column) for column in range(15)),
        ((2, column) for column in range(13)),
        ((3, column) for column in range(12)),
        ((4, column) for column in range(11)),
    )
    large = MatrixConfig(
        rows=5,
        cols=15,
        switches=large_switches,
        key_widths={(0, 0): 3, (1, 14): 4, (2, 12): 5, (4, 10): 12},
        key_labels={
            (0, 0): "Esc",
            (1, 14): "Backspace",
            (2, 12): "Enter",
            (4, 10): "Space",
        },
        row_pins=[0, 2, 4, 5, 12],
        column_pins=list(range(13, 28)),
    )

    for name, config, row_counts in (
        ("3x4", small, [2, 1, 2]),
        ("5x15", large, [14, 15, 13, 12, 11]),
    ):
        valid, errors = config.validate()
        _require(valid, f"{name} matrix was invalid: {'; '.join(errors)}")
        layout = config.to_layout(f"Smoke {name}")
        _require(layout.label == "matrix", f"{name} did not convert to a matrix layout")
        _require(
            [sum(row == index for row, _column in config.switches)
             for index in range(config.rows)] == row_counts,
            f"{name} sparse row populations changed",
        )
        _require(
            [key.key_id for key in layout.keys] == config.keys(),
            f"{name} layout key IDs did not match its populated cells",
        )

    layout = large.to_layout("Smoke 5x15 Matrix")
    assignments = {key_id: None for key_id in large.keys()}
    assignments["MX-00-00"] = ShortcutAction(("lctrl", "lshift"), "s").to_json()
    assignments["MX-02-12"] = ModifierAction("ralt", "up").to_json()
    assignments["MX-04-10"] = MediaAction("play_pause").to_json()
    document = create_project(
        "Smoke Matrix", layout, assignments, matrix_config=large
    )
    saved_path = save_project(project_path, document)
    saved_document = json.loads(saved_path.read_text(encoding="utf-8"))
    _require(
        saved_document.get("project_version") == PROJECT_VERSION == 3,
        "matrix project was not saved as version 3",
    )

    reloaded = load_project(saved_path)
    _require(reloaded.matrix_config is not None, "reloaded project lost matrix data")
    _require(
        reloaded.matrix_config.to_dict() == large.to_dict(),
        "reloaded matrix dictionary was not equal to the saved matrix",
    )
    _require(reloaded.assignments == assignments, "reloaded typed actions changed")
    _require(
        [key.key_id for key in reloaded.layout.keys] == large.keys(),
        "reloaded matrix key IDs changed",
    )
    _require(reloaded.matrix_config.row_pins == large.row_pins, "row pins changed")
    _require(
        reloaded.matrix_config.column_pins == large.column_pins,
        "column pins changed",
    )
    _require(reloaded.matrix_config.key_widths == large.key_widths, "widths changed")
    _require(reloaded.matrix_config.key_labels == large.key_labels, "labels changed")

    device = SimulatedESP32S3Device(reloaded.matrix_config.keys())
    device.set_matrix_config(reloaded.matrix_config)
    _require(not device.get_pressed_key_ids(), "matrix device started with a pressed key")
    device.press_matrix_key(4, 10)
    _require(
        device.get_pressed_key_ids() == {"MX-04-10"},
        "matrix press did not set the expected pressed key ID",
    )
    device.release_matrix_key(4, 10)
    _require(not device.get_pressed_key_ids(), "matrix release did not clear pressed state")


def _run_smoke_flow(application: object, profile_path: Path) -> None:
    """Exercise the real window, profile, and simulated-device integrations."""
    from .action import ShortcutAction, SingleKeyAction
    from .app import Keyboard75Window
    from .layouts import L12

    def choose(combo: object, value: str) -> None:
        index = combo.findData(value)
        _require(index >= 0, f"editor option {value!r} was not available")
        combo.setCurrentIndex(index)

    window = Keyboard75Window()
    try:
        application.processEvents()

        _require(
            len(window.key_widgets) == 75,
            f"expected 75 key widgets, found {len(window.key_widgets)}",
        )

        window.key_widgets["K07"].click()
        application.processEvents()
        _require(
            window.selected_key is not None
            and window.selected_key.key_id == "K07",
            "K07 was not selected",
        )

        choose(window.action_type_combo, "shortcut")
        window.modifier_checkboxes["lctrl"].setChecked(True)
        window.modifier_checkboxes["lshift"].setChecked(True)
        choose(window.shortcut_key_combo, "s")
        window.apply_button.click()
        shortcut = ShortcutAction(("lctrl", "lshift"), "s")
        _require(
            window.selected_key.assignment == shortcut.to_json(),
            "K07 assignment was not Ctrl+Shift+S",
        )

        window.save_profile(str(profile_path))
        saved_document = json.loads(profile_path.read_text(encoding="utf-8"))
        _require(
            saved_document["profile_version"] == 2
            and saved_document["keys"]["K07"]["assignment"] == shortcut.to_json(),
            "saved profile JSON did not contain the typed K07 shortcut",
        )

        reopened = Keyboard75Window()
        try:
            _require(reopened.load_profile(profile_path), "could not reopen S1.2 profile")
            reopened.key_widgets["K07"].click()
            _require(
                reopened.selected_key.assignment == shortcut.to_json()
                and reopened.action_type_combo.currentData() == "shortcut"
                and reopened.modifier_checkboxes["lctrl"].isChecked()
                and reopened.modifier_checkboxes["lshift"].isChecked()
                and reopened.shortcut_key_combo.currentData() == "s",
                "typed K07 shortcut did not survive profile reopen",
            )
        finally:
            reopened._set_dirty(False)
            reopened.close()
            application.processEvents()

        window.connect_device()
        _require(window.device.is_connected(), "simulated device did not connect")
        window.set_host_connected(True)
        _require(
            window.device.get_transport() == "usb",
            "simulated device did not prefer USB for a connected host",
        )
        window.apply_button.click()
        _require(
            window.device.get_key_states().get("K07") == "Ctrl+Shift+S",
            "simulated device did not store the K07 shortcut",
        )

        # Exercise a second key count and project persistence in the same real
        # GUI flow. The explicit clean state avoids an interactive prompt.
        window._set_dirty(False)
        _require(window.switch_layout(L12), "could not switch to the L12 layout")
        _require(
            len(window.key_widgets) == 12
            and list(window.key_widgets) == [
                f"K{number:02d}" for number in range(1, 13)
            ],
            "L12 did not build 12 stable key widgets",
        )
        window._set_dirty(False)
        project_path = window.new_project("Smoke 12", profile_path.parent)
        _require(project_path is not None, "could not create the 12-key smoke project")
        window.key_widgets["K12"].click()
        choose(window.action_type_combo, "key")
        choose(window.single_key_combo, "enter")
        window.apply_button.click()
        window.save_project()
        window.clear_button.click()
        window._set_dirty(False)
        _require(window.load_project(project_path), "could not reload smoke project")
        _require(
            window.layout.key_count == 12
            and window.layout.keys[-1].key_id == "K12"
            and window.layout.keys[-1].assignment == SingleKeyAction("enter").to_json(),
            "12-key project assignment did not survive save and reload",
        )
        _require(
            window.device.get_key_states().get("K12") == "Enter",
            "simulated device did not adopt the reloaded 12-key project",
        )
    finally:
        if window.device.is_connected():
            window.disconnect_device()
        # Avoid an interactive close prompt in the deterministic smoke runner.
        window._set_dirty(False)
        window.close()
        application.processEvents()


def run_smoke() -> int:
    """Run the deterministic offscreen smoke test and return a process status."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    try:
        from PySide6.QtWidgets import QApplication

        application = QApplication.instance() or QApplication([sys.argv[0]])
        with tempfile.TemporaryDirectory(prefix="kb-dm-smoke-") as temp_dir:
            temp_path = Path(temp_dir)
            _run_smoke_flow(application, temp_path / "smoke-profile.json")
            _run_matrix_smoke_flow(temp_path / "smoke-matrix")
    except Exception as error:
        print(f"Keyboard DM smoke test FAILED: {error}", file=sys.stderr)
        return 1

    print(
        "Keyboard DM smoke test passed: 75-key K07=Ctrl+Shift+S typed profile "
        "save/reopen and JSON verification; "
        "simulated device connected via USB; 12-key K12=Enter project "
        "save/reload verified; matrix 3x4 and sparse 5x15 conversion, v3 typed-action "
        "round-trip, pins/widths/labels, and press/release verified."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the desktop app or run its headless smoke test."""
    parser = argparse.ArgumentParser(description="Keyboard DM desktop application")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="run a headless application smoke test and exit",
    )
    arguments = parser.parse_args(argv)

    if arguments.smoke:
        return run_smoke()

    if not _display_is_available():
        print(
            "Usage: python -m desktop_app (a graphical display is required; "
            "use --smoke for a headless check)",
            file=sys.stderr,
        )
        return 1

    from PySide6.QtWidgets import QApplication

    from .app import Keyboard75Window

    application = QApplication(sys.argv)
    window = Keyboard75Window()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
