"""Headless import and construction smoke test for the GUI."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from desktop_app.app import Keyboard75Window


def test_window_constructs_with_75_key_widgets() -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window()

    assert len(window.key_widgets) == 75

    window.close()
    application.processEvents()
