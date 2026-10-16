# Keyboard DM Product Specification

Version: 1.1
Date: 2026-10-11  
Status: Phase 0 baseline, updated by BD-1

## 1. Product definition

Keyboard DM is a universal programmable keyboard platform built around a standard ESP32, preferably an ESP32-WROOM-32 DevKit-class board or similar economical board; the exact part remains **TBD**. It shall operate primarily as a Bluetooth Low Energy (BLE) HID keyboard. Keyboard DM is layout-agnostic: it supports 6-, 9-, 12- and 75-key matrices and fully custom layouts, with 75 keys as the reference development target. USB serial, provided by the development board's USB-UART bridge or a routed UART, shall be used for programming, firmware updates, and configuration. Native USB HID is not a requirement and is not available on the standard ESP32.

Users shall be able to customize key assignments, macros, shortcuts, profiles, and RGB lighting where supported by the eventual LED hardware, with settings retained in ESP32 flash/NVS. Battery operation is optional and deferred; its scope remains **TBD**.

The standard ESP32 is the primary implementation target. The desktop configurator and its S1.2 typed-action/profile-v2 model remain board-independent. Future support for ESP32-C3, ESP32-S2, and ESP32-S3 is deferred behind an extensible board-capability system; no board is purchased, asserted selected, or authorized for additional firmware by this specification.

## 2. Goals

- Provide reliable keyboard operation over BLE HID, including pairing and reconnection.
- Support all 75 physical keys through a diode-protected switch matrix.
- Allow users to define key assignments, shortcuts, macros, and reusable profiles.
- Send board-agnostic configuration to the standard ESP32 over USB serial and preserve it in flash/NVS.
- Keep layout, assignments, and configuration formats independent of board-specific GPIO and transport details.
- Support an extensible board-capability system, with ESP32-C3, ESP32-S2, and ESP32-S3 capability entries deferred.
- Provide configurable RGB lighting only after the LED hardware is confirmed.
- Keep the architecture ready for optional future battery operation after the battery circuit is defined.

## 3. Scope

### 3.1 In scope for the product

- One 75-key mechanical-key layout.
- BLE HID keyboard operation as the primary input transport.
- USB serial for programming, firmware updates, and device configuration; it is not a keyboard input transport.
- User-configurable key assignments, macros, shortcuts, and profiles.
- Board-independent S1.2 typed actions and profile v2 configuration.
- Persistent on-device settings in ESP32 flash/NVS.
- An extensible board-capability architecture, with only the standard ESP32 implemented first.
- Configurable RGB lighting if supported by confirmed LED hardware.
- Optional future battery support.

### 3.2 Out of scope for this specification phase

- Firmware implementation or framework selection.
- Firmware for ESP32-C3, ESP32-S2, or ESP32-S3.
- Native USB HID for the 75-key standard-ESP32 target.
- PCB or schematic design.
- Exact matrix wiring or diode orientation.
- GPIO assignments or pinmaps.
- A final standard-ESP32 board/module or flash capacity.
- A final RGB LED type, count, topology, or electrical budget.
- A final battery, charger, protection circuit, connector, capacity, or runtime target.
- Manufacturing, enclosure, commercial, and certification plans.

## 4. Functional requirements

| ID | Requirement | Verification intent |
| --- | --- | --- |
| FR-01 | The product shall expose a standards-compatible keyboard interface through BLE HID. | Confirm enumeration, pairing, and keyboard input on supported BLE hosts. |
| FR-02 | The product shall support secure BLE pairing/bonding and reconnect behavior. | Confirm first pairing, bonded reconnect, disconnect recovery, and reset behavior on supported hosts. |
| FR-03 | The product shall use BLE as its keyboard input transport; USB serial shall be limited to programming, firmware updates, and configuration. | Verify BLE key reporting and verify that the USB-UART connection does not present a USB HID keyboard. |
| FR-04 | BLE connection, disconnection, and reset transitions shall not duplicate events or leave keys stuck. | Exercise transitions and confirm a clean, unambiguous keyboard state after each one. |
| FR-05 | The product shall scan and report all 75 mechanical keys through a diode-protected matrix. | Confirm every key independently after the matrix is finalized. |
| FR-06 | The product shall support custom key assignments. | Save and exercise a non-default assignment. |
| FR-07 | The product shall support user-defined macros and shortcuts. | Save and exercise representative supported sequences. |
| FR-08 | The product shall support multiple selectable configuration profiles. | Save, switch, and restore at least two distinct profiles; final capacity is **TBD**. |
| FR-09 | The product shall provide configurable RGB lighting if supported by the confirmed LED hardware. | Verify supported effects and controls after LED hardware is selected. |
| FR-10 | The product shall retain user settings in standard-ESP32 flash/NVS across reset and power loss. | Change settings, power-cycle the unit, and confirm restoration. |
| FR-11 | The product architecture shall accommodate optional future battery operation. | Review the design after battery scope, circuitry, and power targets are confirmed. |

## 5. Behavior requirements

### 5.1 BLE input and USB-serial configuration

