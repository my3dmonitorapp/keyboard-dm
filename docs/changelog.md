# Documentation Changelog

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
