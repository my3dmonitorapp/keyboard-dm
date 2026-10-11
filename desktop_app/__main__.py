"""Command-line entry point for the Keyboard75 desktop application."""

from __future__ import annotations

import argparse
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
    from .app import Keyboard75Window

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

        window.assignment_edit.setText("A")
        window.apply_button.click()
        _require(window.selected_key.assignment == "A", "K07 assignment was not A")

        window.save_profile(str(profile_path))
        window.assignment_edit.setText("NONE")
        window.apply_button.click()
        _require(
            window.selected_key.assignment == "NONE",
            "could not reset K07 before profile reload",
        )
        window.load_profile(str(profile_path))
        _require(
            window.selected_key.assignment == "A"
            and window.assignment_edit.text() == "A",
            "saved K07 assignment did not survive profile reload",
        )

        window.connect_device()
        _require(window.device.is_connected(), "simulated device did not connect")
        window.set_host_connected(True)
        _require(
            window.device.get_transport() == "usb",
            "simulated device did not prefer USB for a connected host",
        )
        window.assignment_edit.setText("A")
        window.apply_button.click()
        _require(
            window.device.get_key_states().get("K07") == "A",
            "simulated device did not store K07 assignment A",
        )
    finally:
        if window.device.is_connected():
            window.disconnect_device()
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
        print(f"Keyboard75 smoke test FAILED: {error}", file=sys.stderr)
        return 1

    print(
        "Keyboard75 smoke test passed: 75 key widgets; K07=A profile "
        "round-trip; simulated device connected via USB; device K07=A."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the desktop app or run its headless smoke test."""
    parser = argparse.ArgumentParser(description="Keyboard75 desktop application")
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
