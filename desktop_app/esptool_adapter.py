"""Port detection and esptool backend adapters (F3-T2).

Abstraction so the installer never talks to esptool or serial ports
directly: everything goes through the :class:`FlashBackend` protocol.
A deterministic mock backend drives all tests; the real subprocess
backend exists but its mutating operations are gated, so they stay
inert until an explicit operator authorization (F4) is provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable

from .manifest import ChipFamily, FLASH_SIZES_BYTES

__all__ = [
    "PortInfo",
    "list_serial_ports",
    "EsptoolChipInfo",
    "check_compatibility",
    "FlashBackend",
    "FlashDeniedError",
    "FlashBackendError",
    "MockFlashBackend",
    "RealFlashBackend",
    "normalize_chip_family",
]


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str = ""
    manufacturer: str = ""


def list_serial_ports() -> list[PortInfo]:
    """Enumerate USB serial ports (read-only; never opens or resets)."""
    try:
        from serial.tools.list_ports import comports  # type: ignore
    except ImportError:
        return []
    out: list[PortInfo] = []
    for p in comports():
        out.append(PortInfo(p.device, p.description or "", p.manufacturer or ""))
    return out


@dataclass(frozen=True)
class EsptoolChipInfo:
    chip_id: int
    chip_name: str
    revision: int
    features: tuple[str, ...]
    flash_size_bytes: int
    flash_frequency: str
    flash_mode: str


class FlashDeniedError(RuntimeError):
    """Raised when a real (non-mock) flash/erase/backup operation is
    attempted without explicit operator authorization."""


class FlashBackendError(RuntimeError):
    """Raised when the backend fails for other reasons."""


@runtime_checkable
class FlashBackend(Protocol):
    """Abstraction over esptool + serial storage.

    Read-only operations (chip identification, flash characteristic
    query) are always allowed. Mutating operations (write, erase,
    read-back of device flash) are gated in :class:`RealFlashBackend`.
    """

    def chip_info(self, port: PortInfo) -> EsptoolChipInfo: ...
    def read_flash(self, port: PortInfo, size: int) -> bytes: ...
    def write_flash(
        self,
        port: PortInfo,
        images: list[tuple[int, bytes]],
        progress: Callable[[int, int, str], None] | None = None,
    ) -> None: ...
    def erase_flash(self, port: PortInfo) -> None: ...


#: esptool chip names / chip IDs -> manifest chip-family strings.
_CHIP_NAME_TO_FAMILY = {
    "esp32": ChipFamily.ESP32,
    "esp32s2": None,  # not supported by this project
    "esp32c2": None,
    "esp32c3": ChipFamily.ESP32_C3,
    "esp32c6": None,
}


def normalize_chip_family(chip_name: str) -> str | None:
    """Return the manifest chip-family string for an esptool chip name,
    or None when the chip is not supported."""
    return _CHIP_NAME_TO_FAMILY.get(chip_name.strip().lower())


def check_compatibility(chip: EsptoolChipInfo, manifest) -> list[str]:
    """Compare a connected chip against a manifest. Empty list = OK."""
    problems: list[str] = []
    family = normalize_chip_family(chip.chip_name)
    if family is None:
        problems.append(f"unsupported chip {chip.chip_name!r}")
        return problems
    if family != manifest.chip_family:
        problems.append(
            f"chip {chip.chip_name} does not match target {manifest.chip_family}"
        )
    required = FLASH_SIZES_BYTES[manifest.flash_size]
    if chip.flash_size_bytes < required:
        problems.append(
            f"chip flash {chip.flash_size_bytes // (1024 * 1024)}MB is smaller "
            f"than required {required // (1024 * 1024)}MB"
        )
    return problems


class MockFlashBackend:
    """Deterministic backend backed by in-memory dict storages.

    Each configured port maps to a (chip_info, bytearray) pair. Writing
    updates the storage; reading returns the current contents.
    """

    def __init__(self) -> None:
        self._ports: dict[str, tuple[EsptoolChipInfo, bytearray]] = {}

    def add_port(
        self, port: PortInfo, chip: EsptoolChipInfo, initial: bytes = b""
    ) -> None:
        self._ports[port.device] = (chip, bytearray(initial))

    def chip_info(self, port: PortInfo) -> EsptoolChipInfo:
        if port.device not in self._ports:
            raise FlashBackendError(f"no such port {port.device!r}")
        return self._ports[port.device][0]

    def read_flash(self, port: PortInfo, size: int) -> bytes:
        if port.device not in self._ports:
            raise FlashBackendError(f"no such port {port.device!r}")
        _, storage = self._ports[port.device]
        out = bytearray(b"\xff" * size)
        chunk = bytes(storage[:size])
        out[0 : len(chunk)] = chunk
        return bytes(out)  # unwritten flash reads as 0xFF (erased state)

    def write_flash(
        self,
        port: PortInfo,
        images: list[tuple[int, bytes]],
        progress: Callable[[int, int, str], None] | None = None,
    ) -> None:
        if port.device not in self._ports:
            raise FlashBackendError(f"no such port {port.device!r}")
        chip, storage = self._ports[port.device]
        offset_count = 0
        for off, data in images:
            if off + len(data) > chip.flash_size_bytes:
                raise FlashBackendError(
                    f"image at 0x{off:x} overruns flash (size {len(data)})"
                )
            while len(storage) < off + len(data):
                storage.append(0xFF)
            storage[off : off + len(data)] = data
            offset_count += 1
            if progress:
                progress(offset_count, len(images), f"0x{off:x}")

    def erase_flash(self, port: PortInfo) -> None:
        if port.device not in self._ports:
            raise FlashBackendError(f"no such port {port.device!r}")
        chip, storage = self._ports[port.device]
        if len(storage) < chip.flash_size_bytes:
            storage.extend(b"\xff" * (chip.flash_size_bytes - len(storage)))
        for i in range(chip.flash_size_bytes):
            storage[i] = 0xFF


class RealFlashBackend:
    """esptool-backed backend for physical devices.

    Read-only operations (chip_info) are permitted. Mutating operations
    (read_flash, write_flash, erase_flash) are gated: they raise
    :class:`FlashDeniedError` unless :meth:`authorize` was called with
    a token. This gate cannot be bypassed through the normal UI path.
    """

    def __init__(self, esptool_bin: str = "esptool.py") -> None:
        self._esptool = esptool_bin
        self._authorized: bool = False
        self._auth_token: str | None = None

    def authorize(self, token: str) -> None:
        self._auth_token = token
        self._authorized = True

    def _require_auth(self, op: str) -> None:
        if not self._authorized:
            raise FlashDeniedError(
                f"operation {op!r} requires explicit operator authorization"
            )

    def chip_info(self, port: PortInfo) -> EsptoolChipInfo:
        import subprocess

        proc = subprocess.run(
            [self._esptool, "--port", port.device, "--chip", "auto",
             "read_mac"],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode != 0:
            raise FlashBackendError(f"esptool read_mac failed: {proc.stderr.strip()}")
        return EsptoolChipInfo(0, "", 0, (), 0, "", "")

    def read_flash(self, port: PortInfo, size: int) -> bytes:
        self._require_auth("read_flash")
        raise FlashBackendError("not implemented in F3 (read-only gate enforced)")

    def write_flash(
        self, port: PortInfo, images: list[tuple[int, bytes]],
        progress: Callable[[int, int, str], None] | None = None
    ) -> None:
        self._require_auth("write_flash")
        raise FlashBackendError("not implemented in F3 (read-only gate enforced)")

    def erase_flash(self, port: PortInfo) -> None:
        self._require_auth("erase_flash")
        raise FlashBackendError("not implemented in F3 (read-only gate enforced)")
