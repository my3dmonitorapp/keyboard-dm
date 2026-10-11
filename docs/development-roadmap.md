# Keyboard75 Development Roadmap

Date: 2026-10-11  
Target MCU: ESP32-S3 only

## 1. Roadmap rules

- The ESP32-S3 is the sole target MCU and supersedes the earlier standard-ESP32 plan.
- Work proceeds in two parallel tracks: Track A for the desktop application and Track B for ESP32-S3 firmware.
- The tracks share product decisions, but Track A can use the deterministic simulated device while Track B remains hardware-gated.
- No firmware work may begin until the pre-firmware verification gate in Phase 2 passes.
- GPIO allocation, exact matrix wiring, diode orientation, RGB hardware, and battery circuitry remain **TBD** until confirmed by evidence.
- A phase may begin only when its listed entry gate is satisfied; schedule dates beyond Phase 0 are intentionally **TBD**.

## 2. Parallel tracks

### Track A — Desktop application

Status: **S1 complete (2026-10-11)**

Track A runs independently against a simulated ESP32-S3 device until verified hardware is available. The provisional layout remains clearly labeled and does not define final key placement or firmware wiring.

Milestone S1 delivered:

- A Python and PySide6 desktop application launched with `python -m desktop_app`.
- A visibly **PROVISIONAL** 5 × 15 editor using stable IDs K01–K75 and default `NONE` assignments.
- Selection and editing for every key through the graphical inspector.
- Version 1 JSON profile creation, validation, save, and load for all 75 assignments.
- A deterministic simulated ESP32-S3 device with connect/disconnect behavior, BLE default transport, and automatic USB preference when a host is connected.
- GUI integration for device state, transport state, and sending assignments to the simulator.
- A real offscreen smoke entrypoint (`python -m desktop_app --smoke`) covering the window, K07 assignment, profile round-trip, USB preference, and simulated device state.
- Automated tests for the layout model, GUI construction, profiles, simulated device, and end-to-end smoke flow.

Future Track A milestones remain **TBD** and must not assume unresolved physical layout, wiring, or GPIO decisions.

### Track B — ESP32-S3 firmware

Status: **BLOCKED until the Phase 2 hardware verification gate passes**

Track B must not begin firmware, framework-specific configuration, or executable firmware prototypes until matrix continuity, diode orientation, and GPIO allocation have been verified and the complete Phase 2 gate below passes.

#### Phase 0 — Product and architecture planning

Status: **Complete with the 2026-10-11 documentation baseline**

Objectives:

- Confirm the ESP32-S3 as the only target MCU.
- Define the product capabilities and acceptance direction.
- Record verified MCU capabilities and hardware constraints.
- Size candidate 75-key matrix topologies without assigning pins.
- Identify every decision that gates later work.

Deliverables:

- `docs/product-specification.md` v1.0
- `docs/hardware-requirements.md`
- `docs/development-roadmap.md`
- `docs/changelog.md`

Exit condition: the four planning documents exist, agree on the ESP32-S3 decision, contain no pinmap or GPIO assumptions, and identify unresolved hardware items as **TBD**.

#### Phase 1 — Physical hardware discovery and decisions

Status: **GATED / not started**

Entry gate: Phase 0 approved.

Required work:

- Finish and inspect the physical key matrix.
- Record the as-built row/column topology and exact wiring.
- Verify continuity, isolation, all 75 switches, and diode presence/orientation.
- Select the exact ESP32-S3 chip or module and flash/PSRAM configuration.
- Select the USB connector, protection, power, programming, and debug approach.
- Select RGB LED type, count, layout, interface, and electrical budget.
- Decide the battery scope and, if pursued, define the battery, charging, protection, power-path, monitoring, and safety architecture.
- Build the complete resource, power, thermal, and memory budgets.
- Produce and review the GPIO allocation only after every competing resource is known.

Exit evidence:

