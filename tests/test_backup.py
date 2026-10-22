"""Tests for the pre-flash backup workflow (F3-T4)."""

from __future__ import annotations

import json
import os
import stat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from desktop_app.backup import (
    BackupError,
    BackupService,
    chunked_sha256,
    sha256_file,
)
from desktop_app.esptool_adapter import (
    EsptoolChipInfo,
    MockFlashBackend,
    PortInfo,
)

PORT = PortInfo("/dev/ttyMOCK1")
FLASH_SIZE = 4 * 1024 * 1024
C3_CHIP = EsptoolChipInfo(5, "ESP32C3", 4, (4,), FLASH_SIZE, "80m", "dio")


def make_backend(with_data: bool = False) -> MockFlashBackend:
    backend = MockFlashBackend()
    initial = b""
    if with_data:
        initial = bytes((i % 256) for i in range(FLASH_SIZE))
    backend.add_port(PORT, C3_CHIP, initial)
    return backend


class TestBackupService:
    def test_create_backup_4mb(self, tmp_path) -> None:
        backend = make_backend()
        svc = BackupService(backend, tmp_path / "backups")
        record = svc.create_backup(PORT, C3_CHIP)
        assert record.size == FLASH_SIZE
        assert os.path.isfile(record.path)
        import hashlib as _h

        expected = _h.sha256(b"\xff" * FLASH_SIZE).hexdigest()
        assert record.digest == expected
        # private permissions
        mode = stat.S_IMODE(os.stat(record.path).st_mode)
        assert mode == 0o600
        assert os.path.isfile(record.meta_path)
        assert svc.verify_record(record)

    def test_backup_matches_existing_flash(self, tmp_path) -> None:
        backend = make_backend(with_data=True)
        svc = BackupService(backend, tmp_path / "backups")
        record = svc.create_backup(PORT, C3_CHIP)
        with open(record.path, "rb") as fh:
            data = fh.read()
        assert len(data) == FLASH_SIZE
        assert bytes((i % 256) for i in range(FLASH_SIZE)) == data

    def test_meta_contents(self, tmp_path) -> None:
        backend = make_backend()
        svc = BackupService(backend, tmp_path / "backups")
        record = svc.create_backup(PORT, C3_CHIP, label="9key-board")
        meta = svc.meta(record.path)
        assert meta["schema"] == "keyboard-dm/backup-meta/1"
        assert meta["label"] == "9key-board"
        assert meta["port"] == PORT.device
        assert meta["flash_size_bytes"] == FLASH_SIZE
        assert meta["sha256"] == record.digest
        # no private device identifiers
        assert "mac" not in json.dumps(meta).lower()

    def test_refuse_storage_inside_repo(self, tmp_path) -> None:
        with pytest.raises(BackupError):
            BackupService(
                make_backend(),
                tmp_path / "in-repo-backups",
                repo_root=tmp_path,
            )

    def test_outside_repo_allowed(self, tmp_path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "private"
        BackupService(make_backend(), outside, repo_root=repo)  # no raise

    def test_tampered_backup_fails_verification(self, tmp_path) -> None:
        backend = make_backend()
        svc = BackupService(backend, tmp_path / "backups")
        record = svc.create_backup(PORT, C3_CHIP)
        with open(record.path, "r+b") as fh:
            fh.seek(16)
            fh.write(b"\x00")
        assert not svc.verify_record(record)

    def test_missing_file_raises(self, tmp_path) -> None:
        from desktop_app.backup import verify_backup_file

        with pytest.raises(BackupError):
            verify_backup_file(str(tmp_path / "nope.bin"))


class TestChunkedSha256:
    def test_known_vector(self) -> None:
        data = bytes(range(256)) * 8  # 2048 bytes
        def read_at(offset, n):
            return data[offset:offset + n]

        digest, buf = chunked_sha256(read_at, len(data))
        import hashlib

        assert digest == hashlib.sha256(data).hexdigest()
        assert buf == data

    def test_short_read_raises(self) -> None:
        def short_read(offset, n):
            return b"\x00" * (n - 1)

        with pytest.raises(BackupError):
            chunked_sha256(short_read, 4096)

    def test_progress_called_per_chunk(self) -> None:
        data = b"\xAA" * 600
        calls: list[tuple[int, int]] = []
        def read_at(offset, n):
            return data[offset:offset + n]

        def call(done: int, total: int) -> None:
            calls.append((done, total))

        chunked_sha256(read_at, len(data), chunk_size=256, progress=call)
        assert calls[-1] == (600, 600)
        assert calls[0][0] == 256


class TestEngineIntegration:
    def test_engine_backup_uses_verified_service(self, tmp_path) -> None:
        # The engine's happy path (T3) flows readback -> write_record;
        # here we assert the produced backup verifies against itself.
        from desktop_app.installer import InstallerEngine, SafetyGate
        from desktop_app.manifest import KNOWN_REFERENCE_ARTIFACTS
        import hashlib as _h

        backend = make_backend()
        manifest = [m for m in KNOWN_REFERENCE_ARTIFACTS if m.name == "kbdm-esp32c3"][0]
        payloads = {
            img.file_name: bytes([(k + b) % 256 for b in range(img.size_bytes)])
            for k, img in enumerate(manifest.images)
        }
        # rebuild manifest to match tampered-free payload hashes
        from desktop_app.manifest import manifest_from_dict, FirmwareImage

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
                    "file_name": i.file_name,
                    "offset": i.offset,
                    "sha256": _h.sha256(payloads[i.file_name]).hexdigest(),
                    "size_bytes": i.size_bytes,
                }
                for i in manifest.images
            ],
        }
        eff = manifest_from_dict(doc)
        engine = InstallerEngine(
            backend, SafetyGate(), lambda f: payloads[f], str(tmp_path / "bk")
        )
        outcome = engine.run(PORT, eff)
        assert outcome.state.value == "done"
        assert outcome.backup_path is not None
        with open(outcome.backup_path, "rb") as fh:
            assert fh.read(16) == b"\xff" * 16
        meta = svc_meta(outcome.backup_path)
        assert meta["sha256"] == _h.sha256(b"\xff" * FLASH_SIZE).hexdigest()


def svc_meta(backup_path: str) -> dict:
    from desktop_app.backup import BackupService

    meta_path = backup_path.rsplit(".", 1)[0] + ".meta.json"
    with open(meta_path) as fh:
        return json.load(fh)
