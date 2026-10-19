"""ESP32-WROOM-32 GPIO policy and pinmap integration tests."""

import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop_app.app import MatrixPinmapDialog
from desktop_app.esp32_gpio import (
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
        (0, "boot state"),
        (2, "boot state"),
        (5, "PWM at boot"),
        (12, "1.8V flash"),
        (15, "boot log"),
    ],
)
def test_strapping_pins_warn_without_blocking(pin: int, reason: str) -> None:
    result = validate_gpio_pin(pin, PinRole.OUTPUT)

    assert result.valid
    assert reason.lower() in result.warning.lower()


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


def test_esp32c3_profile_is_explicitly_undefined() -> None:
    with pytest.raises(ValueError, match="not yet defined"):
        validate_gpio_pin(4, PinRole.OUTPUT, profile="esp32c3")


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


def test_twenty_unique_matrix_pins_fit_on_the_30_pin_board() -> None:
    rows = list(SAFE_RECOMMENDED_PINS[:5])
    columns = list(SAFE_RECOMMENDED_PINS[5:]) + [34, 35, 36, 39, 0]

    assert len(rows + columns) == 20
    assert len(set(rows + columns)) == 20
    assert all(validate_gpio_pin(pin, PinRole.OUTPUT).valid for pin in rows)
    assert all(validate_gpio_pin(pin, PinRole.INPUT).valid for pin in columns)


def test_pinmap_dialog_shows_specific_rejection_next_to_bad_pin() -> None:
    application = QApplication.instance() or QApplication([])
    config = MatrixConfig(rows=1, cols=1, row_pins=[4], column_pins=[5])
    dialog = MatrixPinmapDialog(config)

    dialog.row_pin_inputs[0].setText("8")
    application.processEvents()

    assert "wired to the module SPI flash" in dialog.row_pin_messages[0].text()
    assert "Row 0: GPIO 8 is wired to the module SPI flash" in dialog.status_label.text()
    dialog.close()


def test_pinmap_dialog_collects_strapping_warnings_in_visible_panel() -> None:
    application = QApplication.instance() or QApplication([])
    config = MatrixConfig(rows=1, cols=1, row_pins=[0], column_pins=[4])
    dialog = MatrixPinmapDialog(config)

    assert "Boot/strapping warnings" in dialog.warning_label.text()
    assert "GPIO 0" in dialog.warning_label.text()
    assert "boot state" in dialog.warning_label.text()
    assert dialog.warning_label.isHidden() is False
    dialog.close()
