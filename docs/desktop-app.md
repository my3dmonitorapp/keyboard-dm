# Keyboard75 Desktop Application

Milestone S1.1 is a universal PySide6 keyboard configurator for built-in 6-, 9-, 12-, and 75-key layouts plus custom grids from 2 to 500 keys. It communicates only with a deterministic simulated ESP32-S3 device: the application makes no real USB, BLE, network, firmware, or hardware calls.

## Setup

From the repository root, create and activate a Python virtual environment, then install the development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install PySide6 pytest
```

The repository's existing `.venv` can also be used directly by replacing `python` with `.venv/bin/python` in the commands below.

## Launch

```bash
python -m desktop_app
```

Choose **Layout → L06**, **L09**, **L12**, or **L75** for a built-in layout. Each layout uses stable row-major IDs from K01 through its key count. L75 remains a provisional 15 × 5 physical arrangement. Choose **Layout → Custom...** to enter a key count and optional column/row dimensions; omitted dimensions are derived automatically.

Switching layouts preserves assignments for shared key IDs and initializes newly added keys to `NONE`. If the current layout has unsaved changes, the application asks whether to save, discard, or cancel before switching.

## Local profiles and hardware configuration

**File → Save Local Profile...** writes a version 1 JSON file on the local computer. A missing `.json` suffix is added automatically. **File → Open Local Profile...** accepts the profile only when its key IDs exactly match the active layout; a mismatch displays a clear error and leaves the current assignments intact.

Saving or loading a local profile is never a hardware write or hardware read. The separate device controls affect only the in-memory simulator. No real keyboard is configured by this application.

The title and status bar show the current local profile and `(unsaved)` state. Closing, opening another profile, or switching layouts while changes are pending invokes the unsaved-changes guard.

## Keyboard projects

A project combines a name, layout metadata, geometry, and version 1 assignments in one `*.kb75.json` file. Use **File → Projects → New Project...**, **Save Project**, and **Open Project** to manage projects. Opening a project restores both its layout and assignments and re-synchronizes the simulated device's key set.

Project and profile user data belongs in the repository's ignored `profiles/` directory. These files are local working data and are not source-controlled.

## Smoke test

The smoke flow verifies the real GUI, a 75-key profile round-trip, simulated USB preference, a switch to the 12-key layout, and a 12-key project save/reload:

```bash
python -m desktop_app --smoke
```

The command forces Qt's offscreen platform, exits 0 on success, and prints `Keyboard75 smoke test passed`. A failed check exits nonzero with a message beginning `Keyboard75 smoke test FAILED`.

## Tests

Run the complete suite headlessly from the repository root:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q
```

Run only the end-to-end smoke test with:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_smoke.py -q
```

## Troubleshooting: no graphical display

The interactive application needs an X11, Wayland, or another Qt-supported display. On a headless machine, use the smoke command or pytest suite. If normal launch reports that a graphical display is required, start it in a desktop session with `DISPLAY` or `WAYLAND_DISPLAY` configured; offscreen mode does not create a visible interactive window.
