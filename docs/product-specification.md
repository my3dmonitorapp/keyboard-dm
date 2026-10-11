# Keyboard75 Product Specification

Version: 1.0  
Date: 2026-10-11  
Status: Phase 0 baseline

## 1. Product definition

Keyboard75 is a 75-key mechanical keyboard built around the ESP32-S3. It shall operate as a native USB HID keyboard when wired and as a Bluetooth Low Energy (BLE) HID keyboard when wireless. Users shall be able to customize key assignments, macros, shortcuts, profiles, and RGB lighting, with settings retained on the ESP32-S3.

The ESP32-S3 is the project's single and only target MCU. This confirmed decision supersedes the earlier plan to use a standard ESP32.

## 2. Goals

- Provide reliable wired keyboard operation over native USB HID.
- Provide reliable wireless keyboard operation over BLE HID.
- Prefer USB automatically whenever a valid USB host connection is available.
- Support all 75 physical keys through a diode-protected switch matrix.
- Allow users to define key assignments, shortcuts, macros, and reusable profiles.
- Provide configurable RGB lighting once the LED hardware is confirmed.
- Preserve user settings across resets and power cycles without external configuration storage.
- Keep the architecture ready for future battery operation after the battery circuit is defined.

## 3. Scope

### 3.1 In scope for the product

- One 75-key mechanical-key layout.
- Native USB HID keyboard operation.
- BLE HID keyboard operation.
- Automatic transport selection with USB preferred while connected to a host.
- User-configurable key assignments, macros, shortcuts, and profiles.
- Configurable RGB lighting.
- Persistent on-device settings.
- Future battery support.

### 3.2 Out of scope for this specification phase

- Firmware implementation or framework selection.
- PCB or schematic design.
- Exact matrix wiring or diode orientation.
- GPIO assignments or pinmaps.
- A final RGB LED type, count, topology, or electrical budget.
- A final battery, charger, protection circuit, connector, capacity, or runtime target.
- Manufacturing, enclosure, commercial, and certification plans.

## 4. Functional requirements

| ID | Requirement | Verification intent |
| --- | --- | --- |
| FR-01 | The product shall expose a standards-compatible keyboard interface through native USB HID. | Confirm enumeration and keyboard input on supported host systems. |
| FR-02 | The product shall expose a keyboard interface through BLE HID. | Confirm pairing, reconnection, and keyboard input on supported BLE hosts. |
| FR-03 | The product shall support switching between USB and BLE operation. | Exercise connection and disconnection transitions in both directions. |
| FR-04 | When connected to a valid USB host, the product shall prefer USB for keyboard input. | Verify that input is routed by USB while the host connection is valid. |
| FR-05 | The product shall scan and report all 75 mechanical keys through a diode-protected matrix. | Confirm every key independently after the matrix is finalized. |
| FR-06 | The product shall support custom key assignments. | Save and exercise a non-default assignment. |
| FR-07 | The product shall support user-defined macros and shortcuts. | Save and exercise representative supported sequences. |
| FR-08 | The product shall support multiple selectable configuration profiles. | Save, switch, and restore at least two distinct profiles; final capacity is TBD. |
| FR-09 | The product shall provide configurable RGB lighting. | Verify supported effects and controls after LED hardware is selected. |
| FR-10 | The product shall retain user settings on the ESP32-S3 across reset and power loss. | Change settings, power-cycle the unit, and confirm restoration. |
| FR-11 | The architecture shall accommodate future battery operation. | Review the design after battery circuitry and power targets are confirmed. |

## 5. Behavior requirements

### 5.1 Transport priority

- USB is the preferred transport whenever a valid USB host connection is present.
- BLE remains the wireless transport when USB host operation is unavailable.
- The exact transition timing, host-presence detection rule, BLE behavior while USB is active, and user override behavior are TBD and must be resolved before implementation.
- Switching transports shall not intentionally duplicate a key event across both transports.
- Recovery from an interrupted transition shall leave the keyboard in one unambiguous active-input mode.

### 5.2 Configuration and persistence

- The S1.2 desktop configuration model represents assignments as typed actions: a single keyboard key, an explicit sided modifier down/up event, a shortcut containing one to four sided modifiers plus one keyboard key, or one of six consumer-HID media controls.
- Desktop local profiles use schema version 2 and store structured action payloads. Version 1 string assignments are migrated deterministically; unrecognized legacy strings are retained verbatim rather than discarded.
- Key assignments, macros, shortcuts, profiles, lighting settings, and relevant user preferences shall be stored in ESP32-S3-accessible non-volatile flash.
- No external configuration storage device is assumed.
- Settings shall have a defined schema/version so later product revisions can validate or migrate stored data.
- Factory defaults and a user-accessible reset behavior are required; their exact interaction is TBD.
- Limits for macro length, profile count, and configuration size are TBD pending memory selection and product decisions.

### 5.3 RGB lighting

- Lighting shall be configurable independently of normal key reporting.
- A safe default state and a method to disable lighting shall be provided.
- Brightness, effects, persistence, and behavior per profile are product requirements, but their exact supported ranges are TBD.
- LED type, count, layout, protocol, voltage, current, and update topology are all TBD.

## 6. Quality attributes

- **Correctness:** A physical key action shall produce the configured logical action without unintended duplicate or missing events under supported operating conditions.
- **Reliability:** Transport changes and power cycles shall not corrupt persisted user settings.
- **Responsiveness:** Wired and wireless input latency targets are TBD and must be set before verification planning closes.
- **Interoperability:** The supported USB and BLE host operating-system matrix is TBD.
- **Maintainability:** Product behavior shall remain separable from hardware-specific matrix, LED, and power details so confirmed hardware can be incorporated without changing the product goals.
- **Safety:** RGB and future battery behavior shall remain within the confirmed electrical and thermal budgets; those budgets are currently TBD.

## 7. Release acceptance criteria

A product release is acceptable only when:

1. All 75 keys pass matrix, rollover, and stuck-key testing against the finalized matrix design.
2. USB HID and BLE HID each pass the approved host compatibility test set.
3. USB preference and every approved transport transition pass repeatable tests.
4. Key assignments, macros, shortcuts, and profiles behave as specified.
5. Stored settings survive reset and power-cycle tests, including interrupted-write testing.
6. RGB behavior passes functional and electrical tests against the selected LED hardware.
7. If battery operation is included in that release, its safety, charging, power-path, runtime, and low-battery requirements are confirmed and verified.

Targets and test procedures that depend on unfinished hardware remain gated and TBD.

## 8. Open decisions

- ESP32-S3 chip/module variant and its flash/PSRAM capacity: **TBD**.
- Exact GPIO allocation: **TBD**.
- Matrix row/column topology, wiring, and diode orientation: **TBD**.
- RGB LED type, count, placement, electrical interface, and power budget: **TBD**.
- Battery chemistry, capacity, protection, charging, power-path, connector, monitoring, and runtime target: **TBD**.
- Supported host operating systems and compatibility matrix: **TBD**.
- Profile count, macro limits, configuration format, configuration interface, and reset behavior: **TBD**.
- Input latency, rollover, debounce, wake, sleep, and reconnect targets: **TBD**.

## 9. Change note

- **2026-10-11 — v1.0:** Established the first product specification in this repository. Confirmed the ESP32-S3 as the sole target MCU, replacing the previously planned standard ESP32. No pin-level decisions are made by this specification.
- **2026-10-11 — S1.2 note:** Documented the desktop typed-action model and version 2 local-profile schema; this does not authorize or define firmware transport.
