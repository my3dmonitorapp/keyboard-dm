"""Headless client and deterministic in-memory firmware protocol endpoint."""

from __future__ import annotations

import base64
import binascii
import json
import zlib
from dataclasses import dataclass
from itertools import count
from typing import Any, Protocol

from .action import Action
from .esp32_gpio import PinRole, get_gpio_profile, validate_gpio_pin
from .serialization import stable_json_bytes, verify_firmware_config_crc

PROTOCOL_VERSION = "0.1"
MAX_LINE_BYTES = 1536
MAX_RAW_CHUNK_BYTES = 1024
MAX_UPLOAD_BYTES = 8192


class FirmwareProtocolError(RuntimeError):
    """A structured firmware rejection or invalid response."""

    def __init__(self, code: str, message: str = "command rejected") -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class FirmwareTransport(Protocol):
    def request(self, line: bytes, timeout: float | None = None) -> bytes: ...


class FirmwareProtocolClient:
    """Synchronous JSON-over-LF client with bounded base64 upload chunks."""

    def __init__(
        self,
        transport: FirmwareTransport,
        *,
        timeout: float = 1.0,
        chunk_size: int = MAX_RAW_CHUNK_BYTES,
    ) -> None:
        if type(chunk_size) is not int or not 1 <= chunk_size <= MAX_RAW_CHUNK_BYTES:
            raise ValueError("chunk_size must be from 1 to 1024 raw bytes")
        self.transport = transport
        self.timeout = timeout
        self.chunk_size = chunk_size
        self._ids = count(1)

    def command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = str(next(self._ids))
        payload = {
            "version": PROTOCOL_VERSION,
            "id": request_id,
            "cmd": command,
            "params": params,
        }
        line = stable_json_bytes(payload) + b"\n"
        if len(line) - 1 > MAX_LINE_BYTES:
            raise FirmwareProtocolError("invalid_command", "request is overlong")
        raw = self.transport.request(line, timeout=self.timeout)
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as error:
            raise FirmwareProtocolError("invalid_response", str(error)) from error
        if not isinstance(response, dict) or response.get("id") != request_id:
            raise FirmwareProtocolError("invalid_response", "response ID mismatch")
        if response.get("ok") is not True:
            detail = response.get("error", {})
            raise FirmwareProtocolError(
                str(detail.get("code", "unknown_error")),
                str(detail.get("message", "command rejected")),
            )
        result = response.get("result")
        if not isinstance(result, dict):
            raise FirmwareProtocolError("invalid_response", "result must be an object")
        return result

    def version(self) -> dict[str, Any]:
        return self.command("version", {})

    def status(self) -> dict[str, Any]:
        return self.command("config_status", {})

    config_status = status

    def get_config(self) -> dict[str, Any]:
        result = self.command("config_get", {"source": "active"})
        config = result.get("config")
        if not isinstance(config, dict):
            raise FirmwareProtocolError("invalid_response", "config is missing")
        return config

    config_get = get_config

    def upload_config(
        self,
        config: bytes | bytearray | memoryview | dict[str, Any],
        *,
        upload_id: str = "desktop",
    ) -> dict[str, Any]:
        raw = stable_json_bytes(config) if isinstance(config, dict) else bytes(config)
        if not 1 <= len(raw) <= MAX_UPLOAD_BYTES:
            raise ValueError("firmware config must be from 1 to 8192 bytes")
        if not upload_id or len(upload_id.encode("utf-8")) > 32:
            raise ValueError("upload_id must be from 1 to 32 UTF-8 bytes")
        checksum = zlib.crc32(raw) & 0xFFFFFFFF
        self.command(
            "config_upload",
            {
                "phase": "start",
                "upload_id": upload_id,
                "encoding": "base64",
                "total_bytes": len(raw),
                "crc32": checksum,
            },
        )
        for sequence, offset in enumerate(range(0, len(raw), self.chunk_size)):
            chunk = raw[offset : offset + self.chunk_size]
            self.command(
                "config_upload",
                {
                    "phase": "chunk",
                    "upload_id": upload_id,
                    "seq": sequence,
                    "data": base64.b64encode(chunk).decode("ascii"),
                },
            )
        return self.command("config_commit", {})

    config_upload = upload_config

    def reboot(self) -> dict[str, Any]:
        """Reboot an injectable transport, then return persisted status."""
        reboot = getattr(self.transport, "reboot", None)
        if reboot is None:
            raise FirmwareProtocolError("unsupported", "transport cannot reboot")
        reboot()
        return self.status()


