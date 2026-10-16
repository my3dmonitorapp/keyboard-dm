"""End-to-end headless smoke test for the desktop entry point."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from desktop_app.__main__ import main


def test_smoke_entrypoint_runs_real_flow_and_exits_zero(capsys) -> None:
    assert main(["--smoke"]) == 0

    captured = capsys.readouterr()
    assert "Keyboard DM smoke test passed" in captured.out
    assert captured.err == ""
