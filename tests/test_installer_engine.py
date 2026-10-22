"""Tests for the installer state machine and safety gate (F3-T3)."""

from __future__ import annotations

import hashlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from desktop_app.esptool_adapter import (
    EsptoolChipInfo,
    FlashDeniedError,
    MockFlashBackend,
    PortInfo,
    RealFlashBackend,
)
from desktop_app.installer import (
    PROTOCOL_VERSION,
    InstallerEngine,
    InstallerState,
    SafetyGate,
    detect_protocol_version,
)
from desktop_app.manifest import (
    KNOWN_REFERENCE_ARTIFACTS,
    FirmwareManifest,
    manifest_from_dict,
)

C3 = "kbdm-esp32c3"
PORT = PortInfo("/dev/ttyMOCK0")
FLASH_SIZE = 4 * 1024 * 1024

C3_CHIP = EsptoolChipInfo(5, "ESP32C3", 4, (4,), FLASH_SIZE, "80m", "dio")
def make_backend(chip= C3_CHIP) -> "MockFlashBackend":
    b = MockFlashBackend()
    b.add_port(PORT, chip, b"\xff" * FLASH_SIZE)
    return b


ESP32_CHIP = EsptoolChipInfo(0, "ESP32", 0, (0,), FLASH_SIZE, "80m", "dio")


def sha256hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_manifest(name: str) -> FirmwareManifest:
    for manifest in KNOWN_REFERENCE_ARTIFACTS:
        if manifest.name == name:
            return manifest
    raise KeyError(name)


def payloads_for(manifest: FirmwareManifest, seed: int = 7) -> dict[str, bytes]:
    return {
        img.file_name: bytes([(seed + k + b) % 256 for b in range(img.size_bytes)])
        for k, img in enumerate(manifest.images)
    }


def manifest_with_payloads(
    manifest: FirmwareManifest, payloads: dict[str, bytes]
) -> FirmwareManifest:
    """Validate and rebuild a manifest whose hashes match the given payloads."""
    doc = {
        "schema": manifest.schema,
        "name": manifest.name,
        "version": manifest.version,
        "chip_family": manifest.chip_family,
        "flash_size": manifest.flash_size,
        "flash_mode": manifest.flash_mode,
        "flash_freq": manifest.flash_freq,
        "images": [
            {
                "file_name": img.file_name,
                "offset": img.offset,
                "sha256": sha256hex(payloads[img.file_name]),
                "size_bytes": img.size_bytes,
            }
            for img in manifest.images
        ],
    }
    return manifest_from_dict(doc)


@pytest.fixture
def c3_env(tmp_path):
    """Mock C3 env: backend, engine, manifest matching the payload bytes."""
    backend = make_backend()
    m = make_manifest(C3)
    payloads = payloads_for(m)
    effective = manifest_with_payloads(m, payloads)
    engine = InstallerEngine(
        backend, SafetyGate(), lambda f: payloads[f], str(tmp_path), is_mock=True
    )
    return backend, engine, effective


class TestHappyPath:
    def test_full_run_reaches_done(self, c3_env) -> None:
        _, engine, manifest = c3_env
        seen: list[InstallerState] = []
        engine._phase_callbacks.append(lambda s, d: seen.append(s))
        outcome = engine.run(PORT, manifest)
        assert outcome.state == InstallerState.DONE
        assert outcome.protocol_version == PROTOCOL_VERSION
        for expected in (
            InstallerState.DISCOVERING,
            InstallerState.IDENTIFYING,
            InstallerState.COMPAT_CHECK,
            InstallerState.VERIFY_ARTIFACTS,
            InstallerState.BACKING_UP,
            InstallerState.FLASHING,
            InstallerState.VERIFYING_FLASH,
            InstallerState.RECONNECTING,
            InstallerState.DONE,
        ):
            assert expected in seen
        assert outcome.backup_path is not None
        assert os.path.isfile(outcome.backup_path)

    def test_flash_writes_all_segments(self, c3_env) -> None:
        backend, engine, manifest = c3_env
        engine.run(PORT, manifest)
        for img in manifest.images:
            stored = backend.read_flash(PORT, img.offset + img.size_bytes)[
                img.offset : img.offset + img.size_bytes
            ]
            assert len(stored) == img.size_bytes
            assert stored != b"\xff" * img.size_bytes

    def test_backup_of_pristine_flash_is_all_ff(self, c3_env) -> None:
        _, engine, manifest = c3_env
        outcome = engine.run(PORT, manifest)
        with open(outcome.backup_path, "rb") as fh:
            data = fh.read()
        assert len(data) == FLASH_SIZE
        assert data == b"\xff" * len(data)
        assert sha256hex(data) == hashlib.sha256(b"\xff" * FLASH_SIZE).hexdigest()


