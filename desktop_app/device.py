"""Deterministic simulated ESP32-S3 device for Milestone S1.

This module deliberately performs no hardware, USB, BLE, socket, or network
operations.  It models only the small device API needed by the desktop app.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .layouts import L75
from .profile import MAX_ASSIGNMENT_LENGTH


class DeviceConnectionError(RuntimeError):
    """Raised when an operation requires a connected simulated device."""


class SimulatedESP32S3Device:
    """In-memory simulation of the Keyboard75 ESP32-S3.

    The active transport defaults to BLE. Calling :meth:`set_host_connected`
    with ``True`` automatically prefers USB; calling it with ``False`` returns
    the active transport to BLE. ``set_transport`` remains available for
    deterministic manual selection between those host-state changes.

    Key assignments persist across disconnect/reconnect cycles. For an
    explicit no-connection result, :meth:`get_key_states` returns an empty
    dictionary while disconnected, and writes while disconnected raise
    :class:`DeviceConnectionError`.
    """

    def __init__(self, key_ids: Iterable[str] | None = None) -> None:
        self._connected = False
        self._host_connected = False
        self._transport = "ble"
        if key_ids is None:
            key_ids = (key.key_id for key in L75.keys)
        self._key_states = {key_id: "NONE" for key_id in key_ids}

    def set_key_ids(
        self,
        key_ids: Iterable[str],
        assignments: Mapping[str, str] | None = None,
    ) -> None:
        """Adopt a key set, optionally replacing states from an active project."""
        previous_states = self._key_states
        self._key_states = {
            key_id: (
                assignments.get(key_id, "NONE")
                if assignments is not None
                else previous_states.get(key_id, "NONE")
            )
            for key_id in key_ids
        }

    def connect(self) -> None:
        """Connect the deterministic in-memory device."""
        self._connected = True

    def disconnect(self) -> None:
        """Disconnect the device without discarding its stored assignments."""
        self._connected = False

    def is_connected(self) -> bool:
        """Return whether the simulated device is connected."""
        return self._connected

    def set_transport(self, transport: str) -> None:
        """Set the active transport to exactly ``"usb"`` or ``"ble"``."""
        if transport not in {"usb", "ble"}:
            raise ValueError("Transport must be 'usb' or 'ble'")
        self._transport = transport

    def get_transport(self) -> str:
        """Return the current active transport."""
        return self._transport

    def set_host_connected(self, connected: bool) -> None:
        """Update host presence, preferring USB when present and BLE otherwise."""
        if not isinstance(connected, bool):
            raise TypeError("Host connected state must be a bool")
        self._host_connected = connected
        self._transport = "usb" if connected else "ble"

    def send_key_assignment(self, key_id: str, assignment: str) -> None:
        """Store one assignment after validating the key and assignment value."""
        if key_id not in self._key_states:
            raise ValueError(f"Unknown key ID {key_id!r} for the simulated device")
        if not isinstance(assignment, str):
            raise TypeError("Assignment must be a string")
        if len(assignment) > MAX_ASSIGNMENT_LENGTH:
            raise ValueError(
                f"Assignment for {key_id} exceeds {MAX_ASSIGNMENT_LENGTH} characters"
            )
        if not self._connected:
            raise DeviceConnectionError(
                "Cannot send a key assignment while the device is disconnected"
            )
        self._key_states[key_id] = assignment

    def get_key_states(self) -> dict[str, str]:
        """Return a copy of all key states, or ``{}`` while disconnected."""
        if not self._connected:
            return {}
        return dict(self._key_states)
