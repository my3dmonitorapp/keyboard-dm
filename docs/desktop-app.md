# Keyboard DM Desktop Application

Milestone M1 extends the PySide6 keyboard configurator with sparse electrical-matrix layouts alongside the built-in 6-, 9-, 12-, and 75-key layouts and custom grids. It communicates only with a deterministic simulated ESP32-S3 device: the application makes no real USB, BLE, network, firmware, or hardware calls.

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

Select a key, then use the inspector's **Action** menu to choose **Single Key**, **Modifier Key**, **Keyboard Shortcut**, **Media Key**, or **None**. Choose the key/media control or sided modifier checkboxes shown for that type, then select **Apply**. **Clear** removes the assignment. Shortcuts are entered manually with one to four sided modifier checkboxes and one main-key menu; press-to-record is not part of S1.2.

### Matrix layout

Choose **Layout → Matrix...** to open `MatrixSetupDialog`, enter the row and column counts, select the populated switch cells, optionally set selected-cell widths, and generate the layout. On the generated layout, select a key to edit its display label and width or move it to an empty row/column cell. Stable matrix key IDs use the form `MX-rr-cc`.

Choose **Layout → GPIO pinmap...** to assign row and column pins independently. The dialog validates entries live against its configurable minimum/maximum range and rejects duplicate pins across all row and column lines. These values are project data only; they are not a verified hardware pinmap and are never written to a device.

Matrix presses can be simulated without hardware through `window.device.press_matrix_key(row, column)` and `release_matrix_key(row, column)`; the matching visible keycap follows the pressed state. Save the matrix with **File → Projects → Save Project** and reopen it from **Open Project** to restore switches, geometry, labels, pins, and typed assignments. The `--smoke` flow described below exercises matrix conversion, v3 save/reload, and press/release simulation headlessly.

## Local profiles and hardware configuration

**File → Save Local Profile...** writes a version 2 JSON file with typed action payloads on the local computer. A missing `.json` suffix is added automatically. **File → Open Local Profile...** accepts the profile only when its key IDs exactly match the active layout; a mismatch displays a clear error and leaves the current assignments intact. Version 1 profiles are migrated on load, with unknown assignment text preserved verbatim.

Saving or loading a local profile is never a hardware write or hardware read. The separate device controls affect only the in-memory simulator. No real keyboard is configured by this application.

The title and status bar show the current local profile and `(unsaved)` state. Closing, opening another profile, or switching layouts while changes are pending invokes the unsaved-changes guard.

## Keyboard projects

A project combines a name, layout metadata, geometry, and version 2 typed assignments in one `*.kb75.json` file. Project schema version 3 additionally persists a matrix configuration when the active layout is matrix-generated. Use **File → Projects → New Project...**, **Save Project**, and **Open Project** to manage projects. Opening a project restores its layout and assignments, restores matrix data when present, and re-synchronizes the simulated device's key set.

Project and profile user data belongs in the repository's ignored `profiles/` directory. These files are local working data and are not source-controlled.

## Smoke test

The smoke flow verifies the real GUI, existing 75- and 12-key flows, 3×4 and sparse 5×15 matrix conversion, a version 3 matrix project round-trip with typed actions and pin/width/label data, and a simulated matrix press/release:

```bash
python -m desktop_app --smoke
```

The command forces Qt's offscreen platform, exits 0 on success, and prints `Keyboard DM smoke test passed`. A failed check exits nonzero with a message beginning `Keyboard DM smoke test FAILED`.

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
