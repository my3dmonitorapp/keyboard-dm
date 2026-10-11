"""Command-line entry point for the Keyboard75 desktop application."""

from __future__ import annotations

import os
import sys


def _display_is_available() -> bool:
    """Return whether Qt can reasonably start a GUI in this environment."""
    if sys.platform.startswith("linux"):
        if os.environ.get("QT_QPA_PLATFORM") in {"offscreen", "minimal"}:
            return True
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def main() -> int:
    """Launch the desktop app, or fail cleanly when no display is present."""
    if not _display_is_available():
        print(
            "Usage: python -m desktop_app (a graphical display is required)",
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
