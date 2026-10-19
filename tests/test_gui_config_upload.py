"""Main-window provisioning over the injected in-memory protocol transport."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from desktop_app.action import SingleKeyAction
from desktop_app.app import Keyboard75Window
from desktop_app.fw_protocol_client import (
    FirmwareProtocolError,
    InMemoryFirmwareProtocol,
)
from desktop_app.matrix_model import MatrixConfig


def _window(endpoint: InMemoryFirmwareProtocol) -> Keyboard75Window:
    config = MatrixConfig(
        rows=2,
        cols=2,
        switches={(0, 0), (0, 1), (1, 0), (1, 1)},
        row_pins=[0, 1],
        column_pins=[3, 4],
    )
    window = Keyboard75Window(
        layout=config.to_layout("Upload test"),
        firmware_transport=endpoint,
        firmware_chip_class="esp32c3",
    )
    window.matrix_config = config
    window.matrix_layout = config.to_layout("Upload test")
    window.current_project_name = "Upload test"
    return window


def test_upload_action_verifies_readback_and_reboot_persistence() -> None:
    application = QApplication.instance() or QApplication([])
    endpoint = InMemoryFirmwareProtocol(profile="esp32c3")
    window = _window(endpoint)

    assert window.upload_configuration_to_device()
    status = window.upload_status_label.text()
    assert "Upload sent" in status
    assert "Commit accepted" in status
    assert "Identical readback verified" in status
    assert "Persistence after simulated reboot verified" in status
    assert "FAILED" not in status
    assert endpoint.storage.generation == 1

    window.close()
    application.processEvents()


def test_legacy_preflight_names_key_and_never_calls_transport() -> None:
    application = QApplication.instance() or QApplication([])
    endpoint = InMemoryFirmwareProtocol(profile="esp32c3")
    window = _window(endpoint)
    window.layout.keys[0].assignment = {"type": "legacy", "raw": "custom"}

    assert not window.upload_configuration_to_device()
    assert endpoint.request_count == 0
    assert window.layout.keys[0].key_id in window.upload_status_label.text()
    assert "FAILED: preflight rejected" in window.upload_status_label.text()

    window._set_dirty(False)
    window.close()
    application.processEvents()


def test_simulator_commit_rejection_is_reported_without_activation() -> None:
    class RejectingFirmwareProtocol(InMemoryFirmwareProtocol):
        def _commit(self, override_crc):
            del override_crc
            self._clear_upload()
            raise FirmwareProtocolError("bad_crc", "simulated checksum rejection")

    application = QApplication.instance() or QApplication([])
    endpoint = RejectingFirmwareProtocol(profile="esp32c3")
    window = _window(endpoint)

    assert not window.upload_configuration_to_device()
    status = window.upload_status_label.text()
    assert "Upload sent" in status
    assert "Commit rejected: bad_crc" in status
    assert status.splitlines()[-1].startswith("FAILED: bad_crc")
    assert endpoint.active_config_bytes is None
    assert endpoint.storage.generation == 0

    window.close()
    application.processEvents()


def test_interruption_preserves_active_then_reconfigure_and_reupload_succeeds() -> None:
    application = QApplication.instance() or QApplication([])
    endpoint = InMemoryFirmwareProtocol(profile="esp32c3")
    window = _window(endpoint)
    assert window.upload_configuration_to_device()
    kept = endpoint.active_config_bytes

    window.layout.keys[0].assignment = SingleKeyAction("a").to_json()
    endpoint.fail_on_request = endpoint.request_count + 3
    assert not window.upload_configuration_to_device()
    assert "FAILED" in window.upload_status_label.text()
    assert endpoint.active_config_bytes == kept

    endpoint.fail_on_request = None
    window.current_project_name = "Reconfigured"
    assert window.upload_configuration_to_device()
    assert endpoint.storage.generation == 2
    assert endpoint.active_config_bytes != kept
    assert "Persistence after simulated reboot verified" in (
        window.upload_status_label.text()
    )

    window.close()
    application.processEvents()
