"""Deterministic simulated Keyboard DM device.

This module deliberately performs no hardware, USB, BLE, socket, or network
operations.  It models only the small device API needed by the desktop app.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .action import Action, ActionValidationError
from .layouts import L75
from .matrix_model import MatrixConfig


class DeviceConnectionError(RuntimeError):
    """Raised when an operation requires a connected simulated device."""


class SimulatedKeyboardDevice:
    """In-memory simulation of the simulated Keyboard DM ESP32 board.

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
        self._matrix_config: MatrixConfig | None = None
        self._pressed_key_ids: set[str] = set()
        self._pressed_state_listeners: list[Callable[[], None]] = []

    def set_key_ids(
        self,
        key_ids: Iterable[str],
        assignments: Mapping[str, dict[str, Any] | str | None] | None = None,
    ) -> None:
        """Adopt a key set, optionally replacing states from an active project."""
        previous_states = self._key_states
        previous_actions = self._key_actions
        previous_pressed = self._pressed_key_ids
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
        self._pressed_key_ids = previous_pressed.intersection(self._key_states)
        if self._pressed_key_ids != previous_pressed:
            self._notify_pressed_state_listeners()

    def set_matrix_config(self, config: MatrixConfig | None) -> None:
        """Set the matrix used to translate row/column simulation events."""
        if config is not None and not isinstance(config, MatrixConfig):
            raise TypeError("Matrix config must be a MatrixConfig or None")
        self._matrix_config = config

    def add_pressed_state_listener(self, listener: Callable[[], None]) -> None:
        """Call *listener* whenever the simulated pressed-key set changes."""
        if not callable(listener):
            raise TypeError("Pressed-state listener must be callable")
        if listener not in self._pressed_state_listeners:
            self._pressed_state_listeners.append(listener)

    def _notify_pressed_state_listeners(self) -> None:
        for listener in tuple(self._pressed_state_listeners):
            listener()

    def press_key(self, key_id: str) -> None:
        """Press a known key ID; pressing an already-pressed key is idempotent."""
        if key_id not in self._key_states:
            raise ValueError(f"Unknown key ID {key_id!r} for the simulated device")
        if key_id not in self._pressed_key_ids:
            self._pressed_key_ids.add(key_id)
            self._notify_pressed_state_listeners()

    def release_key(self, key_id: str) -> None:
        """Release a known key ID; an already-released key is a no-op."""
        if key_id not in self._key_states:
            raise ValueError(f"Unknown key ID {key_id!r} for the simulated device")
        if key_id in self._pressed_key_ids:
            self._pressed_key_ids.remove(key_id)
            self._notify_pressed_state_listeners()

    def _matrix_key_id(self, row: int, column: int) -> str:
        config = self._matrix_config
        if config is None:
            raise ValueError("No active matrix config on the simulated device")
        if type(row) is not int or type(column) is not int:
            raise ValueError("Matrix row and column must be integers")
        if not (0 <= row < config.rows and 0 <= column < config.cols):
            raise ValueError(
                f"Matrix cell ({row}, {column}) is outside "
                f"{config.rows}x{config.cols} bounds"
            )
        key_id = config.key_id_for_cell((row, column))
        if key_id is None:
            raise KeyError(f"Matrix cell ({row}, {column}) has no switch")
        if key_id not in self._key_states:
            raise ValueError(
                f"Matrix key ID {key_id!r} is unknown to the simulated device"
            )
        return key_id

    def press_matrix_key(self, row: int, column: int) -> None:
        """Translate an occupied matrix cell and press its stable key ID."""
        self.press_key(self._matrix_key_id(row, column))

    def release_matrix_key(self, row: int, column: int) -> None:
        """Translate an occupied matrix cell and release its stable key ID."""
        self.release_key(self._matrix_key_id(row, column))

    def get_pressed_key_ids(self) -> set[str]:
        """Return a copy of the currently pressed key IDs."""
        return set(self._pressed_key_ids)

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