def verify_firmware_identity(
    client: FirmwareProtocolClient, selected_chip_class: str
) -> None:
    """Verify protocol, compiled board identity, and transport capability."""
    known_boards = {"esp32", "esp32c3"}
    if selected_chip_class not in known_boards:
        raise FirmwareProtocolError(
            "unknown_board", f"selected target {selected_chip_class!r} is unsupported"
        )
    transport_kind = getattr(client.transport, "transport_kind", None)
    transport_boards = {
        "usb_uart": "esp32",
        "c3_native_usart": "esp32c3",
    }
    capable_board = transport_boards.get(transport_kind)
    if transport_kind is not None and capable_board is None:
        raise FirmwareProtocolError(
            "unknown_transport", f"transport capability {transport_kind!r} is unsupported"
        )
    if capable_board is not None and capable_board != selected_chip_class:
        raise FirmwareProtocolError(
            "board_mismatch",
            f"{transport_kind} is for {capable_board}, selected target is {selected_chip_class}",
        )
    version = client.version()
    if version.get("protocol") != PROTOCOL_VERSION or version.get("active_protocol") != 1:
        raise FirmwareProtocolError(
            "unsupported_protocol", "firmware protocol 0.1 (active protocol 1) is required"
        )
    board = version.get("board")
    if not isinstance(board, str) or not board:
        raise FirmwareProtocolError(
            "identity_unverifiable", "firmware version response has no board identity"
        )
    if board not in known_boards:
        raise FirmwareProtocolError(
            "unknown_board", f"firmware reported unsupported board {board!r}"
        )
    if board != selected_chip_class:
        raise FirmwareProtocolError(
            "board_mismatch",
            f"firmware is {board}, selected target is {selected_chip_class}",
        )
    if capable_board is not None and board != capable_board:
        raise FirmwareProtocolError(
            "board_mismatch", f"firmware {board} is incompatible with {transport_kind}"
        )


@dataclass
class InMemoryFirmwareStorage:
    """Persistent state retained when a simulated endpoint is rebooted."""

    active_config: bytes | None = None
    generation: int = 0


