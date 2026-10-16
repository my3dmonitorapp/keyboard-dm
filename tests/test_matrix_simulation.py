"""Matrix event simulation and visual pressed-state coverage."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop_app.action import SingleKeyAction
from desktop_app.app import Keyboard75Window
from desktop_app.device import SimulatedESP32S3Device
from desktop_app.layouts import L06
from desktop_app.matrix_model import MatrixConfig


def _sparse_matrix() -> MatrixConfig:
    return MatrixConfig(rows=3, cols=4, switches={(0, 0), (1, 2), (2, 3)})


def test_headless_matrix_press_release_and_invalid_cells() -> None:
    config = _sparse_matrix()
    device = SimulatedESP32S3Device(config.keys())
    device.set_matrix_config(config)

    device.press_matrix_key(1, 2)
    device.press_matrix_key(1, 2)
    assert device.get_pressed_key_ids() == {"MX-01-02"}

    device.release_matrix_key(1, 2)
    device.release_matrix_key(1, 2)
    assert device.get_pressed_key_ids() == set()

    with pytest.raises(KeyError, match="has no switch"):
        device.press_matrix_key(0, 1)
    with pytest.raises(ValueError, match="outside"):
        device.press_matrix_key(3, 0)
    with pytest.raises(ValueError, match="Unknown key ID"):
        device.press_key("MX-99-99")
    with pytest.raises(ValueError, match="Unknown key ID"):
        device.release_key("MX-99-99")


def test_matrix_device_events_highlight_only_pressed_keycap() -> None:
    application = QApplication.instance() or QApplication([])
    window = Keyboard75Window(layout=L06)
    config = _sparse_matrix()
    window.matrix_config = config
    window.matrix_layout = config.to_layout()
    window._install_layout(config.to_layout())

    pressed = window.key_widgets["MX-01-02"]
    other = window.key_widgets["MX-00-00"]
    window.device.press_matrix_key(1, 2)
    application.processEvents()

    assert pressed.property("devicePressed") is True
    assert pressed.isDown()
    assert other.property("devicePressed") is False
    assert not other.isDown()

    window.device.release_matrix_key(1, 2)
    application.processEvents()
    assert pressed.property("devicePressed") is False
    assert not pressed.isDown()

    window._set_dirty(False)
    window.close()
    application.processEvents()


def test_non_matrix_assignments_and_press_state_remain_independent() -> None:
    device = SimulatedESP32S3Device(("K01", "K02"))
    device.connect()
    device.send_key_assignment("K01", SingleKeyAction("a").to_json())
    device.press_key("K02")

    assert device.get_key_states() == {"K01": "A", "K02": "NONE"}
    assert device.get_pressed_key_ids() == {"K02"}

    device.release_key("K02")
    assert device.get_pressed_key_ids() == set()
    assert device.get_key_states() == {"K01": "A", "K02": "NONE"}