- Signed-off as-built matrix record and continuity/diode test results.
- Approved ESP32-S3 ordering code.
- Approved USB and BLE/RF hardware approach.
- Approved RGB selection and budget.
- Approved battery decision and circuitry requirements, or an explicit decision to defer battery population while preserving a reviewed future path.
- Reviewed power/TDP, memory, and I/O budgets.
- Reviewed GPIO allocation with no conflicts.

#### Phase 2 — Pre-firmware verification gate

Status: **GATED / not started**

This is a mandatory stop/go review. No firmware, framework-specific configuration, or executable prototype work begins before it passes.

The gate passes only when all of the following are true:

1. The exact ESP32-S3 part/module and memory configuration are confirmed.
2. The physical 75-key matrix wiring and diode orientation are documented and electrically verified.
3. The GPIO allocation is complete, reviewed, and consistent with device, boot, memory, USB, debug, RGB, and power constraints.
4. The native USB hardware path and host-presence strategy are confirmed.
5. The BLE/RF implementation and antenna constraints are confirmed.
6. RGB hardware and its worst-case current/thermal limits are confirmed.
7. Battery circuitry is confirmed, or battery implementation is explicitly deferred with defined interface constraints.
8. Persistence capacity, memory headroom, and power-loss recovery requirements are bounded.
9. USB-preferred transport behavior and unresolved product acceptance targets are converted into testable decisions.
10. The hardware requirements and product specification are updated to replace every implementation-blocking **TBD** with approved facts.

If any item fails, work returns to Phase 1. Passing this gate authorizes planning for implementation; it does not change the ESP32-S3-only scope.

#### Phase 3 — Core input implementation

Status: **GATED behind Phase 2**

Planned outcomes:

- Bring up the verified matrix and establish correct behavior for all 75 keys.
- Implement key processing, debounce, key assignments, shortcuts, macros, and profile selection.
- Establish persistent settings with versioning, defaults, integrity handling, and power-loss recovery.
- Verify matrix correctness and storage behavior before transport integration.

Exit criteria: all approved core-input and persistence tests pass on representative confirmed hardware.

#### Phase 4 — USB and BLE transport integration

Status: **GATED behind Phases 2 and 3**

Planned outcomes:

- Integrate native USB HID keyboard behavior.
- Integrate BLE HID pairing, bonding, reconnect, and keyboard behavior.
- Implement the approved mode-selection state model with USB preferred when connected to a host.
- Prevent duplicate and stuck key events during transport changes.

Exit criteria: USB, BLE, and transport-transition tests pass across the approved host compatibility set.

#### Phase 5 — RGB and power integration

Status: **GATED behind confirmed RGB hardware and Phase 4**

Planned outcomes:

- Integrate the selected RGB hardware and approved lighting controls.
- Enforce USB and thermal power limits.
- Validate that lighting activity does not degrade key scanning or transport reliability.
- If battery circuitry has been approved for this release, integrate charging, monitoring, low-power behavior, and battery-specific RGB limits.

Exit criteria: functional, electrical, power, thermal, and interference tests pass for all included power modes.

#### Phase 6 — System verification and release readiness

Status: **GATED behind prior applicable phases**

Planned outcomes:

- Run the product acceptance suite for all 75 keys, customization, profiles, persistence, USB, BLE, switching, RGB, and applicable battery behavior.
- Exercise resets, unexpected power removal, connection churn, long-duration operation, and recovery paths.
- Complete host compatibility, power, thermal, and wireless validation.
- Resolve or explicitly defer all release-blocking defects and documentation gaps.

Exit criteria: every in-scope requirement has traceable passing evidence, all deferrals are approved, and release documentation reflects the tested hardware.

## 3. Current blockers and open decisions

- Physical matrix completion and verified wiring.
- Diode orientation.
- Exact ESP32-S3 variant/module and flash/PSRAM capacity.
- GPIO allocation and complete I/O budget.
- USB physical implementation and host-detection behavior.
- RGB type, count, topology, and power budget.
- Battery circuitry and runtime/safety targets.
- Persistence sizing and configuration limits.
- Host compatibility set, latency, rollover, debounce, wake, reconnect, and transition acceptance targets.

All are **TBD**. They are inputs to Phase 1 and must not be guessed to accelerate firmware work.