class InMemoryFirmwareProtocol:
    """Strict protocol simulator for provisioning tests; it performs no GPIO I/O."""

    def __init__(
        self,
        *,
        profile: str = "esp32c3",
        storage: InMemoryFirmwareStorage | None = None,
    ) -> None:
        self.profile = profile
        self.storage = storage or InMemoryFirmwareStorage()
        self.request_count = 0
        self.fail_on_request: int | None = None
        self._clear_upload()

    def _clear_upload(self) -> None:
        self._upload_id: str | None = None
        self._upload_total = 0
        self._upload_crc = 0
        self._upload_next_seq = 0
        self._upload = bytearray()

    @property
    def active_config_bytes(self) -> bytes | None:
        return self.storage.active_config

    def reboot(self) -> None:
        self._clear_upload()

    restart = reboot

    def request(self, line: bytes, timeout: float | None = None) -> bytes:
        del timeout
        self.request_count += 1
        if self.fail_on_request == self.request_count:
            raise TimeoutError("simulated firmware transport timeout")
        return self.exchange(line)

    def exchange(self, line: bytes) -> bytes:
        if not isinstance(line, (bytes, bytearray, memoryview)):
            raise TypeError("protocol input must be bytes")
        raw = bytes(line)
        framed = raw[:-1] if raw.endswith(b"\n") else raw
        if framed.endswith(b"\r"):
            framed = framed[:-1]
        if not framed or len(framed) > MAX_LINE_BYTES:
            return self._error("", "invalid_command")
        try:
            request = json.loads(framed.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._error("", "invalid_command")
        if not isinstance(request, dict):
            return self._error("", "bad_version_or_envelope")
        request_id = request.get("id")
        if not isinstance(request_id, str):
            return self._error("", "bad_version_or_envelope")
        if set(request) - {"version", "id", "cmd", "params", "crc32"}:
            return self._error(request_id, "bad_version_or_envelope")
        if request.get("version", PROTOCOL_VERSION) not in {PROTOCOL_VERSION, 1}:
            return self._error(request_id, "bad_version_or_envelope")
        command = request.get("cmd")
        params = request.get("params")
        if not isinstance(command, str) or not isinstance(params, dict):
            return self._error(request_id, "bad_version_or_envelope")
        try:
            result = self._apply(command, params)
        except FirmwareProtocolError as error:
            return self._error(request_id, error.code, error.message)
        return stable_json_bytes({"id": request_id, "ok": True, "result": result})

    process_line = exchange

    @staticmethod
    def _error(request_id: str, code: str, message: str = "command rejected") -> bytes:
        return stable_json_bytes(
            {
                "id": request_id,
                "ok": False,
                "error": {"code": code, "message": message, "details": {}},
            }
        )

    def _apply(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        if command == "version" and not params:
            return {
                "protocol": PROTOCOL_VERSION,
                "active_protocol": 1,
                "board": self.profile,
            }
        if command in {"config_status", "boot_status"} and not params:
            return {
                "state": 2 if self.storage.active_config is not None else 0,
                "active_generation": self.storage.generation,
            }
        if command == "config_get":
            if set(params) - {"source"} or params.get("source", "active") != "active":
                raise FirmwareProtocolError("not_found")
            if self.storage.active_config is None:
                raise FirmwareProtocolError("not_found")
            return {"config": json.loads(self.storage.active_config.decode("utf-8"))}
        if command == "config_upload":
            return self._upload_command(params)
        if command == "config_commit":
            if set(params) - {"crc32", "upload_id"}:
                raise FirmwareProtocolError("bad_params")
            return self._commit(params.get("crc32"))
        raise FirmwareProtocolError("unknown_command")

    def _upload_command(self, params: dict[str, Any]) -> dict[str, Any]:
        phase = params.get("phase")
        if phase == "start":
            required = {"phase", "upload_id", "encoding", "total_bytes", "crc32"}
            if set(params) != required or params.get("encoding") != "base64":
                raise FirmwareProtocolError("bad_params")
            upload_id = params.get("upload_id")
            total = params.get("total_bytes")
            checksum = params.get("crc32")
            if (
                not isinstance(upload_id, str)
                or not upload_id
                or len(upload_id.encode()) > 32
                or type(total) is not int
                or not 1 <= total <= MAX_UPLOAD_BYTES
                or type(checksum) is not int
                or not 0 <= checksum <= 0xFFFFFFFF
            ):
                raise FirmwareProtocolError("bad_params")
            self._clear_upload()
            self._upload_id = upload_id
            self._upload_total = total
            self._upload_crc = checksum
            return {"accepted": True, "next_seq": 0}
        if phase == "chunk":
            if set(params) != {"phase", "upload_id", "seq", "data"}:
                raise FirmwareProtocolError("bad_params")
            if (
                self._upload_id is None
                or params.get("upload_id") != self._upload_id
                or params.get("seq") != self._upload_next_seq
                or not isinstance(params.get("data"), str)
            ):
                raise FirmwareProtocolError("bad_state")
            try:
                chunk = base64.b64decode(params["data"], validate=True)
            except (binascii.Error, ValueError) as error:
                raise FirmwareProtocolError("bad_state") from error
            if len(chunk) > MAX_RAW_CHUNK_BYTES or len(self._upload) + len(chunk) > self._upload_total:
                raise FirmwareProtocolError("bad_state")
            self._upload.extend(chunk)
            self._upload_next_seq += 1
            return {"accepted": True, "next_seq": self._upload_next_seq}
        if phase == "abort":
            self._clear_upload()
            return {"accepted": True}
        if phase == "commit":
            if set(params) != {"phase", "upload_id"} or params.get("upload_id") != self._upload_id:
                raise FirmwareProtocolError("bad_state")
            return self._commit(None)
        raise FirmwareProtocolError("bad_params")

    def _commit(self, override_crc: Any) -> dict[str, Any]:
        if self._upload_id is None:
            raise FirmwareProtocolError("bad_state")
        raw = bytes(self._upload)
        expected = self._upload_crc if override_crc is None else override_crc
        if type(expected) is not int or len(raw) != self._upload_total or (zlib.crc32(raw) & 0xFFFFFFFF) != expected:
            self._clear_upload()
            raise FirmwareProtocolError("bad_crc")
        try:
            config = json.loads(raw.decode("utf-8"))
            self._validate_config(config)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            self._clear_upload()
            raise FirmwareProtocolError("bad_config", str(error)) from error
        generation = self.storage.generation + 1
        config["generation"] = generation
        config.pop("crc32", None)
        config["crc32"] = zlib.crc32(stable_json_bytes(config)) & 0xFFFFFFFF
        self.storage.active_config = stable_json_bytes(config)
        self.storage.generation = generation
        self._clear_upload()
        return {"generation": generation, "status": "validated"}

    def _validate_config(self, config: Any) -> None:
        if not isinstance(config, dict) or not verify_firmware_config_crc(config):
            raise ValueError("embedded config CRC mismatch")
        required = {
            "protocol_version", "config_schema_version", "chip_class", "matrix",
            "actions", "meta", "extensions", "generation", "crc32",
        }
        if set(config) != required or config["protocol_version"] != 1 or config["config_schema_version"] != 1:
            raise ValueError("unsupported config envelope")
        matrix = config["matrix"]
        actions = config["actions"]
        if not isinstance(matrix, dict) or not isinstance(actions, dict):
            raise ValueError("matrix and actions must be objects")
        rows, cols = matrix.get("rows"), matrix.get("cols")
        row_pins, col_pins = matrix.get("row_pins"), matrix.get("col_pins")
        populated = matrix.get("populated")
        if type(rows) is not int or type(cols) is not int or not 1 <= rows <= 16 or not 1 <= cols <= 16:
            raise ValueError("invalid matrix dimensions")
        if not isinstance(row_pins, list) or len(row_pins) != rows or not isinstance(col_pins, list) or len(col_pins) != cols:
            raise ValueError("pin counts do not match matrix")
        scan = matrix.get("scan_mode")
        if scan == "drive_rows_low_read_cols_pullup":
            row_role, col_role = PinRole.OUTPUT, PinRole.INPUT
            expected_diode = "col_to_row"
        elif scan == "drive_cols_low_read_rows_pullup":
            row_role, col_role = PinRole.INPUT, PinRole.OUTPUT
            expected_diode = "row_to_col"
        else:
            raise ValueError("invalid scan mode")
        pins = row_pins + col_pins
        if len(set(pins)) != len(pins):
            raise ValueError("duplicate GPIO pin")
        for pin, role in [*((pin, row_role) for pin in row_pins), *((pin, col_role) for pin in col_pins)]:
            result = validate_gpio_pin(pin, role, profile=self.profile)
            if not result.valid:
                raise ValueError(result.error)
            if (
                role is PinRole.INPUT
                and matrix.get("pull_up_source") == "internal"
                and pin in get_gpio_profile(self.profile).input_only_pins
            ):
                raise ValueError(f"GPIO {pin} requires an external pull-up")
        diode = matrix.get("diode_direction")
        if isinstance(diode, str) and diode != expected_diode:
            raise ValueError("scan/diode mismatch")
        if not isinstance(populated, list) or len(populated) > 256:
            raise ValueError("invalid populated switches")
        seen: set[str] = set()
        for switch in populated:
            if not isinstance(switch, dict) or set(switch) != {"row", "col", "key_id"}:
                raise ValueError("invalid switch")
            row, col, key_id = switch["row"], switch["col"], switch["key_id"]
            if type(row) is not int or type(col) is not int or not (0 <= row < rows and 0 <= col < cols):
                raise ValueError("switch outside matrix")
            if key_id != f"MX-{row:02d}-{col:02d}" or key_id in seen:
                raise ValueError("invalid or duplicate switch ID")
            seen.add(key_id)
        if set(actions) != seen:
            raise ValueError("actions do not match populated switches")
        for action in actions.values():
            if action is not None:
                restored = Action.from_json(action)
                if restored.action_type == "legacy":
                    raise ValueError("legacy actions cannot be activated")


# Natural aliases used by tests and non-GUI integrations.
ProtocolClient = FirmwareProtocolClient
SimulatedFirmwareProtocol = InMemoryFirmwareProtocol
