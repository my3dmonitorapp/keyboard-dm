"""Desktop-to-firmware bridge and in-memory provisioning coverage."""

from __future__ import annotations

import json
import zlib
from pathlib import Path

import pytest

from desktop_app.action import MediaAction, ModifierAction, ShortcutAction, SingleKeyAction
from desktop_app.fw_protocol_client import (
    FirmwareProtocolClient,
    FirmwareProtocolError,
    InMemoryFirmwareProtocol,
    MAX_LINE_BYTES,
)
from desktop_app.matrix_model import MatrixConfig
from desktop_app.project import create_project
from desktop_app.serialization import (
    SerializationError,
    action_to_firmware,
    firmware_config_json,
    project_to_firmware_config,
    stable_json_bytes,
    verify_firmware_config_crc,
)


def matrix_project(rows: int = 3, cols: int = 2, *, name: str = "Pad") -> dict:
    switches = {(row, col) for row in range(rows) for col in range(cols)}
    config = MatrixConfig(
        rows=rows,
        cols=cols,
        switches=switches,
        row_pins=[0, 1, 3][:rows],
        column_pins=[4, 5, 6][:cols],
    )
    assignments = {key_id: None for key_id in config.keys()}
    assignments[config.keys()[0]] = SingleKeyAction("a")
    document = create_project(name, config.to_layout(name), assignments, matrix_config=config)
    document["created"] = "2026-10-19T00:00:00+00:00"
    document["updated"] = "2026-10-19T00:00:00+00:00"
    return document


def with_embedded_crc(config: dict) -> bytes:
    config.pop("crc32", None)
    config["crc32"] = zlib.crc32(stable_json_bytes(config)) & 0xFFFFFFFF
    return stable_json_bytes(config)


def test_blank_3x2_provision_readback_and_reboot_persistence() -> None:
    endpoint = InMemoryFirmwareProtocol(profile="esp32c3")
    client = FirmwareProtocolClient(endpoint)
    raw = firmware_config_json(matrix_project(), chip_class="esp32c3")

    assert client.status() == {"state": 0, "active_generation": 0}
    assert client.upload_config(raw) == {"generation": 1, "status": "validated"}
    assert client.get_config()["matrix"]["rows"] == 3
    assert client.reboot() == {"state": 2, "active_generation": 1}
    assert client.get_config()["meta"]["project_name"] == "Pad"


def test_reconfiguration_replaces_active_and_survives_reboot() -> None:
    endpoint = InMemoryFirmwareProtocol(profile="esp32c3")
    client = FirmwareProtocolClient(endpoint)
    client.upload_config(firmware_config_json(matrix_project(name="First"), chip_class="esp32c3"))
    client.upload_config(firmware_config_json(matrix_project(name="Second"), chip_class="esp32c3"))

    assert client.reboot()["active_generation"] == 2
    assert client.get_config()["meta"]["project_name"] == "Second"


def test_invalid_pin_and_switch_are_rejected_without_mutation() -> None:
    endpoint = InMemoryFirmwareProtocol(profile="esp32c3")
    client = FirmwareProtocolClient(endpoint)
    good = firmware_config_json(matrix_project(name="Good"), chip_class="esp32c3")
    client.upload_config(good)

    bad_pin = json.loads(good)
    bad_pin["matrix"]["row_pins"][0] = 18
    with pytest.raises(FirmwareProtocolError, match="bad_config"):
        client.upload_config(with_embedded_crc(bad_pin))

    bad_switch = json.loads(good)
    bad_switch["matrix"]["populated"][0]["row"] = 9
    with pytest.raises(FirmwareProtocolError, match="bad_config"):
        client.upload_config(with_embedded_crc(bad_switch))
    assert client.get_config()["meta"]["project_name"] == "Good"


