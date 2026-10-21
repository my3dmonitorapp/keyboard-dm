"""Optional, lazily imported PySerial transport for Keyboard DM firmware."""

from __future__ import annotations

import time
from typing import Callable


class SerialTransportError(RuntimeError):
    """A serial connection, I/O, or framing failure."""


def _serial_module():
    try:
        import serial
    except (ImportError, ModuleNotFoundError) as error:
        raise SerialTransportError("pyserial is required for USB serial connections") from error
    return serial


def discover_serial_ports(
    port_provider: Callable | None = None,
) -> list[dict[str, str]]:
    """Return available serial ports without opening any of them."""
    if port_provider is None:
        try:
            from serial.tools import list_ports
        except (ImportError, ModuleNotFoundError) as error:
            raise SerialTransportError("pyserial is required for USB serial discovery") from error
        port_provider = list_ports.comports
    return [
        {
            "port": str(getattr(item, "device", item)),
            "description": str(getattr(item, "description", "")),
        }
        for item in port_provider()
    ]


class USBSerialTransport:
    """Synchronous JSON-over-LF transport backed by an injectable serial port."""

    _KINDS = frozenset({"usb_uart", "c3_native_usart"})

    def __init__(
        self,
        port: str | object,
        *,
        baud_rate: int = 115200,
        transport_kind: str = "usb_uart",
        timeout: float = 1.0,
        serial_factory: Callable | None = None,
    ) -> None:
        if transport_kind not in self._KINDS:
            raise ValueError("transport_kind must be 'usb_uart' or 'c3_native_usart'")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.port = port
        self.baud_rate = baud_rate
        self.transport_kind = transport_kind
        self.timeout = timeout
        self._serial_factory = serial_factory
        self._serial = port if not isinstance(port, str) else None

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and bool(getattr(self._serial, "is_open", True))

    def connect(self) -> None:
        if self.is_connected:
            return
        if self._serial is None:
            serial = _serial_module() if self._serial_factory is None else None
            factory = self._serial_factory or serial.Serial
            try:
                self._serial = factory(
                    port=self.port,
                    baudrate=self.baud_rate,
                    bytesize=8 if serial is None else serial.EIGHTBITS,
                    parity="N" if serial is None else serial.PARITY_NONE,
                    stopbits=1 if serial is None else serial.STOPBITS_ONE,
                    timeout=self.timeout,
                    write_timeout=self.timeout,
                )
            except Exception as error:
                self._serial = None
                raise SerialTransportError(f"could not open serial port: {error}") from error
        elif hasattr(self._serial, "open"):
            try:
                self._serial.open()
            except Exception as error:
                raise SerialTransportError(f"could not open serial port: {error}") from error

    def disconnect(self) -> None:
        serial_port = self._serial
        if serial_port is not None and hasattr(serial_port, "close"):
            try:
                serial_port.close()
            except Exception as error:
                raise SerialTransportError(f"could not close serial port: {error}") from error

    close = disconnect

    def request(self, line: bytes, timeout: float | None = None) -> bytes:
        if not self.is_connected:
            raise SerialTransportError("serial port is disconnected")
        wait = self.timeout if timeout is None else timeout
        if wait <= 0:
            raise SerialTransportError("serial response timed out")
        deadline = time.monotonic() + wait
        response = bytearray()
        try:
            written = self._serial.write(line)
            if written != len(line):
                raise SerialTransportError("serial write was incomplete")
            self._serial.flush()
            while time.monotonic() < deadline:
                if not bool(getattr(self._serial, "is_open", True)):
                    raise SerialTransportError("serial port disconnected during request")
                remaining = max(0.0, deadline - time.monotonic())
                if hasattr(self._serial, "timeout"):
                    self._serial.timeout = remaining
                chunk = self._serial.read(1)
                if not chunk:
                    continue
                response.extend(chunk)
                if chunk == b"\n":
                    return bytes(response)
        except SerialTransportError:
            raise
        except Exception as error:
            raise SerialTransportError(f"serial I/O failed: {error}") from error
        raise SerialTransportError("serial response timed out")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.disconnect()
