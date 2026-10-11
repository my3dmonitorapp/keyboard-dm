"""Tests for the deterministic Milestone S1 simulated device."""

import pytest

from desktop_app.action import (
    Action,
    ActionValidationError,
    MediaAction,
    ModifierAction,
    ShortcutAction,
    SingleKeyAction,
)
from desktop_app.device import DeviceConnectionError, SimulatedESP32S3Device
from desktop_app.layouts import L06, L12


def test_connect_and_disconnect() -> None:
    device = SimulatedESP32S3Device()

    assert not device.is_connected()
    device.connect()
    assert device.is_connected()
    device.disconnect()
    assert not device.is_connected()


def test_host_connected_prefers_usb() -> None:
    device = SimulatedESP32S3Device()
    device.set_transport("ble")

    device.set_host_connected(True)

    assert device.get_transport() == "usb"


def test_ble_is_default_when_host_is_absent() -> None:
    device = SimulatedESP32S3Device()

    assert device.get_transport() == "ble"
    device.set_transport("usb")
    device.set_host_connected(False)
    assert device.get_transport() == "ble"


def test_assignment_round_trip_returns_a_copy() -> None:
    device = SimulatedESP32S3Device()
    device.connect()

    device.send_key_assignment("K07", SingleKeyAction("a").to_json())
    states = device.get_key_states()

    assert len(states) == 75
    assert states["K07"] == "A"
    assert states["K75"] == "NONE"
    states["K07"] = "changed outside device"
    assert device.get_key_states()["K07"] == "A"


def test_device_adopts_new_key_set_and_preserves_shared_states() -> None:
    device = SimulatedESP32S3Device(("K01", "K02"))
    device.connect()
    action = SingleKeyAction("b")
    device.send_key_assignment("K02", action.to_json())

    device.set_key_ids(("K01", "K02", "K03"))

    assert device.get_key_states() == {"K01": "NONE", "K02": "B", "K03": "NONE"}
    assert device.get_key_actions() == {
        "K01": None,
        "K02": action.to_json(),
        "K03": None,
    }


@pytest.mark.parametrize("layout", [L06, L12], ids=["6-keys", "12-keys"])
def test_device_reads_and_writes_supported_small_layouts(layout) -> None:
    key_ids = [key.key_id for key in layout.keys]
    device = SimulatedESP32S3Device(key_ids)
    device.connect()

    device.send_key_assignment(key_ids[-1], SingleKeyAction("enter").to_json())

    assert list(device.get_key_states()) == key_ids
    assert device.get_key_states()[key_ids[-1]] == "Enter"


@pytest.mark.parametrize("key_id", ["K00", "K76", "K7", "not-a-key"])
def test_invalid_key_is_rejected(key_id: str) -> None:
    device = SimulatedESP32S3Device()
    device.connect()

    with pytest.raises(ValueError, match="Unknown key ID"):
        device.send_key_assignment(key_id, SingleKeyAction("a").to_json())


def test_structured_actions_round_trip_to_identical_objects() -> None:
    device = SimulatedESP32S3Device()
    device.connect()
    expected = {
        "K01": ShortcutAction(("lctrl", "lshift"), "s"),
        "K02": MediaAction("vol_up"),
        "K03": SingleKeyAction("a"),
        "K04": ModifierAction("lshift", "down"),
    }

    for key_id, action in expected.items():
        device.send_key_assignment(key_id, action.to_json())

    payloads = device.get_key_actions(expected)

    assert {
        key_id: Action.from_json(payload) for key_id, payload in payloads.items()
    } == expected
    states = device.get_key_states()
    assert {key_id: states[key_id] for key_id in expected} == {
        "K01": "Ctrl+Shift+S",
        "K02": "Volume Up",
        "K03": "A",
        "K04": "Left Shift Down",
    }


def test_structured_action_results_are_independent_copies() -> None:
    device = SimulatedESP32S3Device(("K01",))
    device.connect()
    device.send_key_assignment(
        "K01", ShortcutAction(("lctrl", "lshift"), "s").to_json()
    )

    actions = device.get_key_actions()
    assert actions["K01"] is not None
    actions["K01"]["modifiers"].append("lalt")  # type: ignore[index, union-attr]

    assert device.get_key_actions()["K01"] == {
        "type": "shortcut",
        "modifiers": ["lctrl", "lshift"],
        "key": "s",
    }


def test_clear_removes_structured_action_and_keeps_display_state() -> None:
    device = SimulatedESP32S3Device(("K01",))
    device.connect()
    device.send_key_assignment("K01", SingleKeyAction("a").to_json())

    device.send_key_assignment("K01", None)

    assert device.get_key_actions() == {"K01": None}
    assert device.get_key_states() == {"K01": "NONE"}


def test_invalid_structured_payload_is_rejected() -> None:
    device = SimulatedESP32S3Device()
    device.connect()

    with pytest.raises(ActionValidationError, match="Unknown single key"):
        device.send_key_assignment("K01", {"type": "key", "key": "zzz_not_a_key"})


def test_non_dict_payload_is_rejected() -> None:
    device = SimulatedESP32S3Device()
    device.connect()

    with pytest.raises(TypeError, match="dict or None"):
        device.send_key_assignment("K01", 123)  # type: ignore[arg-type]


def test_no_connection_behavior_is_explicit() -> None:
    device = SimulatedESP32S3Device()

    assert device.get_key_states() == {}
    with pytest.raises(DeviceConnectionError, match="device is disconnected"):
        device.send_key_assignment("K01", SingleKeyAction("a").to_json())


def test_transport_rejects_unknown_value() -> None:
    device = SimulatedESP32S3Device()

    with pytest.raises(ValueError, match="'usb' or 'ble'"):
        device.set_transport("wifi")
