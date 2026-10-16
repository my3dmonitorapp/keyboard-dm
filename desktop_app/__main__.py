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
        with tempfile.TemporaryDirectory(prefix="/project-smoke-") as temp_dir:
            _run_smoke_flow(application, Path(temp_dir) / "smoke-profile.json")
    except Exception as error:
        print(f"Keyboard DM smoke test FAILED: {error}", file=sys.stderr)
        return 1

    print(
        "Keyboard DM smoke test passed: 75-key K07=Ctrl+Shift+S typed profile "
        "save/reopen and JSON verification; "
        "simulated device connected via USB; 12-key K12=Enter project "
        "save/reload verified."
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
