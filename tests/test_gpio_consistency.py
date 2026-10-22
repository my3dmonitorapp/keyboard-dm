"""Keep literal firmware pin arrays and desktop capability profiles in lockstep."""

from __future__ import annotations

import re
from pathlib import Path

from desktop_app.esp32_gpio import (
    ESP32_C3_SUPER_MINI_PROFILE,
    ESP32_DEVKIT_V1_PROFILE,
    PinRole,
    UART_PIN_WARNINGS,
    validate_gpio_pin,
)


ROOT = Path(__file__).parents[1]
FAMILY_SOURCES = {
    "esp32": ROOT / "firmware/targets/esp32/main/family.c",
    "esp32c3": ROOT / "firmware/targets/esp32c3/main/family.c",
}


def _literal_pin_array(path: Path, name: str) -> set[int]:
    source = path.read_text(encoding="utf-8")
    match = re.search(
        rf"\.{re.escape(name)}\s*=\s*\{{(?P<pins>[\d,\s]*)\}}",
        source,
    )
    if match is None and name == "input_only_pins":
        assert re.search(r"\.input_only_pin_count\s*=\s*0\s*,", source)
        return set()
    assert match is not None, f"missing literal {name} array in {path}"
    pins = match.group("pins").strip()
    return {int(pin) for pin in re.findall(r"\d+", pins)} if pins else set()


def test_desktop_profiles_exactly_cover_firmware_free_pins() -> None:
    profiles = {
        "esp32": ESP32_DEVKIT_V1_PROFILE,
        "esp32c3": ESP32_C3_SUPER_MINI_PROFILE,
    }
    for family, profile in profiles.items():
        reserved = _literal_pin_array(FAMILY_SOURCES[family], "reserved_pins")
        input_only = _literal_pin_array(FAMILY_SOURCES[family], "input_only_pins")
        firmware_free = set(range(profile.max_pin + 1)) - reserved - input_only
        desktop_allowed = {
            pin
            for pin in range(profile.max_pin + 1)
            if any(
                validate_gpio_pin(pin, role, profile=profile).valid
                for role in PinRole
            )
        }

        # The literal probe arrays are the verified policy source for each
        # target; parsing only these initializers catches desktop/C drift.
        assert desktop_allowed == set(profile.available_pins)
        assert desktop_allowed.isdisjoint(reserved)
        assert firmware_free <= desktop_allowed


def test_classic_input_only_and_unavailable_sets_match_firmware() -> None:
    profile = ESP32_DEVKIT_V1_PROFILE
    reserved = _literal_pin_array(FAMILY_SOURCES["esp32"], "reserved_pins")
    input_only = _literal_pin_array(FAMILY_SOURCES["esp32"], "input_only_pins")

    assert input_only == {34, 35, 36, 37, 38, 39}
    assert set(profile.input_only_pins) == input_only & set(profile.available_pins)
    assert reserved == {
        0, 2, 5, 6, 7, 8, 9, 10, 11, 12, 15,
        20, 24, 28, 29, 30, 31,
    }
    assert set(range(40)) - set(profile.available_pins) == reserved | {37, 38}


def test_family_profiles_remain_distinct() -> None:
    classic = ESP32_DEVKIT_V1_PROFILE
    c3 = ESP32_C3_SUPER_MINI_PROFILE

    assert classic.available_pins != c3.available_pins
    assert classic.flash_reserved_pins != c3.flash_reserved_pins
    assert classic.input_only_pins != c3.input_only_pins
    assert 11 not in classic.available_pins
    assert 11 not in c3.available_pins


def test_documented_68_key_matrix_pin_arithmetic() -> None:
    """5x15 needs 20 GPIOs; 4x15 needs 19; only 17 outputs are usable.

    The exact output list is 1, 3, 4, 13, 14, 16, 17, 18, 19, 21, 22, 23,
    25, 26, 27, 32, 33. GPIO1/3 are the two UART-warned pins, so the final
    classic policy is short by three GPIOs for 5x15 and two GPIOs for 4x15.
    """
    usable_outputs = sorted(
        ESP32_DEVKIT_V1_PROFILE.available_pins
        - ESP32_DEVKIT_V1_PROFILE.input_only_pins
    )

    assert usable_outputs == [
        1, 3, 4, 13, 14, 16, 17, 18, 19,
        21, 22, 23, 25, 26, 27, 32, 33,
    ]
    assert len(usable_outputs) == 17
    assert set(usable_outputs) & set(UART_PIN_WARNINGS) == {1, 3}
    assert 5 + 15 == 20
    assert 4 + 15 == 19
    assert (5 + 15) - len(usable_outputs) == 3
    assert (4 + 15) - len(usable_outputs) == 2
