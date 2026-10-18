"""Offscreen tests for the threaded firmware installer panel."""

from __future__ import annotations

import hashlib
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop_app.esptool_adapter import (
    EsptoolChipInfo,
    FlashBackendError,
    MockFlashBackend,
    PortInfo,
)
from desktop_app.installer import InstallOutcome, InstallerState
from desktop_app.installer_panel import InstallerPanel
from desktop_app.manifest import FirmwareManifest, manifest_from_dict

PORT = PortInfo("/dev/ttyMOCK0", "Injected test port", "Test")
FLASH_SIZE = 4 * 1024 * 1024


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


def _manifest(payload: bytes = b"panel-test") -> FirmwareManifest:
    return manifest_from_dict(
        {
            "schema": "keyboard-dm/firmware-manifest/1",
            "name": "panel-test",
            "version": "1.0",
            "chip_family": "esp32c3",
            "flash_size": "4MB",
            "flash_mode": "dio",
            "flash_freq": "80m",
            "images": [
                {
                    "file_name": "panel.bin",
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


def _wait_for(application: QApplication, predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        application.processEvents()
        if time.monotonic() >= deadline:
            pytest.fail("timed out waiting for installer panel")
        time.sleep(0.005)
    application.processEvents()


def test_panel_imports_and_constructs_without_display(application) -> None:
    panel = InstallerPanel()

    assert panel.current_state is InstallerState.IDLE
    assert panel.state_label.text() == "State: IDLE"
    assert isinstance(panel._backend, MockFlashBackend)

    panel.close()


def test_discovery_renders_injected_fake_ports(application) -> None:
    ports = [PORT, PortInfo("COM42", "Second fake port")]
    panel = InstallerPanel(discover_ports=lambda: ports)

    assert panel.port_list.count() == 2
    assert panel.port_list.item(0).text() == "/dev/ttyMOCK0 — Injected test port"
    assert panel.port_list.item(1).text() == "COM42 — Second fake port"

    panel.close()


def test_happy_path_reaches_done_and_displays_backup(application, tmp_path) -> None:
    payload = b"panel-test"
    phases = []

    def factory(**kwargs):
        original_callback = kwargs["phase_callbacks"][0]

        def record_phase(state, detail):
            phases.append(state)
            original_callback(state, detail)

        kwargs["phase_callbacks"] = [record_phase]
        from desktop_app.installer import InstallerEngine

        return InstallerEngine(**kwargs)

    panel = InstallerPanel(
        backend=_backend(),
        engine_factory=factory,
        discover_ports=lambda: [PORT],
        manifests=[_manifest(payload)],
        artifact_source=lambda _name: payload,
        backup_dir=tmp_path,
    )
    panel.start_button.click()

    _wait_for(application, lambda: panel.current_state is InstallerState.DONE)
    _wait_for(application, lambda: not panel.is_running)

    backup_path = panel.backup_path_label.text()
    assert InstallerState.FLASHING in phases
    assert panel.progress_bar.value() == 100
    assert os.path.isfile(backup_path)
    assert panel.backup_digest_label.text() == hashlib.sha256(
        b"\xff" * FLASH_SIZE
    ).hexdigest()

    panel.close()


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


def test_cancel_during_run_displays_cancelled(application, tmp_path) -> None:
    panel = InstallerPanel(
        backend=_backend(),
        engine_factory=lambda **kwargs: _CancellableEngine(**kwargs),
        discover_ports=lambda: [PORT],
        manifests=[_manifest()],
        backup_dir=tmp_path,
    )
    panel.start_button.click()
    _wait_for(application, lambda: panel.current_state is InstallerState.FLASHING)

    panel.cancel_button.click()
    _wait_for(application, lambda: panel.current_state is InstallerState.CANCELLED)
    _wait_for(application, lambda: not panel.is_running)

    assert panel.state_label.text() == "State: CANCELLED"
    panel.close()


class _FailingBackend(MockFlashBackend):
    def chip_info(self, port: PortInfo) -> EsptoolChipInfo:
        raise FlashBackendError(f"backend failed on {port.device}")


def test_backend_failure_displays_error_and_recovery(application, tmp_path) -> None:
    panel = InstallerPanel(
        backend=_FailingBackend(),
        discover_ports=lambda: [PORT],
        manifests=[_manifest()],
        artifact_source=lambda _name: b"panel-test",
        backup_dir=tmp_path,
    )
    panel.start_button.click()

    _wait_for(application, lambda: panel.current_state is InstallerState.ERROR)
    _wait_for(application, lambda: not panel.is_running)

    assert "backend failed" in panel.error_label.text()
    assert "check the connection and retry" in panel.recovery_label.text()
    assert panel.recovery_label.text() != "—"
    panel.close()
