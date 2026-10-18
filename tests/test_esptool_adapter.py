"""Tests for port detection and esptool adapter (F3-T2)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from desktop_app.manifest import KNOWN_REFERENCE_ARTIFACTS, ChipFamily
from desktop_app.esptool_adapter import (
    EsptoolChipInfo,
    FlashBackend,
    FlashBackendError,
    FlashDeniedError,
    MockFlashBackend,
    PortInfo,
    RealFlashBackend,
    check_compatibility,
)

PORT = PortInfo("/dev/ttyUSB75")
C3 = EsptoolChipInfo(18, "ESP32C3", 4, ("USB_OTG",), 4 * 1024 * 1024, "80m", "dio")
ESP32 = EsptoolChipInfo(0, "ESP32", 0, (), 4 * 1024 * 1024, "80m", "dio")
SMALL = EsptoolChipInfo(18, "ESP32C3", 4, (), 2 * 1024 * 1024, "80m", "dio")


@pytest.fixture
def backend() -> MockFlashBackend:
    b = MockFlashBackend()
    b.add_port(PORT, C3)
    return b


@pytest.fixture
def manifest() -> "object":
    return KNOWN_REFERENCE_ARTIFACTS[1]  # kbdm-esp32c3


class TestPorts:
    def test_port_info_frozen(self) -> None:
        p = PortInfo("/dev/ttyX")
        with pytest.raises(AttributeError):
            p.device = "/other"

    def test_check_compatible_ok(self, manifest: object) -> None:
        assert check_compatibility(C3, manifest) == []

    def test_reject_wrong_chip(self, manifest: object) -> None:
        problems = check_compatibility(ESP32, manifest)
        assert any("chip" in p for p in problems)

    def test_reject_small_flash(self, manifest: object) -> None:
        problems = check_compatibility(SMALL, manifest)
        assert any("smaller" in p for p in problems)


    def test_reject_unsupported_chip(self, manifest: object) -> None:
        problems = check_compatibility(
            EsptoolChipInfo(2, "ESP32S3", 0, (), 4 * 1024 * 1024, "80m", "dio"),
            manifest,
        )
        assert any("unsupported" in pl for pl in problems)


class TestMockBackend:
    def test_chip_info(self, backend: MockFlashBackend) -> None:
        assert backend.chip_info(PORT).chip_name == "ESP32C3"

    def test_unknown_port(self, backend: MockFlashBackend) -> None:
        with pytest.raises(FlashBackendError):
            backend.chip_info(PortInfo("/dev/ttyX"))

    def test_read_empty(self, backend: MockFlashBackend) -> None:
        data = backend.read_flash(PORT, 1024)
        assert data == b"\xff" * 1024  # erased (unwritten) flash reads 0xFF

    def test_write_then_read(self, backend: MockFlashBackend) -> None:
        img = b"\x09\x30\x0d\x0d"
        backend.write_flash(PORT, [(0x0, img)])
        out = backend.read_flash(PORT, 16)
        assert out[:4] == img
        assert out[4:] == b"\xff" * 12

    def test_progress_callback(self, backend: MockFlashBackend) -> None:
        calls: list[tuple[int, int, str]] = []
        backend.write_flash(
            PORT, [(0x0, b"ab"), (0x100, b"cd")],
            progress=lambda done, total, off: calls.append((done, total, off)),
        )
        assert len(calls) == 2
        assert calls[0][:2] == (1, 2)

    def test_overrun_rejected(self, backend: MockFlashBackend) -> None:
        with pytest.raises(FlashBackendError):
            backend.write_flash(PORT, [(4 * 1024 * 1024 - 2, b"abcdef")])

    def test_erase(self, backend: MockFlashBackend) -> None:
        backend.write_flash(PORT, [(0x0, b"\x01" * 64)])
        backend.erase_flash(PORT)
        assert backend.read_flash(PORT, 64) == b"\xff" * 64


class TestRealBackendGate:
    def test_read_only_ok(self) -> None:
        b = RealFlashBackend()
        assert isinstance(b, FlashBackend)  # protocol conformance

    def test_read_flash_denied(self) -> None:
        b = RealFlashBackend()
        with pytest.raises(FlashDeniedError):
            b.read_flash(PORT, 4096)

    def test_write_flash_denied(self) -> None:
        b = RealFlashBackend()
        with pytest.raises(FlashDeniedError):
            b.write_flash(PORT, [(0, b"")])

    def test_erase_flash_denied(self) -> None:
        b = RealFlashBackend()
        with pytest.raises(FlashDeniedError):
            b.erase_flash(PORT)

    def test_authorized_still_unimplemented(self) -> None:
        b = RealFlashBackend()
        b.authorize("test-token")
        with pytest.raises(FlashBackendError):
            b.write_flash(PORT, [(0, b"")])
