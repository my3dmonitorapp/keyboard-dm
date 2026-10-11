"""Tests for the deterministic Milestone S1 simulated device."""

import pytest

from desktop_app.device import DeviceConnectionError, SimulatedESP32S3Device


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

    device.send_key_assignment("K07", "A")
    states = device.get_key_states()

    assert len(states) == 75
    assert states["K07"] == "A"
    assert states["K75"] == "NONE"
    states["K07"] = "changed outside device"
    assert device.get_key_states()["K07"] == "A"


@pytest.mark.parametrize("key_id", ["K00", "K76", "K7", "not-a-key"])
def test_invalid_key_is_rejected(key_id: str) -> None:
    device = SimulatedESP32S3Device()
    device.connect()

    with pytest.raises(ValueError, match="Unknown key ID"):
        device.send_key_assignment(key_id, "A")


def test_invalid_assignment_is_rejected() -> None:
    device = SimulatedESP32S3Device()
    device.connect()

    with pytest.raises(ValueError, match="K01 exceeds 32 characters"):
        device.send_key_assignment("K01", "A" * 33)
    with pytest.raises(TypeError, match="Assignment must be a string"):
        device.send_key_assignment("K01", 123)  # type: ignore[arg-type]


def test_no_connection_behavior_is_explicit() -> None:
    device = SimulatedESP32S3Device()

    assert device.get_key_states() == {}
    with pytest.raises(DeviceConnectionError, match="device is disconnected"):
        device.send_key_assignment("K01", "A")


def test_transport_rejects_unknown_value() -> None:
    device = SimulatedESP32S3Device()

    with pytest.raises(ValueError, match="'usb' or 'ble'"):
        device.set_transport("wifi")
