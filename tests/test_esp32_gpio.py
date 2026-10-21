"""ESP32-WROOM-32 GPIO policy and pinmap integration tests."""

import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop_app.app import MatrixPinmapDialog
from desktop_app.esp32_gpio import (
    ESP32_C3_SUPER_MINI_PROFILE,
    FLASH_RESERVED_PINS,
    INPUT_ONLY_PINS,
    SAFE_RECOMMENDED_PINS,
    PinRole,
    suggest_safe_pins,
    validate_gpio_pin,
)
from desktop_app.matrix_model import MatrixConfig


@pytest.mark.parametrize("pin", sorted(FLASH_RESERVED_PINS))
@pytest.mark.parametrize("role", [PinRole.INPUT, PinRole.OUTPUT])
def test_flash_reserved_pins_are_rejected(pin: int, role: PinRole) -> None:
    result = validate_gpio_pin(pin, role)

    assert not result.valid
    assert "wired to the module SPI flash" in result.error


@pytest.mark.parametrize("pin", [20, 24, 28, 29, 30, 31, 37, 38])
@pytest.mark.parametrize("role", [PinRole.INPUT, PinRole.OUTPUT])
def test_unavailable_wroom_devkit_pins_are_rejected(pin: int, role: PinRole) -> None:
    result = validate_gpio_pin(pin, role)

    assert not result.valid
    assert "not available" in result.error


@pytest.mark.parametrize("pin", sorted(INPUT_ONLY_PINS))
def test_input_only_pins_cannot_be_matrix_outputs(pin: int) -> None:
    result = validate_gpio_pin(pin, PinRole.OUTPUT)

    assert not result.valid
    assert "input-only" in result.error


@pytest.mark.parametrize("pin", sorted(INPUT_ONLY_PINS))
def test_input_only_pins_need_external_resistors_for_input(pin: int) -> None:
    result = validate_gpio_pin(pin, PinRole.INPUT)

    assert result.valid
    assert "no internal pull-up or pull-down" in result.warning
    assert "external resistor" in result.warning


@pytest.mark.parametrize(
    ("pin", "reason"),
    [
        (0, "VDDSDIO 1.8V/3.3V"),
        (2, "RTC/boot"),
        (5, "USB D-"),
        (12, "LOW at boot enters download mode"),
        (15, "VSPI/HSPI"),
    ],
)
def test_classic_strapping_pins_are_unavailable(pin: int, reason: str) -> None:
    result = validate_gpio_pin(pin, PinRole.OUTPUT)

    assert not result.valid
    assert "unavailable" in result.error
    assert reason.lower() in result.error.lower()


@pytest.mark.parametrize("pin", [1, 3])
def test_programming_uart_pins_warn_without_blocking(pin: int) -> None:
    result = validate_gpio_pin(pin, PinRole.OUTPUT)

    assert result.valid
    assert "UART0" in result.warning
    assert "console" in result.warning


@pytest.mark.parametrize(
    ("pin", "reason"),
    [(None, "required"), (-1, "outside"), (40, "0..39")],
)
def test_unassigned_and_out_of_range_values_are_rejected(
    pin: int | None, reason: str
) -> None:
    result = validate_gpio_pin(pin, PinRole.INPUT)

    assert not result.valid
    assert reason in result.error


def test_gpio39_is_allowed_for_an_input_role() -> None:
    assert validate_gpio_pin(39, PinRole.INPUT).valid


def test_esp32c3_super_mini_profile_is_capability_only_and_usable() -> None:
    assert ESP32_C3_SUPER_MINI_PROFILE.available_pins == frozenset(
        (0, 1, 3, 4, 5, 6, 7, 10, 20, 21)
    )
    assert validate_gpio_pin(4, PinRole.OUTPUT, profile="esp32c3").valid
    assert "SPI flash" in validate_gpio_pin(
        12, PinRole.INPUT, profile="esp32c3"
    ).error
    assert not validate_gpio_pin(11, PinRole.INPUT, profile="esp32c3").valid
    assert not validate_gpio_pin(18, PinRole.INPUT, profile="esp32c3").valid


@pytest.mark.parametrize("pin", range(12, 18))
def test_esp32c3_flash_pins_are_rejected(pin: int) -> None:
    result = validate_gpio_pin(pin, PinRole.INPUT, profile="esp32c3")
    assert not result.valid
    assert "SPI flash" in result.error


@pytest.mark.parametrize("pin", [2, 8, 9])
def test_esp32c3_strapping_pins_are_unavailable(pin: int) -> None:
    result = validate_gpio_pin(pin, PinRole.OUTPUT, profile="esp32c3")
    assert not result.valid
    assert "strapping" in result.error


def test_esp32c3_suggestions_avoid_straps_uart_usb_and_invented_wiring() -> None:
    suggestions = suggest_safe_pins(9, profile="esp32c3")
    assert suggestions == [0, 1, 3, 4, 5, 6, 7, 10]
    assert set(suggestions).isdisjoint({2, 8, 9, 18, 19, 20, 21})


def test_suggestions_are_always_safe_valid_and_unused() -> None:
    generator = random.Random(20261016)
    safe_set = set(SAFE_RECOMMENDED_PINS)
    for _ in range(500):
        used = set(generator.sample(range(40), generator.randrange(0, 40)))
        roles = [
            generator.choice([PinRole.OUTPUT, PinRole.INPUT])
            for _ in range(generator.randrange(0, 20))
        ]

        suggestions = suggest_safe_pins(roles, used)

        assert len(suggestions) == len(set(suggestions))
        assert not used.intersection(suggestions)
        assert set(suggestions) <= safe_set
        assert all(
            validate_gpio_pin(pin, role).valid
            for pin, role in zip(suggestions, roles)
        )

    never_suggest = {6, 7, 8, 9, 10, 11, 20, 24, 28, 29, 30, 31, 37, 38}
    assert never_suggest.isdisjoint(suggest_safe_pins(40, used_pins=()))


def test_twenty_pin_matrix_is_three_outputs_short_on_the_30_pin_board() -> None:
    assert 5 + 15 == 20
    assert len(SAFE_RECOMMENDED_PINS) == 15
    usable_outputs = [
        pin
        for pin in range(40)
        if validate_gpio_pin(pin, PinRole.OUTPUT).valid
    ]
    assert len(usable_outputs) == 17
    assert (5 + 15) - len(usable_outputs) == 3


def test_pinmap_dialog_shows_specific_rejection_next_to_bad_pin() -> None:
    application = QApplication.instance() or QApplication([])
    config = MatrixConfig(rows=1, cols=1, row_pins=[4], column_pins=[5])
    dialog = MatrixPinmapDialog(config)

    dialog.row_pin_inputs[0].setText("8")
    application.processEvents()

    assert "wired to the module SPI flash" in dialog.row_pin_messages[0].text()
    assert "Row 0: GPIO 8 is wired to the module SPI flash" in dialog.status_label.text()
    dialog.close()


def test_pinmap_dialog_shows_strapping_pin_as_unavailable() -> None:
    application = QApplication.instance() or QApplication([])
    config = MatrixConfig(rows=1, cols=1, row_pins=[0], column_pins=[4])
    dialog = MatrixPinmapDialog(config)

    assert "GPIO 0 is unavailable" in dialog.status_label.text()
    assert "boot state" in dialog.status_label.text()
    assert dialog.warning_label.text() == ""
    dialog.close()
