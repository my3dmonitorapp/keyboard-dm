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
def test_flash_reserved_pins_are_rejected(pin: int) -> None:
    result = validate_gpio_pin(pin, PinRole.INPUT)

    assert not result.valid
    assert "reserved for SPI flash" in result.error


@pytest.mark.parametrize("pin", sorted(INPUT_ONLY_PINS))
def test_input_only_pins_cannot_be_matrix_outputs(pin: int) -> None:
    result = validate_gpio_pin(pin, PinRole.OUTPUT)

    assert not result.valid
    assert "input-only" in result.error


@pytest.mark.parametrize(
    ("pin", "reason"),
    [
        (0, "boot state"),
        (2, "boot state"),
        (3, "UART"),
        (9, "voltage"),
    ],
)
def test_strapping_pins_warn_without_blocking(pin: int, reason: str) -> None:
    result = validate_gpio_pin(pin, PinRole.OUTPUT)

    assert result.valid
    assert reason.lower() in result.warning.lower()


@pytest.mark.parametrize(
    ("pin", "reason"),
    [(None, "required"), (-1, "outside"), (38, "maximum 37"), (40, "0..39")],
)
def test_unassigned_and_out_of_range_values_are_rejected(
    pin: int | None, reason: str
) -> None:
    result = validate_gpio_pin(pin, PinRole.INPUT)

    assert not result.valid
    assert reason in result.error


def test_input_only_pin_is_allowed_for_an_input_role_when_exposed() -> None:
    assert validate_gpio_pin(35, PinRole.INPUT).valid


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


def test_pinmap_dialog_shows_specific_rejection_next_to_bad_pin() -> None:
    application = QApplication.instance() or QApplication([])
    config = MatrixConfig(rows=1, cols=1, row_pins=[4], column_pins=[5])
    dialog = MatrixPinmapDialog(config)

    dialog.row_pin_inputs[0].setText("12")
    application.processEvents()

    assert "reserved for SPI flash" in dialog.row_pin_messages[0].text()
    assert "Row 0: GPIO 12 is reserved for SPI flash" in dialog.status_label.text()
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
