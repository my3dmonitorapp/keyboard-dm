# Milestone S1 Brief — Desktop Application (Track A) — 2026-10-11

Status: Approved by owner. Track A (desktop app) runs NOW against a simulated device.
Track B (ESP32-S3 firmware) remains BLOCKED behind the Phase 2 hardware verification gate (matrix continuity, diode orientation, GPIO allocation). Do NOT write firmware. Do NOT invent GPIO connections.

Repo state at start: commit 21d2c9c. Phase 0 docs in docs/ are the source of truth (product-specification.md, hardware-requirements.md, development-roadmap.md, changelog.md). A Python venv already exists at .venv/ with PySide6 + preinstalled pytest (do not reinstall system-wide; never touch anything outside this repo).

## Frozen decisions (do not deviate)
- Framework: Python + PySide6 (approved; PySide6 is already installed in .venv).
- Package layout: top-level package `desktop_app/` in the repo root.
  - `desktop_app/__init__.py`, `__main__.py`, `layout_model.py`, `profile.py`, `device.py`, `app.py` (GUI), plus `tests/` in the repo root.
  - Launch: `python -m desktop_app` (GUI) and `python -m desktop_app --smoke` (headless startup smoke, exits 0 on success).
- Stable key IDs: `K01` … `K75`, assigned row-major in the provisional layout (row 1 col 1 = K01 … row 5 col 15 = K75). IDs are stable across repositioning; physical arrangement is NOT finalized.
- Provisional layout: 5 rows × 15 columns, every key 1u × 1u on a unit grid (x = column, y = row, w = 1, h = 1, top-left origin). Every artifact (model, UI, docs) must be visibly labeled PROVISIONAL. Do not invent the final physical arrangement, keycaps, or per-key default assignments (default assignment = "NONE").
- Profile format: JSON, `profile_version: 1`, fields: `device: "/project-esp32s3"`, `created` (ISO 8601), `updated` (ISO 8601), `keys: {"K01": {"assignment": "NONE"}, ...}`. Loader MUST validate: version == 1, all 75 IDs K01–K75 present, assignment is a string of length ≤ 32. Reject unknown versions and malformed files with a clear error. Save writes an updated `updated` timestamp; unknown-version guard makes save/load round-trip safe.
- Simulated device: class `SimulatedESP32S3Device` in `desktop_app/device.py` — NO real hardware, no sockets, no USB/BLE calls. API: `connect()`, `disconnect()`, `is_connected()`, `set_transport("usb"|"ble")`, `get_transport()`, `send_key_assignment(key_id, assignment)`, `get_key_states()`. Transport rule: USB is preferred when a host is connected — expose `set_host_connected(bool)`: when True, transport auto-prefers "usb" (documented in docstring); when False, "ble" is the default active transport. All behavior deterministic (no randomness, no real latency).
- Vendor software: the existing 12-key vendor reference (`reference/` directory and its files) MUST remain untouched and untracked by Git. Do not add it to the repo.

## Per-task scope (executed as 5 separate bounded runs; each run gets this brief + its own task list)
Task 1 — scaffold + layout model: create `.gitignore` (`.venv/`, `__pycache__/`, `*.pyc`, `profiles/*.bak`), `desktop_app/` skeleton (`__init__`, empty `__main__` printing "/project desktop app placeholder"), `layout_model.py` (Key, Layout, `PROVISIONAL_75_LAYOUT` with all 75 IDs, positions, sizes; to_dict/from_dict), `tests/test_layout_model.py` (75 keys, IDs unique K01–K75, grid geometry valid, round-trip). No GUI yet.
Task 2 — GUI: `app.py` PySide6 main window — 15×5 key grid (QGridLayout of labeled buttons, each showing key ID + current assignment, PROVISIONAL banner at top), select a key → right panel with assignment editor (QLineEdit) + "Apply" that updates the in-memory layout; top bar with device connection placeholder (label only); `__main__.py` wires `python -m desktop_app`. Keep device/profile wiring out (next tasks).
Task 3 — profiles: `profile.py` (save/load/validate per frozen spec above) + `tests/test_profile.py`; GUI wiring: File menu Open/Save profile (.json, chosen via QFileDialog), load populates key assignments, save writes all 75.
Task 4 — simulated device: `device.py` per frozen spec + `tests/test_device.py` (connect/disconnect, host-connected ⇒ usb preferred, ble default otherwise, round-trip assignment, get_key_states consistency); GUI wiring: top bar shows connection state + transport, Connect/Disconnect buttons, Apply sends to device (simulated) when connected and updates key display; transport label reflects auto-preference.
Task 5 — smoke + docs + roadmap: `tests/test_smoke.py` driving a real headless QApplication (QT_QPA_PLATFORM=offscreen must work in test): create window, assert 75 key widgets exist, select K07, change assignment to "A", save profile to a temp file, reload, device connect + apply round-trip, clean shutdown exit 0; also make `python -m desktop_app --smoke` perform the same headless check and exit 0. Update `docs/development-roadmap.md` to the two-track structure (Track A desktop / Track B firmware gated), update `docs/changelog.md`, write `docs/desktop-app.md` (setup, launch, test commands), and verify `.gitignore` keeps vendor reference untracked.

## Global rules for every task
- Python 3 (whatever the laptop venv runs), PySide6 for GUI, pytest for tests. No new third-party deps beyond PySide6 + pytest.
- No `input()`, no network, no subprocess, no hardware calls, no flashing.
- Changes confined to this repo (`desktop_app/`, `tests/`, `docs/`, `.gitignore`, `requirements.txt` if needed).
- Before responding: run `.venv/bin/python -m pytest tests/ -q` and (for Task 2+) `.venv/bin/python -c "import desktop_app"` (import sanity), fix failures, then respond with what changed + test output tail. Do not claim success without passing tests.
- Leave `reference/` and `reference-file-list.txt` exactly as they are; ensure they stay untracked.
