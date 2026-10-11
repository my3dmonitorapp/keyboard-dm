# Documentation Changelog

## 2026-10-11 — BD-1 Bluetooth-first standard-ESP32 planning baseline

- Adopted [BD-1](hardware-decision-2026-10-11-bt-first.md): the primary target is now a standard ESP32 (preferably an ESP32-WROOM-32 DevKit-class or similar economical board; exact part **TBD**) with BLE HID as the primary keyboard transport.
- Removed native USB HID as a requirement for the 75-key keyboard and retained USB serial through the board's USB-UART bridge or routed UART for programming, firmware updates, and configuration.
- Preserved the board-independent S1.2 typed-action model and profile v2 format, and documented an extensible capability matrix with ESP32-C3, ESP32-S2, and ESP32-S3 deferred while the standard ESP32 is implemented first.
- Preserved the mandatory pre-firmware verification gate for as-built matrix wiring, diode orientation, continuity, and confirmed GPIO mapping; no pins, board purchase, battery design, or RGB hardware are asserted.
- Updated `docs/product-specification.md` to v1.1, `docs/hardware-requirements.md`, `docs/development-roadmap.md`, and this changelog. Planned commit: `BD-2: planning docs adopt Bluetooth-first standard ESP32 (spec v1.1, hardware reqs, roadmap retargeted, changelog)`.

## 2026-10-11 — Desktop application Milestone S1.2

- T1: Added a typed, extensible action model for keyboard keys, sided modifier events, shortcuts, media controls, and losslessly retained legacy values.
- T2: Upgraded local profiles to version 2 and added deterministic, lossless migration of version 1 string assignments.
- T3: Replaced the plain-text assignment field with a compact action editor for single keys, modifiers, shortcuts, media controls, apply, and clear.
- T4: Updated the simulated device to accept structured actions, retain canonical payloads, expose readable wire labels, and round-trip actions.
- T5: Closed the verification matrix, extended the GUI smoke flow to typed shortcut save/reopen, refreshed user documentation, and completed the final regression sweep.
- Deliverable state: S1.2 is complete for local profile/project editing and deterministic simulated-device integration. The optional shortcut recorder was not implemented; macro and layer extension interfaces exist but recording and layer behavior are not implemented; real BLE/USB HID transport remains pending the firmware hardware gate.

## 2026-10-11 — Desktop application Milestone S1.1

- Expanded the configurator from the provisional 75-key board to built-in 6-, 9-, 12-, and 75-key layouts plus custom 2–500-key grids with stable row-major IDs.
- Hardened version 1 profile persistence for variable key sets, clear mismatch errors, `.json` suffix handling, save feedback, and unsaved-changes protection.
- Added named local keyboard projects that restore layout metadata, geometry, and assignments while keeping legacy 75-key profiles compatible.
- Made the simulated device follow the active layout and clarified throughout the UI and documentation that local profile/project saves never write to hardware.
- Added headless regression coverage across all built-in sizes and a custom size, GUI layout selection and save/reopen, error-state preservation, close guards, small-layout device operation, legacy compatibility, and a 12-key project smoke flow.
- Marked Track A S1.1 complete; subsequent Track A milestones remain TBD.

## 2026-10-11 — Desktop application Milestone S1

- Completed Track A Milestone S1 with the **PROVISIONAL** 75-key PySide6 layout editor.
- Added version 1 JSON profile save/load validation for K01–K75.
- Added deterministic simulated ESP32-S3 connection, BLE/USB transport selection, and assignment state.
- Added GUI device integration and an offscreen end-to-end smoke entrypoint.
- Added automated coverage for the layout, GUI, profiles, simulated device, and smoke flow.
- Split the roadmap into Track A (desktop application) and Track B (ESP32-S3 firmware); Track B remains **BLOCKED** behind the Phase 2 hardware verification gate.

## 2026-10-11 — Phase 0 baseline

- Confirmed the **ESP32-S3** as the single and only target MCU for Keyboard75.
- This decision replaces and supersedes the previously planned standard ESP32 target.
- Added the Phase 0 planning baseline: product specification v1.0, hardware requirements, and development roadmap.
- Kept GPIO allocation, exact matrix wiring, diode orientation, RGB hardware, and battery circuitry explicitly **TBD** pending hardware confirmation.
- Historical note: this baseline is superseded by BD-1 and product specification v1.1 above.
