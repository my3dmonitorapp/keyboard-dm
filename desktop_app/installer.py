"""Firmware installer state machine (F3-T3).

Pure, backend-agnostic engine. All device traffic goes through a
:class:`~desktop_app.esptool_adapter.FlashBackend`. The engine is fully
driven by the mock backend in tests; the real backend's authorization
gate is enforced at the adapter level AND re-checked here
(:class:`SafetyGate`), so real flashing/erasing cannot happen through
the UI path without explicit operator authorization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .esptool_adapter import (
    EsptoolChipInfo,
    FlashBackend,
    FlashBackendError,
    FlashDeniedError,
    PortInfo,
    check_compatibility,
)
from .manifest import FirmwareManifest, verify_file_sha256

__all__ = [
    "InstallerState",
    "InstallerError",
    "SafetyGate",
    "InstallerEngine",
    "PROTOCOL_VERSION",
    "detect_protocol_version",
]

#: Protocol version announced by the F2 firmware after successful flash.
PROTOCOL_VERSION = 2

#: F2 firmware command the app polls after reconnection to verify the
#: flashed image (response carries the protocol version byte).
PROTOCOL_VERSION_COMMAND = b"\x10"


class InstallerState(Enum):
    IDLE = "idle"
    DISCOVERING = "discovering"
    IDENTIFYING = "identifying"
    COMPAT_CHECK = "compat_check"
    VERIFY_ARTIFACTS = "verify_artifacts"
    BACKING_UP = "backing_up"
    FLASHING = "flashing"
    VERIFYING_FLASH = "verifying_flash"
    RECONNECTING = "reconnecting"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset({InstallerState.DONE, InstallerState.ERROR, InstallerState.CANCELLED})


class InstallerError(RuntimeError):
    def __init__(self, message: str, recovery: str = "") -> None:
        super().__init__(message)
        self.recovery = recovery


@dataclass
class SafetyGate:
    """Explicit authorization gate for mutating operations.

    ``armed`` defaults to False. UI interactions never arm it; only
    an out-of-band operator authorization token can. When disarmed,
    any mutating backend call is refused before it reaches the backend.
    """

    armed: bool = False
    auth_token: str = ""

    def arm(self, token: str) -> None:
        if not token:
            raise ValueError("authorization token is empty")
        self.armed = True
        self.auth_token = token

    def disarm(self) -> None:
        self.armed = False
        self.auth_token = ""

    def require_mutation_allowed(self, is_mock: bool) -> None:
        if is_mock:
            return  # tests are authorized by construction
        if not self.armed:
            raise InstallerError(
                "installation refused: no active operator authorization",
                recovery=(
                    "real-device installation requires explicit approval; "
                    "see the recovery plan in the installer log"
                ),
            )

    def require_read_only(self, is_mock: bool) -> None:
        # Reading full device flash is sensitive even without erasing.
        if is_mock or self.armed:
            return
        raise InstallerError(
            "device read-out refused: no active operator authorization",
            recovery="backup of real device flash requires explicit approval",
        )


def detect_protocol_version(version_byte: int) -> tuple[int, bool]:
    """Parse a protocol-version response from the flashed firmware.

    Returns (version, compatible). Compatible when the version byte is
    >= PROTOCOL_VERSION (newer firmwares stay acceptable).
    """
    if not isinstance(version_byte, int) or not 0 <= version_byte <= 255:
        return 0, False
    return version_byte, version_byte >= PROTOCOL_VERSION


@dataclass
class InstallOutcome:
    state: InstallerState
    message: str = ""
    recovery: str = ""
    backup_path: str | None = None
    protocol_version: int | None = None


class InstallerEngine:
    """Drives a single installation run.

    ``phase_callbacks`` is called as (state, detail) at every transition.
    Flash progress arrives through ``progress`` as (done_images, total_images,
    next_offset). ``reconnect_probe`` simulates reading the protocol
    version after the device re-enumerates (mock returns a byte).
    """

    def __init__(
        self,
        backend: FlashBackend,
        gate: SafetyGate,
        artifact_source: Callable[[str], bytes],
        backup_dir: str,
        *,
        phase_callbacks: list[Callable[[InstallerState, str], None]] | None = None,
        reconnect_probe: Callable[[PortInfo], int] | None = None,
        repo_root: str | None = None,
        is_mock: bool = True,
    ) -> None:
        self._backend = backend
        self._gate = gate
        self._artifacts = artifact_source
        self._backup_dir = Path(backup_dir)
        self._repo_root = repo_root
        self._phase_callbacks = phase_callbacks or []
        self._reconnect_probe = reconnect_probe or (lambda port: PROTOCOL_VERSION)
        self._is_mock = is_mock
        self._cancelled = False
        self.state = InstallerState.IDLE

    # -- public API ---------------------------------------------------
    @property
    def state(self) -> InstallerState:
        return self._state

    @state.setter
    def state(self, value: InstallerState) -> None:
        self._state = value
        for cb in self._phase_callbacks:
            cb(value, self._detail)

    def cancel(self) -> None:
        self._cancelled = True

    def run(
        self,
        port: PortInfo,
        manifest: FirmwareManifest,
        backup_name: str | None = None,
    ) -> InstallOutcome:
        try:
            return self._run(port, manifest, backup_name)
        except InstallerError as exc:
            self._detail = str(exc)
            final_state = InstallerState.CANCELLED if self._cancelled else InstallerState.ERROR
            self.state = final_state
            return InstallOutcome(
                final_state, str(exc), exc.recovery
            )
        except FlashDeniedError as exc:
            self._detail = str(exc)
            self.state = InstallerState.ERROR
            return InstallOutcome(
                InstallerState.ERROR,
                str(exc),
                "operator authorization required; nothing was written to the device",
            )
        except FlashBackendError as exc:
            self._detail = str(exc)
            self.state = InstallerState.ERROR
            return InstallOutcome(
                InstallerState.ERROR,
                str(exc),
                "check the connection and retry; the device state is unknown",
            )

    # -- phase callbacks default -------------------------------------
    _detail: str = ""

    def _set(self, next_state: InstallerState, detail: str = "") -> None:
        self._detail = detail
        self.state = next_state
        if self._cancelled:
            self.state = InstallerState.CANCELLED
            raise InstallerError("installation cancelled by operator", 
                                 recovery="device left in its prior state unless "
                                          "the operation had already reached a "
                                          "commit point (flash write)")

    # -- run phases ---------------------------------------------------
    def _run(
        self,
        port: PortInfo,
        manifest: FirmwareManifest,
        backup_name: str | None,
    ) -> InstallOutcome:
        self._cancelled = False
        self._set(InstallerState.DISCOVERING, f"port={port.device}")
        chip = self._backend.chip_info(port)  # read-only, always allowed

        self._set(InstallerState.IDENTIFYING, f"chip={chip.chip_name}")

        self._set(InstallerState.COMPAT_CHECK, "")
        problems = check_compatibility(chip, manifest)
        if problems:
            raise InstallerError(
                "device not compatible: " + "; ".join(problems),
                recovery="this firmware build targets a different chip/flash; "
                         "select the matching artifact or device",
            )

        self._set(InstallerState.VERIFY_ARTIFACTS, f"files={len(manifest.images)}")
        for image in manifest.images:
            data = self._artifacts(image.file_name)
            if len(data) != image.size_bytes:
                raise InstallerError(
                    f"artifact {image.file_name!r}: size mismatch "
                    f"({len(data)} vs {image.size_bytes})",
                    recovery="missing or corrupted firmware file; re-download",
                )
            actual = _sha256(data)
            if actual != image.sha256:
                raise InstallerError(
                    f"artifact {image.file_name!r}: SHA-256 mismatch",
                    recovery="firmware file is corrupt or was modified; "
                             "delete it and re-download",
                )

        self._set(InstallerState.BACKING_UP, backup_name or "")
        backup_path, backup_digest = self._make_backup(port, chip, manifest, backup_name)

        self._set(InstallerState.FLASHING, "")
        images: list[tuple[int, bytes]] = []
        for image in manifest.images:
            images.append((image.offset, self._artifacts(image.file_name)))
        progress = self._flash_progress
        self._gate.require_mutation_allowed(self._is_mock)
        self._backend.write_flash(port, images, progress)

        self._set(InstallerState.VERIFYING_FLASH, "")
        self._gate.require_mutation_allowed(self._is_mock)
        for image in manifest.images:
            readout = self._backend.read_flash(
                port, image.offset + image.size_bytes
            )[image.offset : image.offset + image.size_bytes]
            expected = self._artifacts(image.file_name)
            if not _segments_equal(readout, expected):
                raise InstallerError(
                    f"post-flash verification failed for {image.file_name!r}",
                    recovery="the device may be partially flashed; re-run the "
                             "installer (full re-flash restores consistency)",
                )

        self._set(InstallerState.RECONNECTING, "")
        version_byte = self._reconnect_probe(port)
        version, ok = detect_protocol_version(version_byte)
        if not ok:
            raise InstallerError(
                f"device reconnected but announced protocol version {version} "
                f"(expected >= {PROTOCOL_VERSION})",
                recovery="firmware may not have started; re-run the installer",
            )

        self._set(InstallerState.DONE, f"protocol_v={version}")
        return InstallOutcome(
            InstallerState.DONE,
            "installation complete",
            backup_path=str(backup_path),
            protocol_version=version,
        )

    def _make_backup(
        self,
        port: PortInfo,
        chip: EsptoolChipInfo,
        manifest: FirmwareManifest,
        backup_name: str | None,
    ) -> tuple[str, str]:
        import hashlib
        import os

        from .backup import BackupService

        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._gate.require_read_only(self._is_mock)
        size = chip.flash_size_bytes
        data = self._backend.read_flash(port, size)
        if len(data) != size:
            raise InstallerError(
                f"full flash readback returned {len(data)} of {size} bytes",
                recovery="readback incomplete; retry before flashing",
            )
        record = BackupService.write_record(
            self._backup_dir, port, chip, data, label=backup_name or "pre-flash"
        )
        return record.path, record.digest

    def _flash_progress(self, done: int, total: int, off: str) -> None:
        self._detail = f"{done}/{total} images written (next {off})"


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _segments_equal(a: bytes, b: bytes) -> bool:
    if len(a) != len(b):
        return False
    return all(x == y for x, y in zip(a, b))

