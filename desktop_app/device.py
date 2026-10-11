"""Deterministic simulated ESP32-S3 device for Milestone S1.

This module deliberately performs no hardware, USB, BLE, socket, or network
operations.  It models only the small device API needed by the desktop app.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .action import Action, ActionValidationError
from .layouts import L75


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
        self._key_actions: dict[str, dict[str, Any] | None] = {
            key_id: None for key_id in self._key_states
        }

    def set_key_ids(
        self,
        key_ids: Iterable[str],
        assignments: Mapping[str, dict[str, Any] | str | None] | None = None,
    ) -> None:
        """Adopt a key set, optionally replacing states from an active project."""
        previous_states = self._key_states
        previous_actions = self._key_actions
        self._key_states = {}
        self._key_actions = {}
        for key_id in key_ids:
            if assignments is None:
                self._key_states[key_id] = previous_states.get(key_id, "NONE")
                action = previous_actions.get(key_id)
                self._key_actions[key_id] = None if action is None else dict(action)
                continue

            assignment = assignments.get(key_id)
            if isinstance(assignment, dict):
                action = Action.from_json(assignment)
                self._key_actions[key_id] = action.to_json()
                self._key_states[key_id] = action.label
            else:
                # Label-only mappings remain supported for display compatibility,
                # but never enter the structured firmware-facing store.
                self._key_actions[key_id] = None
                self._key_states[key_id] = assignment or "NONE"

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

    def send_key_assignment(
        self, key_id: str, payload: dict[str, Any] | None
    ) -> None:
        """Validate and store one structured action, or clear it with ``None``."""
        if key_id not in self._key_states:
            raise ValueError(f"Unknown key ID {key_id!r} for the simulated device")
        if payload is not None and not isinstance(payload, dict):
            raise TypeError("Action payload must be a dict or None")
        try:
            action = None if payload is None else Action.from_json(payload)
        except ActionValidationError:
            raise
        if not self._connected:
            raise DeviceConnectionError(
                "Cannot send a key assignment while the device is disconnected"
            )
        self._key_actions[key_id] = None if action is None else action.to_json()
        self._key_states[key_id] = "NONE" if action is None else action.label

    def get_key_actions(
        self, key_ids: Iterable[str] | None = None
    ) -> dict[str, dict[str, Any] | None]:
        """Return copies of canonical structured payloads, or ``{}`` if offline."""
        if not self._connected:
            return {}
        selected_ids = tuple(self._key_actions) if key_ids is None else tuple(key_ids)
        unknown_ids = [key_id for key_id in selected_ids if key_id not in self._key_actions]
        if unknown_ids:
            raise ValueError(
                f"Unknown key ID {unknown_ids[0]!r} for the simulated device"
            )
        return {
            key_id: (
                None
                if self._key_actions[key_id] is None
                else Action.from_json(self._key_actions[key_id]).to_json()
            )
            for key_id in selected_ids
        }

    def get_key_states(self) -> dict[str, str]:
        """Return a copy of all key states, or ``{}`` while disconnected."""
        if not self._connected:
            return {}
        return dict(self._key_states)
