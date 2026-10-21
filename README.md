# Keyboard DM – Universal ESP32 Keyboard Configurator

## What is Keyboard DM?
Keyboard DM (Device Mapper) is an **open‑source, cross‑platform GUI tool** that lets you configure any ESP32‑based keyboard – from the classic ESP32‑WROOM‑32 to the low‑power ESP32‑C3 – as a fully‑customizable HID device. It generates the firmware source and flash‑ready binaries for the selected chip, handling:
- GPIO‑to‑key mapping (any digital pin can become a key or a combo)
- Layout definition (QWERTY, DVORAK, user‑defined matrices)
- Layer support (Fn‑layers, media shortcuts, macro‑keys)
- Optional visual preview of the resulting key matrix.

The goal is to give makers a **single, Python‑driven workflow** that hides the low‑level build system while exposing every configurable aspect of the keyboard firmware.

---

## Current GUI – PySide6 implementation
The desktop application is built with **PySide6 6.12** (Qt 6). It provides:
- A matrix editor for assigning keys to GPIO pins.
- Real‑time validation of duplicate or invalid assignments.
- Layer management UI (add, reorder, enable/disable).
- Export / Import of configuration files (`.json` compatible with the firmware builder).
- A *simulated* preview window that visualises the key positions (no hardware interaction).

> **Note:** All GUI actions are local; no network or daemon processes are started.

---

## Supported hardware targets
| Chip | Family | Status |
|------|--------|--------|
| **ESP32‑WROOM‑32** (classic) | ESP32 | ✅ Fully supported – build produces a flashable binary. |
| **ESP32‑C3** | ESP32‑C3 | ✅ Fully supported – same workflow, different toolchain. |
| Other ESP families (S2, S3, H2…) | – | ⚠️ *Planned* – the UI schema is ready, but the build scripts are not yet ported. |

---

## Ubuntu development setup (RTX host)
The repository is developed **exclusively on the RTX Ubuntu 26.04 desktop**.
```bash
# 1. Install system prerequisites
sudo apt update && sudo apt install -y python3-pip git cmake build-essential

# 2. Clone the repo (already done on RTX, shown for completeness)
git clone git@github-keyboard-dm:my3dmonitorapp/keyboard-dm.git ~/projects/keyboard75
cd ~/projects/keyboard75

# 3. Create a Python virtual environment (already present in the CI setup)
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install PySide6==6.12.0 pytest==9.1.1

# 4. Run the GUI (offscreen for CI, normal for development)
python -m keyboard_dm_gui   # or: .venv/bin/python -m keyboard_dm_gui
```
> **Important:** The **Codex CLI** on RTX runs with the model `gpt-5.6-sol` (ChatGPT‑subscription‑based). **Never use Astra.**

---

## Keyboard layout, GPIO & key assignment
- Layouts are defined in JSON files under `layout/`. A typical file contains a **matrix** (rows × columns) and a **mapping** object that links each matrix coordinate to a GPIO pin number.
- The GUI editor writes this JSON, which the firmware builder reads to generate the C source (using the `kb75` codegen).
- Keys can be simple (single HID code) or **combo** definitions (`{"combo": ["Ctrl", "C"]}`) – supported by the firmware runtime.

---

## Implemented vs. simulated hardware features
| Feature | Implemented | Simulated / Planned |
|--------|-------------|--------------------|
| GPIO‑to‑key mapping | ✅ | – |
| Matrix preview UI | ✅ | – |
| Layer stacking (Fn, media) | ✅ | – |
| Real HID output (USB) | ✅ (firmware) | – |
| Wireless BLE mode | – | ⚠️ Planned (requires ESP‑BLUEDroid port) |
| Advanced macro engine | – | ⚠️ Planned |

---

## Project roadmap (high‑level)
- **v0.9** – Stabilise ESP32‑C3 support, add automated release builds.
- **v1.0** – First stable public release, comprehensive documentation.
- **v1.1** – BLE wireless mode, community‑contributed keymaps.
- **v2.0** – Full macro language, visual macro editor, plugin system.

---

## Screenshots
*The following images are placeholders – replace them with actual screenshots from the application once they are available.*
- `docs/screenshots/gui_overview.png`
- `docs/screenshots/matrix_editor.png`
- `docs/screenshots/layer_manager.png`

---

## License
The repository currently **does not contain a LICENSE file**. Adding an open‑source license (e.g., MIT or Apache‑2.0) will need your approval before committing.

---

*This README is intended for the repository’s default `main` branch. It was created in a separate `docs/readme` branch to keep the existing `feature/f3-desktop-installer` work untouched.*
