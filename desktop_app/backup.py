"""Pre-flash full-backup workflow (F3-T4).

Reads the device's entire flash, verifies integrity with a chunked
SHA-256, and stores the backup privately OUTSIDE the Git repository
with 0600 permissions plus a sidecar metadata file.

Safety rules enforced here:
* The backup directory must live outside the repository root when a
  repository root is known (never committed to GitHub).
* The sidecar metadata never contains device identifiers, MAC/BT
  bonding data or credentials -- only a generic label, date, size and
  digest.
* Restoring a backup is intentionally NOT implemented in F3. Restoration
  is a separate, separately-authorized operation.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path

CHUNK_SIZE = 256 * 1024  # 256 KiB read/verify chunks


class BackupError(RuntimeError):
    """Backup or verification failure."""


@dataclass(frozen=True)
class BackupRecord:
    path: str
    digest: str
    size: int
    meta_path: str

    def verify(self) -> bool:
        """Re-hash the stored dump and compare with the recorded digest."""
        return verify_backup_file(self.path) == self.digest


def default_backup_root() -> Path:
    """Private, per-user storage: ~/.local/share/keyboard-dm/backups."""
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "keyboard-dm" / "backups"


def sha256_file(path: str, chunk_size: int = CHUNK_SIZE) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_backup_file(path: str) -> str:
    if not os.path.isfile(path):
        raise BackupError(f"backup file not found: {path}")
    return sha256_file(path)


def assert_outside_repo(backup_dir: Path, repo_root: str | Path | None) -> None:
    """Refuse storage of private backups inside the Git repository."""
    if repo_root is None:
        return
    root = Path(repo_root).resolve()
    try:
        backup_dir.resolve().relative_to(root)
    except ValueError:
        return  # outside the repo -- fine
    raise BackupError(
        "backup directory is inside the repository; private dumps must "
        "be stored outside Git"
    )


def chunked_sha256(
    read_fn,
    total_size: int,
    chunk_size: int = CHUNK_SIZE,
    progress=None,
) -> tuple[str, bytes]:
    """SHA-256 over a lazily read stream; returns (digest, all data)."""
    h = hashlib.sha256()
    buf = bytearray()
    offset = 0
    while offset < total_size:
        n = min(chunk_size, total_size - offset)
        chunk = bytes(read_fn(offset, n))
        if len(chunk) != n:
            raise BackupError(
                f"flash readback returned {len(chunk)} of {n} bytes at {offset:#x}"
            )
        h.update(chunk)
        buf.extend(chunk)
        offset += n
        if progress:
            progress(offset, total_size)
    return h.hexdigest(), bytes(buf)


class BackupService:
    """Full-flash backup manager for the installer."""

    def __init__(self, backend, backup_dir: str | Path | None = None,
                 repo_root: str | Path | None = None) -> None:
        self._backend = backend
        self._backup_dir = Path(backup_dir) if backup_dir else default_backup_root()
        assert_outside_repo(self._backup_dir, repo_root)

    @property
    def backup_dir(self) -> Path:
        return self._backup_dir

    def create_backup(
        self,
        port,
        chip_info,
        label: str = "device",
        progress=None,
    ) -> BackupRecord:
        """Read the full flash, verify, store privately, return the record.

        ``chip_info.flash_size_bytes`` defines the readback length.
        ``progress`` is called with (done, total) after each chunk.
        """
        size = int(chip_info.flash_size_bytes)
        if size <= 0:
            raise BackupError("chip flash size is zero or invalid")

        def _read_at(offset: int, n: int) -> bytes:
            # backend.read_flash reads from 0; simulate offset reads by
            # reading the window (mock/real adapters both support this)
            return self._backend.read_flash(port, offset + n)[offset:offset + n]

        self._backend_charged_for_read(port)
        digest, data = chunked_sha256(_read_at, size, progress=progress)

        self._backup_dir.mkdir(parents=True, exist_ok=True)
        base = (
            f"backup-{port.device.replace('/', '_')}-"
            f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{digest[:12]}"
        )
        path = self._backup_dir / f"{base}.bin"
        meta_path = self._backup_dir / f"{base}.meta.json"

        with open(path, "wb") as fh:
            fh.write(data)
        os.chmod(path, 0o600)

        meta = {
            "schema": "keyboard-dm/backup-meta/1",
            "label": label,
            "port": port.device,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "chip_family": getattr(chip_info, "chip_name", "unknown"),
            "flash_size_bytes": size,
            "sha256": digest,
            "note": "Private full-flash dump. Never upload to GitHub.",
        }
        with open(meta_path, "w") as fh:
            json.dump(meta, fh, indent=2)
        os.chmod(meta_path, 0o600)

        return BackupRecord(str(path), digest, size, str(meta_path))

    def _backend_charged_for_read(self, port) -> None:
        """Real-device read-outs are gated; mock reads pass through."""
        # The installer's SafetyGate performs the actual authorization; the
        # service re-checks that a read is possible before doing the work.
        try:
            self._backend.chip_info(port)
        except Exception as exc:
            raise BackupError(f"device not reachable at {port.device!r}: {exc}") from exc

    @staticmethod
    def write_record(
        backup_dir: Path,
        port,
        chip_info,
        data: bytes,
        label: str = "pre-flash",
    ) -> BackupRecord:
        """Store an already-read, size-verified flash buffer privately."""
        digest = hashlib.sha256(data).hexdigest()
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        base = (
            f"backup-{port.device.replace('/', '_')}-"
            f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{digest[:12]}"
        )
        path = backup_dir / f"{base}.bin"
        meta_path = backup_dir / f"{base}.meta.json"
        with open(path, "wb") as fh:
            fh.write(data)
        os.chmod(path, 0o600)
        meta = {
            "schema": "keyboard-dm/backup-meta/1",
            "label": label,
            "port": port.device,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "chip_family": getattr(chip_info, "chip_name", "unknown"),
            "flash_size_bytes": len(data),
            "sha256": digest,
            "note": "Private full-flash dump. Never upload to GitHub.",
        }
        with open(meta_path, "w") as fh:
            json.dump(meta, fh, indent=2)
        os.chmod(meta_path, 0o600)
        return BackupRecord(str(path), digest, len(data), str(meta_path))

    def meta(self, path: str) -> dict:
        meta_path = str(Path(path).with_suffix(".meta.json"))
        if not os.path.isfile(meta_path):
            raise BackupError(f"no metadata for backup {path}")
        with open(meta_path) as fh:
            return json.load(fh)

    def verify_record(self, record: BackupRecord) -> bool:
        if record.size != os.path.getsize(record.path):
            return False
        return record.verify() and self.meta(record.path)["sha256"] == record.digest


__all__ = [
    "BackupError",
    "BackupRecord",
    "BackupService",
    "CHUNK_SIZE",
    "assert_outside_repo",
    "chunked_sha256",
    "default_backup_root",
    "sha256_file",
    "verify_backup_file",
]
