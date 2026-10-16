# Keyboard DM Development Roadmap

Date: 2026-10-11  
Primary target MCU: standard ESP32 (ESP32-WROOM-32 class, part **TBD**)

## 1. Roadmap rules

- The standard ESP32 (ESP32-WROOM-32 DevKit class, exact part **TBD**) is the primary target and supersedes the ESP32-S3-only baseline per [BD-1](hardware-decision-2026-10-11-bt-first.md).
- Work proceeds in two parallel tracks: Track A for the board-independent desktop application and Track B for ESP32 (standard) BLE HID + USB-serial-config firmware.
- The tracks share product decisions, but Track A can use the deterministic simulated device while Track B remains hardware-gated.
- No firmware work may begin until the pre-firmware verification gate in Phase 2 passes.
- GPIO allocation, exact matrix wiring, diode orientation, RGB hardware, and battery circuitry remain **TBD** until confirmed by evidence.
- A phase may begin only when its listed entry gate is satisfied; schedule dates beyond Phase 0 are intentionally **TBD**.

## 2. Parallel tracks

### Track A — Desktop application

Status: **S1.2 complete (2026-10-11)**

Track A runs independently against a deterministic simulated device until verified hardware is available. Existing simulated-device class/UI naming that refers to ESP32-S3 is retained as a documentation-only milestone follow-up; no code rename is authorized here. The provisional layout remains clearly labeled and does not define final key placement or firmware wiring.

Milestone S1 delivered:

- A Python and PySide6 desktop application launched with `python -m desktop_app`.
- A visibly **PROVISIONAL** 5 × 15 editor using stable IDs K01–K75 and default `NONE` assignments.
- Selection and editing for every key through the graphical inspector.
- Version 1 JSON profile creation, validation, save, and load for all 75 assignments.
- A deterministic simulated device originally named for ESP32-S3, with connect/disconnect behavior and its historical BLE/USB simulation behavior; retargeting its naming and behavior is a follow-up outside this documentation-only milestone.
- GUI integration for device state, transport state, and sending assignments to the simulator.
- A real offscreen smoke entrypoint (`python -m desktop_app --smoke`) covering the window, K07 assignment, profile round-trip, USB preference, and simulated device state.
- Automated tests for the layout model, GUI construction, profiles, simulated device, and end-to-end smoke flow.

Milestone S1.1 delivered:

- Built-in 6-, 9-, 12-, and provisional 75-key layouts plus custom 2–500-key grids, all using stable row-major key IDs.
- Variable-size version 1 local profiles with exact key-set validation, legacy 75-key compatibility, visible save state, and unsaved-change guards.
- Named local keyboard projects containing layout metadata, geometry, and assignments.
- Layout-aware simulated-device state for every supported size.
- Headless regression coverage for JSON round-trips, GUI layout selection and save/reopen, mismatch handling, close guards, project switching, and the extended 12-key smoke flow.

Milestone S1.2 delivered:

- Typed keyboard, sided modifier event, shortcut, and consumer-HID media actions with stable serialization and validation.
- Version 2 local profiles plus deterministic, lossless version 1 migration.
- A compact typed GUI action editor and structured simulated-device round-trips.
- Verification coverage for the S1.2 action matrix while retaining S1/S1.1 layout, project, mismatch, and unsaved-change behavior.

Track A milestones after S1.2 remain **TBD** and must not assume unresolved physical layout, wiring, or GPIO decisions. Macro/layer behavior and real BLE HID/USB-serial device transport are not implemented; firmware remains gated below. The S1.2 typed actions and profile v2 format are preserved as board-agnostic interfaces.

### Track B — ESP32 (standard) BLE HID + USB-serial-config firmware

Status: **BLOCKED until the Phase 2 hardware verification gate passes**

Track B must not begin firmware, framework-specific configuration, or executable firmware prototypes until matrix continuity, diode orientation, and GPIO allocation have been verified and the complete Phase 2 gate below passes.

#### Board independence

Per BD-1, firmware planning and the desktop configurator shall keep these concerns separate:

1. **Layout and assignments:** the board-agnostic S1.2 typed-action model and profile v2 format.
2. **Board capability and GPIO configuration:** a per-board descriptor for available/reserved GPIOs, confirmed matrix pinmap, and supported transports and optional features. No pins are assigned in this roadmap.
3. **Desktop-to-device transport:** a pluggable path for configuration; USB serial is used first on the standard ESP32.
4. **BLE HID output:** the primary Keyboard and Consumer-Device report path, consuming the same typed actions regardless of board.
5. **Future RGB and battery:** optional capability blocks enabled only after their hardware is confirmed.

Deferred board-capability entries are documented below; only the standard ESP32 is implemented first:

| Board | BLE HID | USB HID | USB serial config | Roadmap status |
| --- | --- | --- | --- | --- |
| **Standard ESP32 (WROOM-32 class)** | Yes | No | Yes | **PRIMARY**; exact board/module **TBD**. |
| ESP32-C3 | Yes | No | Yes | Deferred capability entry; no firmware in current scope. |
| ESP32-S2 | No | Yes | Yes | Deferred capability entry; USB HID is not a 75-key requirement. |
| ESP32-S3 | Yes | Yes | Yes | Deferred capability entry; no firmware in current scope. |

Multi-board support shall extend the capability system rather than fork the board-agnostic layout/profile model or desktop application.

#### Phase 0 — Product and architecture planning

Status: **Complete with the 2026-10-11 documentation baseline**

Objectives:

- Adopt the standard ESP32 as the primary target, with BLE HID primary and USB serial for programming, updates, and configuration.
- Define the product capabilities and acceptance direction.
- Record verified MCU capabilities and hardware constraints.
- Size candidate 75-key matrix topologies without assigning pins.
- Identify every decision that gates later work.

Deliverables:

- `docs/hardware-decision-2026-10-11-bt-first.md` (BD-1)
- `docs/product-specification.md` v1.1
- `docs/hardware-requirements.md`
- `docs/development-roadmap.md`
- `docs/changelog.md`

Exit condition: BD-1 and the four planning documents exist, agree on the Bluetooth-first standard-ESP32 decision, contain no pinmap or GPIO assumptions, preserve the hardware verification gate, and identify unresolved hardware items as **TBD**.

#### Phase 1 — Physical hardware discovery and decisions

Status: **GATED / not started**

Entry gate: Phase 0 approved.

Required work:

- Finish and inspect the physical key matrix.
- Record the as-built row/column topology and exact wiring.
- Verify continuity, isolation, all 75 switches, and diode presence/orientation.
- Select the exact standard-ESP32 board/module from the recommended economical class in BD-1 and confirm its flash configuration; this is a future selection, not an asserted purchase.
- Confirm the USB-UART bridge or routed-UART programming, firmware-update, configuration, power, protection, and debug approach.
- Decide the RGB scope and, if pursued, select the LED type, count, layout, interface, and electrical budget.
- Decide the battery scope and, if pursued, define the battery, charging, protection, power-path, monitoring, and safety architecture.
- Build the complete resource, power, thermal, and memory budgets.
- Produce and review the GPIO allocation only after every competing resource is known.
- Define the standard-ESP32 board capability descriptor and its confirmed GPIO configuration as a Phase 1/2 artifact, without coupling it to the S1.2 layout/profile model.

Exit evidence:

- Signed-off as-built matrix record and continuity/diode test results.
- Approved standard-ESP32 board/module ordering code and flash configuration.
- Approved USB-serial and BLE/RF hardware approach.
- Approved RGB selection and budget, or an explicit decision to defer RGB.
- Approved battery decision and circuitry requirements, or an explicit decision to defer battery population while preserving a reviewed future path.
- Reviewed power/TDP, memory, and I/O budgets.
- Reviewed GPIO allocation with no conflicts.
- Reviewed standard-ESP32 board capability descriptor matching the approved hardware and GPIO allocation.

#### Phase 2 — Pre-firmware verification gate

Status: **GATED / not started**

This is a mandatory stop/go review. No firmware, framework-specific configuration, or executable prototype work begins before it passes.

The verification gate is unchanged in intent: as-built matrix continuity, diode orientation, and confirmed GPIO mapping remain mandatory before firmware work.

The gate passes only when all of the following are true:

1. The exact standard-ESP32 board/module and flash configuration are confirmed.
2. The physical 75-key matrix wiring and diode orientation are documented and electrically verified.
3. The GPIO allocation is complete, reviewed, and consistent with device, boot/strapping, flash, UART0, debug, RGB, power, and expansion constraints.
4. The USB-serial programming/configuration path through the USB-UART bridge or routed UART is confirmed. USB HID is explicitly not part of this 75-key gate.
5. The BLE/RF implementation and antenna constraints are confirmed.
6. RGB hardware and its worst-case current/thermal limits are confirmed, or RGB implementation is explicitly deferred.
7. Battery circuitry is confirmed, or battery implementation is explicitly deferred with defined interface constraints.
8. Persistence capacity, memory headroom, and power-loss recovery requirements are bounded.
9. BLE pairing, bonding, reconnect, wake, latency, rollover, debounce, and stuck-key/duplicate-event acceptance targets are converted into testable decisions.
10. The hardware requirements and product specification are updated to replace every implementation-blocking **TBD** with approved facts.

If any item fails, work returns to Phase 1. Passing this gate authorizes planning for the standard-ESP32 implementation only; C3/S2/S3 firmware remains deferred.

#### Phase 3 — Core input implementation

Status: **GATED behind Phase 2**

Planned outcomes:

- Bring up the verified matrix and establish correct behavior for all 75 keys.
- Implement key processing, debounce, key assignments, shortcuts, macros, and profile selection.
- Establish persistent settings with versioning, defaults, integrity handling, and power-loss recovery.
- Verify matrix correctness and storage behavior before transport integration.

Exit criteria: all approved core-input and persistence tests pass on representative confirmed hardware.

#### Phase 4 — BLE transport + USB-serial configuration integration

Status: **GATED behind Phases 2 and 3**

Planned outcomes:

- Integrate BLE HID pairing, bonding, reconnect, Keyboard reports, and Consumer-Device reports as the primary keyboard behavior.
- Integrate USB serial as the programming/update and configuration channel, including pushing profile v2 typed actions from the board-independent desktop configurator.
- Implement the approved BLE connection/reset state model and prevent duplicate or stuck key events.
- Keep desktop-to-device configuration transport separable from BLE HID output and from board capability/GPIO configuration.
- Drop USB HID integration from the 75-key standard-ESP32 scope. USB HID remains only a deferred capability for an ESP32-S2-class board entry; it is not authorized for implementation by this roadmap.

Exit criteria: BLE HID and USB-serial configuration/update tests pass across the approved host compatibility set, including BLE transition and reset recovery tests.

#### Phase 5 — RGB and power integration

Status: **GATED behind confirmed RGB hardware and Phase 4**

Planned outcomes:

- Integrate the selected RGB hardware and approved lighting controls.
- Enforce USB-supply and thermal power limits.
- Validate that lighting activity does not degrade key scanning or transport reliability.
- If battery circuitry has been approved for this release, integrate charging, monitoring, low-power behavior, and battery-specific RGB limits.

Exit criteria: functional, electrical, power, thermal, and interference tests pass for all included power modes.

#### Phase 6 — System verification and release readiness

Status: **GATED behind prior applicable phases**

Planned outcomes:

- Run the product acceptance suite for all 75 keys, customization, profiles, persistence, USB serial, BLE HID, BLE transitions/resets, RGB, and applicable battery behavior.
- Exercise resets, unexpected power removal, connection churn, long-duration operation, and recovery paths.
- Complete host compatibility, power, thermal, and wireless validation.
- Resolve or explicitly defer all release-blocking defects and documentation gaps.

Exit criteria: every in-scope requirement has traceable passing evidence, all deferrals are approved, and release documentation reflects the tested hardware.

## 3. Current blockers and open decisions

- Physical matrix completion and verified wiring.
- Diode orientation.
- Exact standard-ESP32 board/module (recommended class: ESP32-WROOM-32 DevKit) and flash capacity.
- GPIO allocation and complete I/O budget.
- USB-UART bridge or routed-UART programming/configuration path and USB power details.
- RGB type, count, topology, and power budget.
- Battery circuitry and runtime/safety targets.
- Persistence sizing and configuration limits.
- BLE host compatibility set, latency, rollover, debounce, wake, pairing, reconnect, and reset-transition acceptance targets.
- Board-capability descriptor and the eventual simulated-device naming/behavior cleanup; the latter requires a separate code milestone and is not part of BD-2.

All are **TBD**. They are inputs to Phase 1 and must not be guessed to accelerate firmware work.