def test_bridge_rejects_pin_outside_selected_capability_profile() -> None:
    document = matrix_project()
    document["matrix"]["row_pins"][0] = 18
    with pytest.raises(SerializationError, match="not available"):
        project_to_firmware_config(document, chip_class="esp32c3")


def test_overlong_and_bad_upload_crc_are_rejected() -> None:
    endpoint = InMemoryFirmwareProtocol(profile="esp32c3")
    response = json.loads(endpoint.exchange(b"x" * (MAX_LINE_BYTES + 1)))
    assert response["error"]["code"] == "invalid_command"

    client = FirmwareProtocolClient(endpoint)
    raw = firmware_config_json(matrix_project(), chip_class="esp32c3")
    client.command("config_upload", {
        "phase": "start", "upload_id": "bad", "encoding": "base64",
        "total_bytes": len(raw), "crc32": 0,
    })
    import base64
    client.command("config_upload", {
        "phase": "chunk", "upload_id": "bad", "seq": 0,
        "data": base64.b64encode(raw).decode("ascii"),
    })
    with pytest.raises(FirmwareProtocolError, match="bad_crc"):
        client.command("config_commit", {})
    assert client.status()["state"] == 0


def test_interrupted_upload_timeout_leaves_active_config_unchanged() -> None:
    endpoint = InMemoryFirmwareProtocol(profile="esp32c3")
    client = FirmwareProtocolClient(endpoint, chunk_size=128)
    client.upload_config(firmware_config_json(matrix_project(name="Kept"), chip_class="esp32c3"))
    endpoint.fail_on_request = endpoint.request_count + 2

    with pytest.raises(TimeoutError):
        client.upload_config(firmware_config_json(matrix_project(name="Lost"), chip_class="esp32c3"))
    endpoint.reboot()
    assert client.get_config()["meta"]["project_name"] == "Kept"
    assert client.status()["active_generation"] == 1


def test_unknown_and_legacy_actions_serialize_as_firmware_legacy() -> None:
    document = matrix_project()
    document["keys"]["MX-00-00"]["assignment"] = {
        "type": "legacy", "raw": "launch-custom"
    }
    config = project_to_firmware_config(document, chip_class="esp32c3")
    assert config["actions"]["MX-00-00"] == {
        "type": "legacy", "raw": "launch-custom"
    }

    assert action_to_firmware("unknown command") == {
        "type": "legacy", "raw": "unknown command"
    }
    assert action_to_firmware(ModifierAction("ralt", "up")) == {
        "type": "modifier", "modifier": "ralt", "event": "up"
    }


def test_exact_golden_3x3_json_is_stable_and_crc_valid() -> None:
    config = MatrixConfig(
        rows=3,
        cols=3,
        switches={(row, col) for row in range(3) for col in range(3)},
        row_pins=[0, 1, 3],
        column_pins=[4, 5, 6],
    )
    assignments = {key_id: None for key_id in config.keys()}
    assignments["MX-00-00"] = SingleKeyAction("escape")
    assignments["MX-01-01"] = ShortcutAction(("lctrl", "lshift"), "s")
    assignments["MX-02-02"] = MediaAction("play_pause")
    document = create_project("Golden 3x3", config.to_layout(), assignments, matrix_config=config)
    document["created"] = document["updated"] = "2026-10-19T00:00:00+00:00"

    raw = firmware_config_json(document, chip_class="esp32c3", generation=7)
    golden = (
        Path(__file__).parents[1]
        / "firmware/host/tests/protocol/valid/golden_3x3.json"
    ).read_bytes().rstrip(b"\n")
    restored = json.loads(raw)
    assert raw == golden
    assert raw == stable_json_bytes(restored)
    assert verify_firmware_config_crc(restored)
    assert restored["matrix"]["populated"][4] == {
        "row": 1, "col": 1, "key_id": "MX-01-01"
    }
    assert restored["actions"]["MX-01-01"] == {
        "type": "shortcut", "modifiers": ["lctrl", "lshift"], "key": "s"
    }
