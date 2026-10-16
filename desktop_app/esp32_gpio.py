"""ESP32-WROOM-32 GPIO safety rules for keyboard matrix scanning.

This module deliberately has no Qt dependency so the electrical policy can be
tested and reused independently of the desktop UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


GPIO_MIN = 0
GPIO_MAX = 39
WROOM_USABLE_MAX = 37

FLASH_RESERVED_PINS = frozenset({6, 7, 8, 12, 15})
INPUT_ONLY_PINS = frozenset({35, 36, 37, 38, 39})
STRAPPING_PIN_WARNINGS = {
    0: "BOOT/chip-select strapping; the external circuit can affect boot state",
    2: "general strapping/LED default; the external circuit can affect boot state",
    3: "UART0 RXD strapping; assignment may interfere with the UART function or boot state",
    9: "VDD_SPI voltage strapping; the external circuit can affect flash voltage configuration",
}

# Conservative automatic choices.  Manual entry remains available for other
# pins that pass the authoritative validation below.
SAFE_RECOMMENDED_PINS = tuple(
    pin
    for pin in range(4, 22)
    if pin not in FLASH_RESERVED_PINS and pin not in STRAPPING_PIN_WARNINGS
)


class PinRole(str, Enum):
    """Electrical role used by the default matrix scan direction."""

    OUTPUT = "output"
    INPUT = "input"


@dataclass(frozen=True)
class GPIOValidation:
    """Result of validating one GPIO assignment."""

    pin: object
    role: PinRole
    error: str | None = None
    warning: str | None = None

    @property
    def valid(self) -> bool:
        return self.error is None

    @property
    def is_valid(self) -> bool:
        """Compatibility spelling for callers that prefer ``is_valid``."""
        return self.valid


def _coerce_role(role: PinRole | str) -> PinRole:
    try:
        return PinRole(role)
    except ValueError as error:
        raise ValueError(f"Unsupported GPIO role {role!r}") from error


def validate_gpio_pin(pin: object, role: PinRole | str) -> GPIOValidation:
    """Validate one assignment against ESP32-WROOM-32 and scan-role rules."""
    resolved_role = _coerce_role(role)
    if pin is None:
        return GPIOValidation(pin, resolved_role, "GPIO assignment is required")
    if type(pin) is not int:
        return GPIOValidation(pin, resolved_role, "GPIO assignment must be an integer")
    if pin < GPIO_MIN or pin > GPIO_MAX:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is outside the ESP32 range {GPIO_MIN}..{GPIO_MAX}",
        )
    if pin in FLASH_RESERVED_PINS:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is reserved for SPI flash",
        )
    if resolved_role is PinRole.OUTPUT and pin in INPUT_ONLY_PINS:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is input-only and cannot drive a matrix row",
        )
    if pin > WROOM_USABLE_MAX:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is not usable on ESP32-WROOM-32 (maximum {WROOM_USABLE_MAX})",
        )

    warning = STRAPPING_PIN_WARNINGS.get(pin)
    if warning is not None:
        warning = f"GPIO {pin}: {warning}"
    return GPIOValidation(pin, resolved_role, warning=warning)


def suggest_safe_pins(
    roles: int | Sequence[PinRole | str],
    used_pins: Iterable[int] = (),
    *,
    min_pin: int = GPIO_MIN,
    max_pin: int = WROOM_USABLE_MAX,
) -> list[int]:
    """Return unused conservative pins that pass validation for each role.

    ``roles`` may be a role sequence or a count (which requests output-role
    pins).  Fewer pins are returned when the conservative pool is exhausted.
    """
    requested_roles: Sequence[PinRole | str]
    if type(roles) is int:
        if roles < 0:
            raise ValueError("GPIO suggestion count cannot be negative")
        requested_roles = [PinRole.OUTPUT] * roles
    else:
        requested_roles = roles

    used = {pin for pin in used_pins if type(pin) is int}
    suggestions: list[int] = []
    for role in requested_roles:
        resolved_role = _coerce_role(role)
        match = next(
            (
                pin
                for pin in SAFE_RECOMMENDED_PINS
                if min_pin <= pin <= max_pin
                and pin not in used
                and validate_gpio_pin(pin, resolved_role).valid
            ),
            None,
        )
        if match is None:
            break
        suggestions.append(match)
        used.add(match)
    return suggestions


# Short aliases keep the public API natural for headless consumers.
validate_pin = validate_gpio_pin
suggest_pins = suggest_safe_pins