- BLE HID is the primary and only required keyboard input transport for the 75-key standard-ESP32 target.
- USB serial is the programming, firmware-update, and configuration channel; it is not an input transport and has no priority relationship with BLE HID.
- The exact BLE pairing/reset experience, transition timing, bonded-host capacity, wake behavior, and reconnect behavior are **TBD** and must be resolved before implementation.
- BLE connection, disconnection, and reset transitions shall not intentionally duplicate a key event.
- Recovery from an interrupted connection or reset shall leave the keyboard in an unambiguous state with no stuck keys.

### 5.2 Configuration and persistence

- The S1.2 desktop configuration model represents assignments as typed actions: a single keyboard key, an explicit sided modifier down/up event, a shortcut containing one to four sided modifiers plus one keyboard key, or one of six consumer-HID media controls.
- Desktop local profiles use schema version 2 and store structured action payloads. Version 1 string assignments are migrated deterministically; unrecognized legacy strings are retained verbatim rather than discarded.
- This typed-action model and profile v2 format are board-agnostic and shall remain independent of board-specific GPIO and transport details.
- Key assignments, macros, shortcuts, profiles, lighting settings, and relevant user preferences shall be stored in standard-ESP32-accessible non-volatile flash/NVS.
- No external configuration storage device is assumed.
- Settings shall have a defined schema/version so later product revisions can validate or migrate stored data.
- Factory defaults and a user-accessible reset behavior are required; their exact interaction is **TBD**.
- Limits for macro length, profile count, and configuration size are **TBD** pending memory selection and product decisions.

### 5.3 RGB lighting

- Lighting shall be configurable independently of normal key reporting if supported by the confirmed LED hardware.
- A safe default state and a method to disable lighting shall be provided when RGB is included.
- Brightness, effects, persistence, and behavior per profile are product requirements only if RGB hardware is selected; their exact supported ranges are **TBD**.
- LED type, count, layout, protocol, voltage, current, and update topology are all **TBD**.

## 6. Quality attributes

- **Correctness:** A physical key action shall produce the configured logical action without unintended duplicate or missing events under supported operating conditions.
- **Reliability:** BLE connection changes and power cycles shall not corrupt persisted user settings or leave stuck keys.
- **Responsiveness:** BLE input latency targets are **TBD** and must be set before verification planning closes.
- **Interoperability:** The supported BLE host operating-system matrix is **TBD**.
- **Maintainability:** Layouts, typed actions, and profile data shall remain board-independent; board capabilities, GPIO configuration, configuration transport, BLE HID output, RGB, and battery support shall remain separable.
- **Safety:** RGB and optional future battery behavior shall remain within confirmed electrical and thermal budgets; those budgets are currently **TBD**.

## 7. Release acceptance criteria

A product release is acceptable only when:

1. All 75 keys pass matrix, rollover, and stuck-key testing against the finalized matrix design.
2. BLE HID pairing, bonding, reconnect, and keyboard behavior pass the approved host compatibility test set.
3. BLE connection/disconnection and reset transitions pass duplicate-event and stuck-key tests.
4. USB serial supports the approved programming, firmware-update, and profile-v2 configuration flows without being treated as a keyboard input transport.
5. Key assignments, macros, shortcuts, and profiles behave as specified.
6. Stored settings survive reset and power-cycle tests, including interrupted-write testing.
7. If RGB is included in that release, its behavior passes functional and electrical tests against the selected LED hardware.
8. If battery operation is included in that release, its safety, charging, power-path, runtime, and low-battery requirements are confirmed and verified.

Targets and test procedures that depend on unfinished hardware remain gated and **TBD**.

## 8. Open decisions

- Specific standard-ESP32 board/module and flash capacity (recommended class: ESP32-WROOM-32 DevKit): **TBD**.
- Matrix row/column topology, wiring, and diode orientation: **TBD**.
- Exact GPIO allocation: **TBD**; no pins are assigned by this specification.
- Battery scope and, if included, chemistry, capacity, protection, charging, power path, connector, monitoring, and runtime target: **TBD**.
- RGB scope and, if included, LED type, count, placement, electrical interface, and power budget: **TBD**.
- Supported BLE host operating systems and compatibility matrix: **TBD**.
- Input latency, rollover, debounce, wake, sleep, pairing, and reconnect targets: **TBD**.
- Profile count, macro limits, configuration framing over USB serial, and reset behavior: **TBD**.

## 9. Change note

- **2026-10-11 — v1.1:** Adopted [BD-1](hardware-decision-2026-10-11-bt-first.md): changed the primary MCU to a standard ESP32 (ESP32-WROOM-32 DevKit class, exact part **TBD**), made BLE HID the primary keyboard transport, removed native USB HID as a 75-key requirement, retained USB serial for programming/updates/configuration, and established board-independent capability support with C3/S2/S3 deferred. No pin-level decisions are made by this specification.
- **2026-10-11 — v1.0:** Established the first product specification in this repository. Confirmed the ESP32-S3 as the sole target MCU, replacing the previously planned standard ESP32. No pin-level decisions are made by this specification. This baseline is superseded by BD-1 and v1.1.
- **2026-10-11 — S1.2 note:** Documented the desktop typed-action model and version 2 local-profile schema; this does not authorize or define firmware transport.
