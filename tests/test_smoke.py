"""End-to-end headless smoke test for the desktop entry point."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from desktop_app.__main__ import _run_matrix_smoke_flow, main


def test_smoke_entrypoint_runs_real_flow_and_exits_zero(capsys) -> None:
    assert main(["--smoke"]) == 0

    captured = capsys.readouterr()
    assert "Keyboard DM smoke test passed" in captured.out
    assert "matrix 3x4 and sparse 5x15" in captured.out
    assert captured.err == ""


def test_matrix_smoke_flow_writes_v3_project(tmp_path) -> None:
    _run_matrix_smoke_flow(tmp_path / "matrix-smoke")

    assert (tmp_path / "matrix-smoke.kb75.json").is_file()
