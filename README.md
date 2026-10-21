# Keyboard DM (Device Mapper)

Keyboard DM (Device Mapper) is an open-source, cross-platform PySide6 GUI for configuring ESP32-based keyboards. It supports key-by-key action assignment, matrix building with explicit GPIO row and column pins and pin-safety validation, profile and project persistence as JSON, and a simulated device for verification without hardware.

## Features

- A fixed 75-key editor with key IDs `K01` through `K75`; click a key to select it.
- Layout switching, including the L12 12-key layout.
- Per-key actions: single key, modifier, shortcut (for example, `Ctrl+Shift+S`), media, and legacy actions.
- Version-2 JSON profile persistence.
- Version-3 JSON project persistence with embedded matrix configuration.
- A matrix configuration builder for rows, columns, sparse switch positions, key widths, key labels, and row/column GPIO pins.
- Validation for sparse matrices, including 3x4 and 5x15 configurations.
- ESP32 GPIO safety validation.
- A simulated ESP32-S3 device that stores key states and prefers a USB transport when a USB host is connected. This device is for development and testing; it does not flash or drive real hardware from the GUI.

## Quick start

```bash
git clone https://github.com/my3dmonitorapp/keyboard-dm.git
cd keyboard-dm

python -m venv .venv
source .venv/bin/activate
pip install PySide6==6.12.0 pytest==9.1.1
```

Launch the PySide6 6.12 (Qt 6) desktop GUI from the repository root. A graphical display is required:

```bash
python -m desktop_app
```

For a headless smoke check:

```bash
python -m desktop_app --smoke
```

## Project structure

- `desktop_app/` — GUI, actions, matrix model, GPIO validation, simulated device, and profile/project persistence.
- `scripts/`
- `tests/` — pytest tests.

## Hardware direction

The GUI is chip-agnostic in this state: users define rows, columns, switches, and GPIO pins for their ESP32 board. Real-hardware firmware flashing is not part of this repository state.

## Limitations

- No firmware or flashing tooling is included in this branch.
- There is no layer system or macro engine.
- No screenshots are included.
- The device model is simulation-only.

## Current status

This branch exists to bring the README in line with the implemented desktop application; firmware development is tracked separately.

## License

The repository currently contains no `LICENSE` file; licensing will be decided with maintainer approval.
