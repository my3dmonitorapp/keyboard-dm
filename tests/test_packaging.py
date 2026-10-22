"""Checks for the optional prebuilt desktop artifact."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def test_built_keyboarddm_smoke() -> None:
    binary = Path(__file__).resolve().parents[1] / "dist" / "KeyboardDM"
    if not binary.is_file():
        pytest.skip("dist/KeyboardDM has not been built")

    environment = os.environ.copy()
    environment.pop("VIRTUAL_ENV", None)
    environment.pop("PYTHONPATH", None)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [str(binary), "--smoke"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, (
        f"packaged smoke test failed with exit {completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
