"""PySide6 panel for the backend-agnostic firmware installer."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .backup import default_backup_root, verify_backup_file
from .esptool_adapter import FlashBackend, MockFlashBackend, PortInfo
from .installer import InstallOutcome, InstallerEngine, InstallerState, SafetyGate
from .manifest import FirmwareManifest, KNOWN_REFERENCE_ARTIFACTS

__all__ = ["InstallerPanel"]


_PHASE_PERCENT = {
    InstallerState.IDLE: 0,
    InstallerState.DISCOVERING: 5,
    InstallerState.IDENTIFYING: 15,
    InstallerState.COMPAT_CHECK: 25,
    InstallerState.VERIFY_ARTIFACTS: 35,
    InstallerState.BACKING_UP: 50,
    InstallerState.FLASHING: 65,
    InstallerState.VERIFYING_FLASH: 80,
    InstallerState.RECONNECTING: 90,
    InstallerState.DONE: 100,
}

_PHASE_MESSAGE = {
    InstallerState.IDLE: "Ready to install firmware.",
    InstallerState.DISCOVERING: "Checking the selected device.",
    InstallerState.IDENTIFYING: "Identifying the device.",
    InstallerState.COMPAT_CHECK: "Checking firmware compatibility.",
    InstallerState.VERIFY_ARTIFACTS: "Verifying firmware files.",
    InstallerState.BACKING_UP: "Backing up the existing firmware.",
    InstallerState.FLASHING: "Writing firmware.",
    InstallerState.VERIFYING_FLASH: "Verifying the installed firmware.",
    InstallerState.RECONNECTING: "Waiting for the device to reconnect.",
    InstallerState.DONE: "Installation complete.",
    InstallerState.ERROR: "Installation failed.",
    InstallerState.CANCELLED: "Installation cancelled.",
}


class _InstallerWorker(QObject):
    phase_changed = Signal(object, str)
    completed = Signal(object, str)

    def __init__(
        self,
        engine: InstallerEngine,
        port: PortInfo,
        manifest: FirmwareManifest,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.port = port
        self.manifest = manifest

    @Slot()
    def run(self) -> None:
        try:
            outcome = self.engine.run(self.port, self.manifest)
            digest = ""
            if outcome.backup_path:
                digest = verify_backup_file(outcome.backup_path)
        except Exception as exc:  # keep worker failures visible in the panel
            outcome = InstallOutcome(
                InstallerState.ERROR,
                str(exc),
                "Correct the reported problem and retry the installation.",
            )
            digest = ""
        self.completed.emit(outcome, digest)


class InstallerPanel(QFrame):
    """Device discovery and firmware installation controls.

    ``discover_ports`` and ``engine_factory`` are injectable so callers and
    tests can provide deterministic discovery and installer implementations.
    The default discovery function returns no ports and the default backend is
    an in-memory :class:`MockFlashBackend`; constructing this widget therefore
    never opens a serial connection.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        backend: FlashBackend | None = None,
        engine_factory: Callable[..., InstallerEngine] | None = None,
        discover_ports: Callable[[], Sequence[PortInfo]] | None = None,
        manifests: Sequence[FirmwareManifest] | None = None,
        artifact_source: Callable[[str], bytes] | None = None,
        backup_dir: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("installerPanel")
        self._backend = backend if backend is not None else MockFlashBackend()
        self._engine_factory = engine_factory or InstallerEngine
        self._discover_ports = discover_ports or (lambda: ())
        self._manifests = tuple(manifests or KNOWN_REFERENCE_ARTIFACTS)
        self._artifact_source = artifact_source or self._missing_artifact
        self._backup_dir = str(backup_dir or default_backup_root())
        self._ports: list[PortInfo] = []
        self._engine: InstallerEngine | None = None
        self._thread: QThread | None = None
        self._worker: _InstallerWorker | None = None
        self.current_state = InstallerState.IDLE

        self._build_ui()
        self.refresh_ports()
        self._show_phase(InstallerState.IDLE, "")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        discovery_row = QHBoxLayout()
        discovery_row.addWidget(QLabel("Detected ports"))
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("installerRefreshButton")
        self.refresh_button.clicked.connect(self.refresh_ports)
        discovery_row.addStretch()
        discovery_row.addWidget(self.refresh_button)
        layout.addLayout(discovery_row)

        self.port_list = QListWidget()
        self.port_list.setObjectName("installerPortList")
        self.port_list.currentRowChanged.connect(self._update_start_enabled)
        layout.addWidget(self.port_list)

        firmware_row = QFormLayout()
        self.firmware_combo = QComboBox()
        self.firmware_combo.setObjectName("installerFirmwareCombo")
        for manifest in self._manifests:
            self.firmware_combo.addItem(
                f"{manifest.name} {manifest.version} ({manifest.chip_family})",
                manifest,
            )
        firmware_row.addRow("Firmware", self.firmware_combo)
        layout.addLayout(firmware_row)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start installation")
        self.start_button.setObjectName("installerStartButton")
        self.start_button.clicked.connect(self.start_install)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("installerCancelButton")
        self.cancel_button.clicked.connect(self.cancel_install)
        self.cancel_button.setEnabled(False)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.state_label = QLabel()
        self.state_label.setObjectName("installerStateLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("installerProgressBar")
        self.progress_bar.setRange(0, 100)
        self.message_label = QLabel()
        self.message_label.setObjectName("installerMessageLabel")
        self.message_label.setWordWrap(True)
        self.error_label = QLabel()
        self.error_label.setObjectName("installerErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.state_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.message_label)
        layout.addWidget(self.error_label)

        results = QFormLayout()
        self.backup_path_label = QLabel("—")
        self.backup_path_label.setObjectName("installerBackupPathLabel")
        self.backup_path_label.setTextInteractionFlags(
            self.backup_path_label.textInteractionFlags()
        )
        self.backup_digest_label = QLabel("—")
        self.backup_digest_label.setObjectName("installerBackupDigestLabel")
        self.recovery_label = QLabel("—")
        self.recovery_label.setObjectName("installerRecoveryLabel")
        self.recovery_label.setWordWrap(True)
        results.addRow("Backup", self.backup_path_label)
        results.addRow("SHA-256", self.backup_digest_label)
        results.addRow("Recovery", self.recovery_label)
        layout.addLayout(results)

    @staticmethod
    def _missing_artifact(file_name: str) -> bytes:
        raise FileNotFoundError(
            f"firmware artifact {file_name!r} is not available; "
            "configure an artifact source"
        )

    @Slot()
    def refresh_ports(self) -> None:
        if self.is_running:
            return
        try:
            self._ports = list(self._discover_ports())
        except Exception as exc:
            self._ports = []
            self._show_error(f"Port discovery failed: {exc}")
        self.port_list.clear()
        for port in self._ports:
            detail = f" — {port.description}" if port.description else ""
            self.port_list.addItem(f"{port.device}{detail}")
        if self._ports:
            self.port_list.setCurrentRow(0)
        self._update_start_enabled()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @Slot()
    def start_install(self) -> None:
        if self.is_running:
            return
        row = self.port_list.currentRow()
        manifest = self.firmware_combo.currentData()
        if row < 0 or row >= len(self._ports):
            self._show_error("Select a detected port before starting.")
            return
        if not isinstance(manifest, FirmwareManifest):
            self._show_error("Select a firmware package before starting.")
            return

        self.error_label.clear()
        self.error_label.hide()
        self.backup_path_label.setText("—")
        self.backup_digest_label.setText("—")
        self.recovery_label.setText("—")

        phase_callbacks = [self._queue_phase]
        try:
            engine = self._engine_factory(
                backend=self._backend,
                gate=SafetyGate(),
                artifact_source=self._artifact_source,
                backup_dir=self._backup_dir,
                phase_callbacks=phase_callbacks,
                is_mock=isinstance(self._backend, MockFlashBackend),
            )
        except Exception as exc:
            self._show_error(f"Could not prepare installer: {exc}")
            return

        thread = QThread(self)
        worker = _InstallerWorker(engine, self._ports[row], manifest)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.phase_changed.connect(self._show_phase)
        worker.completed.connect(self._apply_outcome)
        worker.completed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._thread_finished)
        self._engine = engine
        self._thread = thread
        self._worker = worker
        self._set_running(True)
        thread.start()

    def _queue_phase(self, state: InstallerState, detail: str) -> None:
        if self._worker is not None:
            self._worker.phase_changed.emit(state, detail)

    @Slot()
    def cancel_install(self) -> None:
        if self._engine is not None and self.is_running:
            self.cancel_button.setEnabled(False)
            self.message_label.setText("Cancellation requested…")
            self._engine.cancel()

    @Slot(object, str)
    def _show_phase(self, state: InstallerState, detail: str) -> None:
        self.current_state = state
        self.state_label.setText(f"State: {state.name}")
        if state in _PHASE_PERCENT:
            self.progress_bar.setValue(_PHASE_PERCENT[state])
        message = _PHASE_MESSAGE[state]
        self.message_label.setText(f"{message} {detail}".strip())

    @Slot(object, str)
    def _apply_outcome(self, outcome: InstallOutcome, digest: str) -> None:
        self._show_phase(outcome.state, outcome.message)
        if outcome.backup_path:
            self.backup_path_label.setText(outcome.backup_path)
        if digest:
            self.backup_digest_label.setText(digest)
        if outcome.recovery:
            self.recovery_label.setText(outcome.recovery)
        if outcome.state is InstallerState.ERROR:
            self._show_error(outcome.message or "Installation failed.")
        self._set_running(False)

    @Slot()
    def _thread_finished(self) -> None:
        self._engine = None
        self._worker = None
        self._thread = None
        self._update_start_enabled()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _set_running(self, running: bool) -> None:
        self.port_list.setEnabled(not running)
        self.refresh_button.setEnabled(not running)
        self.firmware_combo.setEnabled(not running)
        self.start_button.setEnabled(not running and bool(self._ports))
        self.cancel_button.setEnabled(running)

    @Slot()
    def _update_start_enabled(self) -> None:
        self.start_button.setEnabled(
            not self.is_running
            and self.port_list.currentRow() >= 0
            and self.firmware_combo.count() > 0
        )

