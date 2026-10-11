# Keyboard75 Desktop Application

The Milestone S1 desktop application edits the **PROVISIONAL** 5 × 15 layout and communicates only with its deterministic simulated ESP32-S3 device. It makes no USB, BLE, network, or hardware calls.

## Setup

From the repository root, create and activate a Python virtual environment, then install the two development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install PySide6 pytest
```

The repository's existing `.venv` can be used directly without activation by running `.venv/bin/python` in the commands below.

## Launch

With the virtual environment active:

```bash
python -m desktop_app
```

Or directly:

```bash
.venv/bin/python -m desktop_app
```

The window shows all 75 stable key IDs, their assignments, profile actions, and the simulated device controls. The displayed physical arrangement is **PROVISIONAL**, not a final keyboard layout.

## Smoke test

The smoke entrypoint selects K07, assigns `A`, saves and reloads a temporary profile, connects the simulated device, verifies USB preference for a connected host, sends the assignment, checks device state, and exits:

```bash
.venv/bin/python -m desktop_app --smoke
```

It forces Qt's offscreen platform, so the same command works without a display. This explicit form works too:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m desktop_app --smoke
```

A successful run exits 0 and prints `Keyboard75 smoke test passed`. A failed check exits nonzero with a message beginning `Keyboard75 smoke test FAILED`.

## Tests

Run the complete suite from the repository root:

```bash
.venv/bin/python -m pytest tests/ -q
```

Run only the end-to-end smoke pytest with:

```bash
.venv/bin/python -m pytest tests/test_smoke.py -q
```

## Profiles

Profiles are version 1 JSON files containing assignments for every key from K01 through K75. Choose the location through **File → Save** and **File → Open**. There is no implicit system-wide profile directory; `profiles/` under the repository root is the recommended location for local development files.

The command-line smoke test uses an automatically removed temporary directory and does not create a persistent profile.

## Troubleshooting: no graphical display

The interactive application needs an X11, Wayland, or other Qt-supported display. On a headless machine, use the smoke command or the pytest suite; both configure `QT_QPA_PLATFORM=offscreen`.

If the interactive launch reports that a graphical display is required, start it in a desktop session with `DISPLAY` or `WAYLAND_DISPLAY` configured. Do not use offscreen mode for interactive editing because no visible window will be available.
