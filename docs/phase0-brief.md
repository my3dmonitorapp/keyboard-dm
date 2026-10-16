# Phase 0 Brief — Keyboard DM: ESP32-S3 Architecture Confirmation (2026-10-11)

Status: Confirmed by owner. Supersedes the previously planned standard ESP32.
Scope: PLANNING DOCUMENTS ONLY. No firmware, no GPIO assumptions.

## Confirmed decisions
- Microcontroller: **ESP32-S3** — the ONLY target MCU for this project. Replaces the previously planned standard ESP32.
- Physical key matrix is **currently being soldered**. GPIO allocation and exact matrix wiring are **NOT finalized** — every pin-related field must be an explicit TBD until confirmed.
- RGB LED hardware (type/count) is **not confirmed** — open item.
- Battery circuitry is **not finalized** — future support required, open item.

## Required capabilities (product requirements)
1. Native USB HID for wired keyboard operation.
2. Bluetooth LE HID for wireless operation.
3. Mode switching between USB and Bluetooth; **USB preferred when connected to a host**.
4. 75 configurable mechanical keys.
5. Diode-protected switch matrix (diode orientation TBD).
6. Custom key assignments, macros, shortcuts, and profiles.
7. Configurable RGB lighting (LED hardware TBD).
8. Persistent settings stored on the ESP32-S3 (no external config storage assumed).
9. Future battery support (circuitry not finalized).

## Deliverables for this phase (Markdown, in docs/)
1. `docs/product-specification.md` — v1.0 (no prior spec exists in this repo; state in the doc that ESP32-S3 is confirmed and supersedes the earlier standard-ESP32 plan, with a change-note).
2. `docs/hardware-requirements.md` — ESP32-S3 verified facts with sources (native USB 1.1, BLE 5, flash/PSRAM options), the 75-key diode matrix sizing/IO-budget analysis (e.g. candidate matrix splits such as 15x5 / 5x15 with arithmetic), RGB lighting requirements (hardware TBD), USB+BLE coexistence and USB-preferring mode-switch behavior, persistence requirements, battery/TDP/open-items sections.
3. `docs/development-roadmap.md` — phased plan. Phase 0 (planning) in progress — this task completes it; later phases explicitly GATED behind hardware confirmation (GPIO allocation, matrix wiring, LED hardware, battery circuitry). Include a verification gate before any firmware work begins.

## Hard constraints for this task
- No firmware, no QMK/ZMK code, no pinmaps, no Kicad files, no code of any kind.
- No assumptions about specific GPIO connections — TBD markers only.
- All file changes confined to `docs/`.
