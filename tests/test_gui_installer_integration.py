"""Offscreen integration tests for the installer in the real main window."""

from __future__ import annotations

import hashlib
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QPushButton, QStackedWidget, QWidget

from desktop_app.app import Keyboard75Window
from desktop_app.esptool_adapter import EsptoolChipInfo, MockFlashBackend, PortInfo
from desktop_app.installer import InstallOutcome, InstallerState
from desktop_app.installer_panel import InstallerPanel
from desktop_app.manifest import FirmwareManifest, manifest_from_dict

PORT = PortInfo("/dev/ttyMOCK0", "Injected test port", "Test")
FLASH_SIZE = 4 * 1024 * 1024


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


def _manifest(payload: bytes = b"integrated-panel-test") -> FirmwareManifest:
    return manifest_from_dict(
        {
            "schema": "keyboard-dm/firmware-manifest/1",
            "name": "integrated-panel-test",
            "version": "1.0",
            "chip_family": "esp32c3",
            "flash_size": "4MB",
            "flash_mode": "dio",
            "flash_freq": "80m",
            "images": [
                {
                    "file_name": "integrated-panel.bin",
                    "offset": 0x1000,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                }
            ],
        }
    )


def _backend() -> MockFlashBackend:
    backend = MockFlashBackend()
    backend.add_port(
        PORT,
        EsptoolChipInfo(5, "ESP32C3", 4, (), FLASH_SIZE, "80m", "dio"),
        b"\xff" * FLASH_SIZE,
    )
    return backend


def _configure_panel(
    panel: InstallerPanel,
    tmp_path,
    *,
    payload: bytes = b"integrated-panel-test",
) -> None:
    manifest = _manifest(payload)
    panel._backend = _backend()
    panel._discover_ports = lambda: [PORT]
    panel._manifests = (manifest,)
    panel._artifact_source = lambda _name: payload
    panel._backup_dir = str(tmp_path)
    panel.firmware_combo.clear()
    panel.firmware_combo.addItem(
        f"{manifest.name} {manifest.version} ({manifest.chip_family})",
        manifest,
    )
    panel.refresh_ports()


def _wait_for(application: QApplication, predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        application.processEvents()
        if time.monotonic() >= deadline:
            pytest.fail("timed out waiting for integrated installer panel")
        time.sleep(0.005)
    application.processEvents()


def test_main_window_reaches_installer_and_returns_to_editor(application) -> None:
    window = Keyboard75Window()
    stack = window.findChild(QStackedWidget, "mainPageStack")
    editor = window.findChild(QWidget, "editorPage")
    panel = window.findChild(InstallerPanel, "installerPanel")
    action = window.findChild(QAction, "firmwareInstallerAction")

    assert stack is window.page_stack
    assert editor is window.editor_page
    assert panel is window.installer_panel
    assert action is window.firmware_installer_action
    assert stack.currentWidget() is editor
    assert isinstance(panel._backend, MockFlashBackend)

    action.trigger()
    application.processEvents()
    assert action.isChecked()
    assert stack.currentWidget() is panel

    action.trigger()
    application.processEvents()
    assert not action.isChecked()
    assert stack.currentWidget() is editor
    assert len(window.key_widgets) == 75
    assert window.findChild(QPushButton, "keyButton_K01") is window.key_widgets["K01"]

    window.close()
    application.processEvents()


def test_integrated_panel_completes_mock_install_and_restores_digest(
    application, tmp_path
) -> None:
    window = Keyboard75Window()
    panel = window.installer_panel
    _configure_panel(panel, tmp_path)
    window.firmware_installer_action.trigger()

    panel.start_button.click()
    _wait_for(application, lambda: panel.current_state is InstallerState.DONE)
    _wait_for(application, lambda: not panel.is_running)

    assert panel.state_label.text() == "State: DONE"
    assert os.path.isfile(panel.backup_path_label.text())
    assert panel.backup_digest_label.text() == hashlib.sha256(
        b"\xff" * FLASH_SIZE
    ).hexdigest()

    window.close()
    application.processEvents()


class _CancellableEngine:
    def __init__(self, phase_callbacks, **_kwargs) -> None:
        self._callbacks = phase_callbacks
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self, _port, _manifest) -> InstallOutcome:
        for callback in self._callbacks:
            callback(InstallerState.FLASHING, "waiting for cancellation")
        while not self._cancelled:
            time.sleep(0.005)
        return InstallOutcome(InstallerState.CANCELLED, "cancelled by test")


def test_integrated_panel_cancel_reaches_cancelled(application, tmp_path) -> None:
    window = Keyboard75Window()
    panel = window.installer_panel
    _configure_panel(panel, tmp_path)
    panel._engine_factory = lambda **kwargs: _CancellableEngine(**kwargs)
    window.firmware_installer_action.trigger()

    panel.start_button.click()
    _wait_for(application, lambda: panel.current_state is InstallerState.FLASHING)
    panel.cancel_button.click()
    _wait_for(application, lambda: panel.current_state is InstallerState.CANCELLED)
    _wait_for(application, lambda: not panel.is_running)

    assert panel.state_label.text() == "State: CANCELLED"

    window.close()
    application.processEvents()


def test_editor_page_regression_after_installer_page(application) -> None:
    window = Keyboard75Window()

    window.firmware_installer_action.trigger()
    application.processEvents()
    window.firmware_installer_action.trigger()
    application.processEvents()

    assert window.page_stack.currentWidget() is window.editor_page
    assert len(window.key_widgets) == 75
    assert window.findChild(QPushButton, "keyButton_K01") is window.key_widgets["K01"]

    window.close()
    application.processEvents()