class TestFailures:
    def test_incompatible_chip_stops_before_writes(self, tmp_path) -> None:
        backend = make_backend()
        m = make_manifest(C3)
        backend.add_port(PORT, ESP32_CHIP, b"\xff" * FLASH_SIZE)
        engine = InstallerEngine(
            backend, SafetyGate(), lambda f: bytes(4), str(tmp_path)
        )
        outcome = engine.run(PORT, m)
        assert outcome.state == InstallerState.ERROR
        assert "not compatible" in outcome.message
        assert outcome.recovery
        assert backend.read_flash(PORT, 4096) == b"\xff" * 4096

    def test_size_mismatch_rejected(self, tmp_path) -> None:
        backend = make_backend()
        m = make_manifest(C3)
        payloads = payloads_for(m)
        effective = manifest_with_payloads(m, payloads)
        # deliver wrong-sized artifact
        engine = InstallerEngine(
            backend, SafetyGate(), lambda f: bytes(16), str(tmp_path)
        )
        outcome = engine.run(PORT, effective)
        assert outcome.state == InstallerState.ERROR
        assert "size mismatch" in outcome.message
        assert backend.read_flash(PORT, 4096) == b"\xff" * 4096

    def test_corrupt_artifact_hash_rejected(self, tmp_path) -> None:
        backend = make_backend()
        m = make_manifest(C3)
        payloads = payloads_for(m)
        # tampered bytes -> payload hash no longer matches manifest hash
        tampered = {
            name: (b"\x00" + data[1:]) if data else data
            for name, data in payloads.items()
        }
        engine = InstallerEngine(
            backend, SafetyGate(), lambda f: tampered[f], str(tmp_path)
        )
        outcome = engine.run(PORT, manifest_with_payloads(m, payloads))
        assert outcome.state == InstallerState.ERROR
        assert "SHA-256" in outcome.message
        assert backend.read_flash(PORT, 4096) == b"\xff" * 4096

    def test_unknown_port_rejected(self, tmp_path) -> None:
        backend = MockFlashBackend()
        m = make_manifest(C3)
        engine = InstallerEngine(
            backend, SafetyGate(), lambda f: bytes(4), str(tmp_path)
        )
        outcome = engine.run(PORT, m)
        assert outcome.state == InstallerState.ERROR
        assert outcome.recovery


class TestSafetyGate:
    def test_real_backend_mutation_denied(self) -> None:
        b = RealFlashBackend()
        with pytest.raises(FlashDeniedError):
            b.write_flash(PORT, [(0x10000, b"x")], lambda *a: None)
        with pytest.raises(FlashDeniedError):
            b.erase_flash(PORT)
        with pytest.raises(FlashDeniedError):
            b.read_flash(PORT, 4096)

    def test_real_backend_engine_run_denied_at_backup(self, tmp_path) -> None:
        b = RealFlashBackend()
        b.chip_info = lambda _port: C3_CHIP  # type: ignore[method-assign]
        m = make_manifest(C3)
        payloads = payloads_for(m)
        engine = InstallerEngine(
            b,
            SafetyGate(),
            lambda f: payloads[f],
            str(tmp_path),
            is_mock=False,
        )
        outcome = engine.run(PORT, manifest_with_payloads(m, payloads))
        assert outcome.state == InstallerState.ERROR
        assert "authorization" in outcome.message

    def test_gate_arm_requires_token(self) -> None:
        gate = SafetyGate()
        with pytest.raises(ValueError):
            gate.arm("")
        gate.arm("op-tok-1")
        assert gate.armed
        gate.disarm()
        assert not gate.armed

    def test_protocol_version_compatibility(self) -> None:
        assert detect_protocol_version(2) == (2, True)
        assert detect_protocol_version(3) == (3, True)
        assert detect_protocol_version(1) == (1, False)
        assert detect_protocol_version(0) == (0, False)
        assert detect_protocol_version(256) == (0, False)

    def test_bad_protocol_version_after_flash(self, c3_env) -> None:
        _, engine, manifest = c3_env
        engine._reconnect_probe = lambda port: 1
        outcome = engine.run(PORT, manifest)
        assert outcome.state == InstallerState.ERROR
        assert "protocol" in outcome.message


class TestCancellation:
    def _run_cancelled(self, tmp_path, at_state: InstallerState) -> InstallerEngine:
        backend = make_backend()
        m = make_manifest(C3)
        payloads = payloads_for(m)
        effective = manifest_with_payloads(m, payloads)
        engine = InstallerEngine(
            backend, SafetyGate(), lambda f: payloads[f], str(tmp_path)
        )
        engine._phase_callbacks.append(
            lambda s, d: engine.cancel() if s == at_state else None
        )
        engine.run(PORT, effective)
        assert engine.state == InstallerState.CANCELLED
        return engine

    def test_cancel_before_flash(self, tmp_path) -> None:
        backend = make_backend()
        self._run_cancelled(tmp_path, InstallerState.BACKING_UP)
        # nothing written before the flash phase
        data = backend.read_flash(PORT, 0x10000 + 8)
        assert data[0x10000 : 0x10000 + 8] == b"\xff" * 8
        assert data[0:8] == b"\xff" * 8

    def test_cancel_during_flash(self, tmp_path) -> None:
        self._run_cancelled(tmp_path, InstallerState.FLASHING)
