"""USB serial transport tests use only injected in-memory ports."""

from __future__ import annotations

import base64
import json
import time
from types import SimpleNamespace

import pytest
import serial

from desktop_app.fw_protocol_client import (
    FirmwareProtocolClient,
    FirmwareProtocolError,
    verify_firmware_identity,
)
from desktop_app.serial_transport import (
    SerialTransportError,
    USBSerialTransport,
    discover_serial_ports,
)


class FakeFirmwareSerial:
    def __init__(self, board: str | None = "esp32") -> None:
        self.is_open = True
        self.timeout = 1.0
        self.board = board
        self.reply = bytearray()
        self.commands: list[str] = []

    def write(self, line: bytes) -> int:
        request = json.loads(line)
        command = request["cmd"]
        self.commands.append(command)
        if command == "version":
            result = {"protocol": "0.1", "active_protocol": 1}
            if self.board is not None:
                result["board"] = self.board
            response = {"id": request["id"], "ok": True, "result": result}
        else:
            response = {"id": request["id"], "ok": True, "result": {}}
        self.reply.extend(json.dumps(response).encode() + b"\n")
        return len(line)

    def flush(self) -> None:
        pass

    def read(self, size: int) -> bytes:
        if not self.reply:
            return b""
        chunk = bytes(self.reply[:size])
        del self.reply[:size]
        return chunk

    def close(self) -> None:
        self.is_open = False

    def open(self) -> None:
        self.is_open = True


def test_request_round_trip_is_lf_framed() -> None:
    port = FakeFirmwareSerial()
    transport = USBSerialTransport(port)
    result = FirmwareProtocolClient(transport).version()
    assert result == {"protocol": "0.1", "active_protocol": 1, "board": "esp32"}
    assert not port.reply


def test_factory_is_deferred_until_explicit_connect() -> None:
    calls = []

    def factory(**settings):
        calls.append(settings)
        return FakeFirmwareSerial()

    transport = USBSerialTransport("/fake/keyboard", serial_factory=factory)
    assert not transport.is_connected
    assert calls == []
    transport.connect()
    assert calls[0]["port"] == "/fake/keyboard"
    assert calls[0]["baudrate"] == 115200
    assert transport.is_connected
    transport.disconnect()
    transport.disconnect()
    assert not transport.is_connected


def test_context_manager_closes_after_successful_request() -> None:
    port = FakeFirmwareSerial()
    with USBSerialTransport(port) as transport:
        assert FirmwareProtocolClient(transport).version()["board"] == "esp32"
    assert not port.is_open


@pytest.mark.parametrize("bad_reply", [b"not-json\n", b'{"id":"wrong","ok":true,"result":{}}\n'])
def test_malformed_or_wrong_id_is_invalid_response(bad_reply) -> None:
    class BadReply(FakeFirmwareSerial):
        def write(self, line):
            self.reply.extend(bad_reply)
            return len(line)

    with pytest.raises(FirmwareProtocolError) as caught:
        FirmwareProtocolClient(USBSerialTransport(BadReply())).version()
    assert caught.value.code == "invalid_response"


def test_timeout_is_bounded() -> None:
    class Silent(FakeFirmwareSerial):
        def write(self, line):
            return len(line)

        def read(self, size):
            time.sleep(min(self.timeout, 0.005))
            return b""

    started = time.monotonic()
    port = Silent()
    with pytest.raises(SerialTransportError, match="timed out"):
        USBSerialTransport(port, timeout=0.03).request(b"{}\n")
    assert time.monotonic() - started < 1
    assert not port.is_open


@pytest.mark.parametrize("operation", ["write", "read"])
def test_serial_exception_is_wrapped(operation) -> None:
    class Broken(FakeFirmwareSerial):
        def write(self, line):
            if operation == "write":
                raise serial.SerialException("gone")
            self.reply.extend(b"x")
            return len(line)

        def read(self, size):
            if operation == "read":
                raise serial.SerialException("gone")
            return super().read(size)

    port = Broken()
    with pytest.raises(SerialTransportError, match="serial I/O failed"):
        USBSerialTransport(port).request(b"{}\n", timeout=0.03)
    assert not port.is_open


