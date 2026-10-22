"""ESP32-family GPIO safety rules for keyboard matrix scanning.

This module deliberately has no Qt dependency so the electrical policy can be
tested and reused independently of the desktop UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


GPIO_MIN = 0
GPIO_MAX = 39
WROOM_AVAILABLE_PINS = frozenset({
    1, 3, 4, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33,
    34, 35, 36, 39,
})

FLASH_RESERVED_PINS = frozenset({6, 7, 8, 9, 10, 11})
INPUT_ONLY_PINS = frozenset({34, 35, 36, 39})
STRAPPING_PIN_WARNINGS = {
    # Espressif's classic ESP32 strapping table assigns the VDDSDIO voltage.
    0: "VDDSDIO 1.8V/3.3V strapping pin; an attached matrix can alter boot state",
    # GPIO2 participates in RTC/boot strapping on the classic ESP32.
    2: "RTC/boot strapping pin; an attached matrix can alter boot state",
    # The DevKit documentation identifies GPIO5 as the USB D- strap/function.
    5: "USB D- strapping pin; an attached matrix can alter boot state",
    # LOW requests download mode; HIGH selects unsafe 1.8V flash on 3.3V WROOM.
    12: "BOOT strapping pin; LOW at boot enters download mode, while HIGH selects 1.8V flash and a 3.3V WROOM board will not start",
    # The classic ESP32 strapping table uses GPIO15 for VSPI/HSPI selection.
    15: "VSPI/HSPI select strapping pin; an attached matrix can alter boot state",
}
UART_PIN_WARNINGS = {
    1: "UART0 TX for the USB-serial console/programming port; assignment can conflict with the serial console and future serial configuration transports",
    3: "UART0 RX for the USB-serial console/programming port; assignment can conflict with the serial console and future serial configuration transports",
}

# Conservative automatic choices.  Manual entry remains available for other
# pins that pass the authoritative validation below.
SAFE_RECOMMENDED_PINS = (4, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33)


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


@dataclass(frozen=True)
class GPIOProfile:
    """Pin capabilities and warnings for one chip/board combination."""

    name: str
    available_pins: frozenset[int]
    flash_reserved_pins: frozenset[int]
    input_only_pins: frozenset[int]
    strapping_warnings: dict[int, str]
    uart_warnings: dict[int, str]
    safe_recommended_pins: tuple[int, ...]
    min_pin: int = GPIO_MIN
    max_pin: int = GPIO_MAX
    board_label: str = "ESP32-WROOM-32 / 30-pin DevKit V1"


ESP32_DEVKIT_V1_PROFILE = GPIOProfile(
    name="esp32",
    available_pins=WROOM_AVAILABLE_PINS,
    flash_reserved_pins=FLASH_RESERVED_PINS,
    input_only_pins=INPUT_ONLY_PINS,
    strapping_warnings=STRAPPING_PIN_WARNINGS,
    uart_warnings=UART_PIN_WARNINGS,
    safe_recommended_pins=SAFE_RECOMMENDED_PINS,
)

# Capability-only profile: this is deliberately not a keyboard pin map.  The
# exposed-pin set follows Apache NuttX's ESP32-C3 Super Mini board pinout:
# https://nuttx.apache.org/docs/latest/platforms/risc-v/esp32c3/boards/esp32c3-supermini/index.html
# Chip restrictions follow Espressif's ESP32-C3 GPIO documentation:
# https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/api-reference/peripherals/gpio.html
# GPIO2 is a strap; GPIO8 is a strap plus the board LED; GPIO9 is BOOT.
# GPIO12-17 are flash, GPIO18/19 are native USB Serial/JTAG, GPIO20/21 are
# UART0. GPIO11 is not exposed on the Super Mini header.
ESP32_C3_SUPER_MINI_PROFILE = GPIOProfile(
    name="esp32c3",
    available_pins=frozenset((0, 1, 3, 4, 5, 6, 7, 10, 20, 21)),
    flash_reserved_pins=frozenset(range(12, 18)),
    input_only_pins=frozenset(),
    strapping_warnings={
        2: "strapping pin; the external circuit can affect boot state",
        8: "strapping pin and on-board LED; the external circuit can affect boot state",
        9: "BOOT strapping pin; LOW at reset enters download mode",
    },
    uart_warnings={
        20: "UART0 RX; assignment can conflict with serial programming or diagnostics",
        21: "UART0 TX; assignment can conflict with serial programming or diagnostics",
    },
    safe_recommended_pins=(0, 1, 3, 4, 5, 6, 7, 10),
    max_pin=21,
    board_label="ESP32-C3 Super Mini",
)

_PROFILES: dict[str, GPIOProfile | None] = {
    "esp32": ESP32_DEVKIT_V1_PROFILE,
    "esp32c3": ESP32_C3_SUPER_MINI_PROFILE,
}


def _resolve_profile(profile: str | GPIOProfile) -> GPIOProfile:
    if isinstance(profile, GPIOProfile):
        return profile
    if profile not in _PROFILES:
        raise ValueError(f"Unknown GPIO capability profile {profile!r}")
    resolved = _PROFILES[profile]
    if resolved is None:
        raise ValueError(f"GPIO capability profile {profile!r} is not yet defined")
    return resolved


def get_gpio_profile(profile: str | GPIOProfile) -> GPIOProfile:
    """Resolve a named capability profile without exposing the registry."""
    return _resolve_profile(profile)


def _coerce_role(role: PinRole | str) -> PinRole:
    try:
        return PinRole(role)
    except ValueError as error:
        raise ValueError(f"Unsupported GPIO role {role!r}") from error


def validate_gpio_pin(
    pin: object,
    role: PinRole | str,
    *,
    profile: str | GPIOProfile = "esp32",
) -> GPIOValidation:
    """Validate one assignment against ESP32-WROOM-32 and scan-role rules."""
    resolved_role = _coerce_role(role)
    capabilities = _resolve_profile(profile)
    if pin is None:
        return GPIOValidation(pin, resolved_role, "GPIO assignment is required")
    if type(pin) is not int:
        return GPIOValidation(pin, resolved_role, "GPIO assignment must be an integer")
    if pin < capabilities.min_pin or pin > capabilities.max_pin:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is outside the {capabilities.name} range "
            f"{capabilities.min_pin}..{capabilities.max_pin}",
        )
    if pin in capabilities.flash_reserved_pins:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is wired to the module SPI flash and is unavailable",
        )
    strapping_reason = capabilities.strapping_warnings.get(pin)
    if strapping_reason is not None and pin not in capabilities.available_pins:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is unavailable: {strapping_reason}",
        )
    if pin not in capabilities.available_pins:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is not available on the {capabilities.board_label}",
        )
    if resolved_role is PinRole.OUTPUT and pin in capabilities.input_only_pins:
        return GPIOValidation(
            pin,
            resolved_role,
            f"GPIO {pin} is input-only and cannot drive a matrix row",
        )
    warning = capabilities.strapping_warnings.get(pin)
    if warning is None:
        warning = capabilities.uart_warnings.get(pin)
    if warning is None and pin in capabilities.input_only_pins:
        warning = "input-only; no internal pull-up or pull-down is available, so an external resistor is required"
    if warning is not None:
        warning = f"GPIO {pin}: {warning}"
    return GPIOValidation(pin, resolved_role, warning=warning)


def suggest_safe_pins(
    roles: int | Sequence[PinRole | str],
    used_pins: Iterable[int] = (),
    *,
    min_pin: int = GPIO_MIN,
    max_pin: int = GPIO_MAX,
    profile: str | GPIOProfile = "esp32",
) -> list[int]:
    """Return unused conservative pins that pass validation for each role.

    ``roles`` may be a role sequence or a count (which requests output-role
    pins).  Fewer pins are returned when the conservative pool is exhausted.
    """
    capabilities = _resolve_profile(profile)
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
                for pin in capabilities.safe_recommended_pins
                if min_pin <= pin <= max_pin
                and pin not in used
                and validate_gpio_pin(pin, resolved_role, profile=capabilities).valid
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
