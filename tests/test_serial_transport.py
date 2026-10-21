"""USB serial transport tests use only injected in-memory ports."""

from __future__ import annotations

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
    def __init__(self, chip_class: str | None = None) -> None:
        self.is_open = True
        self.timeout = 1.0
        self.chip_class = chip_class
        self.reply = bytearray()
        self.commands: list[str] = []

    def write(self, line: bytes) -> int:
        request = json.loads(line)
        command = request["cmd"]
        self.commands.append(command)
        if command == "version":
            result = {"protocol": "0.1", "active_protocol": 1}
            response = {"id": request["id"], "ok": True, "result": result}
        elif command == "config_get" and self.chip_class is None:
            response = {
                "id": request["id"], "ok": False,
                "error": {"code": "not_found", "message": "no active config"},
            }
        elif command == "config_get":
            response = {
                "id": request["id"], "ok": True,
                "result": {"config": {"chip_class": self.chip_class}},
            }
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
    assert result == {"protocol": "0.1", "active_protocol": 1}
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
    with pytest.raises(SerialTransportError, match="timed out"):
        USBSerialTransport(Silent(), timeout=0.03).request(b"{}\n")
    assert time.monotonic() - started < 1


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

    with pytest.raises(SerialTransportError, match="serial I/O failed"):
        USBSerialTransport(Broken()).request(b"{}\n", timeout=0.03)


@pytest.mark.parametrize(
    ("active", "selected"), [("esp32c3", "esp32"), ("esp32", "esp32c3")]
)
def test_identity_mismatch_prevents_upload(active, selected) -> None:
    client = FirmwareProtocolClient(USBSerialTransport(FakeFirmwareSerial(active)))
    uploaded = False
    with pytest.raises(FirmwareProtocolError) as caught:
        verify_firmware_identity(client, selected)
        uploaded = True
    assert caught.value.code == "board_mismatch"
    assert uploaded is False


def test_matching_identity_proceeds_to_upload_command() -> None:
    port = FakeFirmwareSerial("esp32c3")
    client = FirmwareProtocolClient(USBSerialTransport(port))
    verify_firmware_identity(client, "esp32c3")
    client.command("config_upload", {})
    assert port.commands == ["version", "config_get", "config_upload"]


def test_no_active_config_uses_protocol_identity_only() -> None:
    verify_firmware_identity(
        FirmwareProtocolClient(USBSerialTransport(FakeFirmwareSerial())), "esp32"
    )


def test_discovery_uses_provider_without_opening_serial(monkeypatch) -> None:
    monkeypatch.setattr(serial, "Serial", lambda *args, **kwargs: pytest.fail("opened"))
    ports = discover_serial_ports(
        lambda: [SimpleNamespace(device="/fake/one", description="Keyboard DM")]
    )
    assert ports == [{"port": "/fake/one", "description": "Keyboard DM"}]