@pytest.mark.parametrize(("reported", "selected"), [("esp32c3", "esp32"), ("esp32", "esp32c3")])
def test_blank_device_identity_mismatch_prevents_upload(reported, selected) -> None:
    kind = "usb_uart" if selected == "esp32" else "c3_native_usart"
    client = FirmwareProtocolClient(
        USBSerialTransport(FakeFirmwareSerial(reported), transport_kind=kind)
    )
    uploaded = False
    with pytest.raises(FirmwareProtocolError) as caught:
        verify_firmware_identity(client, selected)
        uploaded = True
    assert caught.value.code == "board_mismatch"
    assert uploaded is False


def test_matching_identity_proceeds_to_upload_command() -> None:
    port = FakeFirmwareSerial("esp32c3")
    client = FirmwareProtocolClient(
        USBSerialTransport(port, transport_kind="c3_native_usart")
    )
    verify_firmware_identity(client, "esp32c3")
    client.command("config_upload", {})
    assert port.commands == ["version", "config_upload"]


@pytest.mark.parametrize(
    ("board", "kind"), [("esp32", "usb_uart"), ("esp32c3", "c3_native_usart")]
)
def test_blank_device_matching_identity_is_accepted(board, kind) -> None:
    verify_firmware_identity(FirmwareProtocolClient(
        USBSerialTransport(FakeFirmwareSerial(board), transport_kind=kind)), board)


@pytest.mark.parametrize(
    ("board", "selected", "kind"),
    [
        (None, "esp32", "usb_uart"),
        (None, "esp32c3", "c3_native_usart"),
        ("mystery-chip", "esp32", "usb_uart"),
        ("mystery-chip", "esp32c3", "c3_native_usart"),
    ],
)
def test_blank_device_unknown_or_legacy_identity_is_rejected(board, selected, kind) -> None:
    client = FirmwareProtocolClient(
        USBSerialTransport(FakeFirmwareSerial(board), transport_kind=kind)
    )
    with pytest.raises(FirmwareProtocolError) as caught:
        verify_firmware_identity(client, selected)
    assert caught.value.code in {"identity_unverifiable", "unknown_board"}


@pytest.mark.parametrize(
    ("selected", "kind"), [("esp32c3", "usb_uart"), ("esp32", "c3_native_usart")]
)
def test_transport_capability_mismatch_is_rejected_before_upload(selected, kind) -> None:
    port = FakeFirmwareSerial(selected)
    client = FirmwareProtocolClient(USBSerialTransport(port, transport_kind=kind))
    with pytest.raises(FirmwareProtocolError) as caught:
        verify_firmware_identity(client, selected)
    assert caught.value.code == "board_mismatch"
    assert "config_upload" not in port.commands


def test_realistic_multichunk_upload_has_complete_untruncated_replies() -> None:
    class UploadSerial(FakeFirmwareSerial):
        def __init__(self) -> None:
            super().__init__("esp32")
            self.upload = bytearray()
            self.expected_size = 0
            self.lines: list[bytes] = []

        def write(self, line: bytes) -> int:
            self.lines.append(line)
            request = json.loads(line)
            command, params = request["cmd"], request["params"]
            self.commands.append(command)
            if command == "config_upload" and params["phase"] == "start":
                self.expected_size = params["total_bytes"]
                result = {"accepted": True, "next_seq": 0}
            elif command == "config_upload":
                self.upload.extend(base64.b64decode(params["data"], validate=True))
                result = {"accepted": True, "next_seq": params["seq"] + 1}
            elif command == "config_commit":
                assert len(self.upload) == self.expected_size
                result = {"generation": 1, "status": "validated"}
            else:
                raise AssertionError(command)
            response = {"id": request["id"], "ok": True, "result": result}
            # The transport reads until LF, so a long JSON result cannot be
            # accepted merely because an early read returned some bytes.
            self.reply.extend(json.dumps(response).encode() + b"\n")
            return len(line)

    raw = (b'{"payload":"' + (b"keyboard-dm-" * 500) + b'"}')
    port = UploadSerial()
    client = FirmwareProtocolClient(USBSerialTransport(port))
    result = client.upload_config(raw)
    assert result == {"generation": 1, "status": "validated"}
    assert bytes(port.upload) == raw
    assert port.commands.count("config_upload") > 2
    assert all(line.endswith(b"\n") and len(line) - 1 <= 1536 for line in port.lines)


def test_discovery_uses_provider_without_opening_serial(monkeypatch) -> None:
    monkeypatch.setattr(serial, "Serial", lambda *args, **kwargs: pytest.fail("opened"))
    ports = discover_serial_ports(
        lambda: [SimpleNamespace(device="/fake/one", description="Keyboard DM")]
    )
    assert ports == [{"port": "/fake/one", "description": "Keyboard DM"}]
