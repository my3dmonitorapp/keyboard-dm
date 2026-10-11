# Keyboard75 Hardware Requirements

Date: 2026-10-11  
Status: Phase 0 planning baseline  
Target MCU: ESP32-S3 only

## 1. Purpose and constraints

This document records verified ESP32-S3 capabilities, system-level hardware requirements, sizing analysis, and decisions that must be confirmed before implementation. It does not define a schematic, pinmap, PCB, or firmware design.

The physical key matrix is still being soldered. Every GPIO assignment, exact matrix connection, and diode orientation is therefore **TBD**. The ESP32-S3 replaces the previously planned standard ESP32 and is the only MCU in scope.

## 2. Verified ESP32-S3 facts

| Capability | Verified fact | Relevance to Keyboard75 |
| --- | --- | --- |
| Native USB | The ESP32-S3 USB device stack supports one USB Full-Speed (USB 1.1) peripheral with an internal PHY and supports the HID device class. | Supports native wired keyboard operation without making any board-level pin assignment in this document. |
| Bluetooth | ESP32-S3 supports Bluetooth 5.0 LE. Espressif documents BLE controller and host-stack support for the ESP32-S3; Bluetooth Classic is not supported on this target. | Supports the required BLE HID transport; the product must use BLE, not Bluetooth Classic. |
| Flash | ESP32-S3 variants and modules are available with differing embedded or module-integrated flash capacities and interfaces. Examples in Espressif's current documentation span multiple capacities, including WROOM module options up to 32 MB. | The exact part and flash capacity must be selected after storage, packaging, and availability requirements are known. |
| PSRAM | ESP32-S3 variants/modules offer optional PSRAM in differing capacities and interfaces; Espressif documents options including 2 MB, 8 MB, and 16 MB at the chip-family level. | PSRAM is optional for this product until measured memory needs justify it. Exact availability depends on the selected part/module. |
| On-chip memory | The ESP32-S3 family provides 512 KB SRAM and 384 KB ROM. | Establishes the baseline before any optional PSRAM decision; no application allocation is assumed here. |

### Sources

Primary Espressif sources, accessed 2026-10-11:

1. [ESP32-S3 Series Datasheet](https://documentation.espressif.com/esp32_s3_datasheet_en.pdf) — family features, internal memory, USB OTG, Bluetooth LE, and flash/PSRAM variant table.
2. [ESP32-S3 USB Device Stack](https://docs.espressif.com/projects/esp-usb/en/latest/esp32s3/usb_device.html) — USB Full-Speed (USB 1.1), internal PHY, device mode, and HID class support.
3. [ESP32-S3 Bluetooth LE overview](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/ble/overview.html) — Bluetooth 5.0 LE and supported host stacks; notes that ESP32-S3 does not support Bluetooth Classic.
4. [ESP32-S3-WROOM-1 / WROOM-1U Datasheet](https://documentation.espressif.com/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf) — representative module flash and PSRAM combinations.
5. [ESP32-S3-WROOM-2 Datasheet](https://documentation.espressif.com/esp32-s3-wroom-2_datasheet_en.html) — representative higher-capacity module options up to 32 MB flash and 16 MB PSRAM.
6. [ESP32-S3 Non-Volatile Storage Library](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/storage/nvs_flash.html) — flash-backed key-value storage behavior and built-in wear levelling.

These facts establish capability, not a selected ESP32-S3 ordering code. The exact chip/module, package, memory configuration, and resulting usable I/O remain **TBD**.

## 3. MCU and memory requirements

- The design shall use an ESP32-S3; no standard ESP32 fallback or second target is planned.
- The selected ESP32-S3 part or module shall expose native USB device capability and Bluetooth LE capability required by the product.
- The exact ESP32-S3 ordering code, module versus bare-chip choice, antenna option, flash capacity, and PSRAM capacity are **TBD**.
- The memory selection shall be based on a documented budget covering USB HID, BLE HID, matrix state, user profiles, macros, RGB state/effects, update needs, diagnostics, and operating margin.
- PSRAM shall not be treated as required until the memory budget demonstrates that need.
- Hardware reserved resources, strapping constraints, flash/PSRAM connections, USB, debugging, RGB, battery functions, and expansion needs must all be considered before any matrix line is assigned.

## 4. Key matrix and I/O-budget analysis

### 4.1 Fixed requirements

- The matrix shall support exactly 75 populated mechanical-key positions.
- Every switch shall be diode protected.
- Diode orientation is **TBD** and must be documented from the as-built matrix before electrical or firmware design proceeds.
- Exact row/column wiring, connector mapping, continuity results, and all GPIO assignments are **TBD**.

### 4.2 Candidate matrix sizing

For a direct scanned matrix with `R` row lines and `C` column lines:

- position capacity = `R × C`
- matrix I/O demand = `R + C`

Candidate shapes are planning examples only:

| Candidate | Capacity arithmetic | Matrix lines | Unused positions | Planning observation |
| --- | ---: | ---: | ---: | --- |
| 15 × 5 | 15 × 5 = 75 | 15 + 5 = 20 | 0 | Exact capacity; orientation can be transposed without changing line count. |
| 5 × 15 | 5 × 15 = 75 | 5 + 15 = 20 | 0 | Electrically equivalent sizing to 15 × 5; physical wiring may favor one orientation. |
| 13 × 6 | 13 × 6 = 78 | 13 + 6 = 19 | 3 | Uses one fewer matrix line but introduces unused intersections. |
| 10 × 8 | 10 × 8 = 80 | 10 + 8 = 18 | 5 | Uses fewer matrix lines but may be less natural for the physical layout. |

No candidate is selected here. The as-built wiring and continuity results determine the real topology; it must not be inferred from key count alone.

### 4.3 I/O budget gate

The provisional matrix demand is therefore 18–20 signal lines for the examples above. This is not a statement that 18–20 currently unallocated pins are available.

Before selecting a matrix topology or MCU/module variant, the hardware review shall create an I/O budget with separate entries for:

- matrix row lines: **TBD**;
- matrix column lines: **TBD**;
- native USB resources: **TBD at board level**;
- RGB data/control resources: **TBD**;
- battery charging, power-state, enable, and monitoring resources: **TBD**;
- debugging, boot, manufacturing test, and recovery resources: **TBD**;
- reserved or unavailable resources created by the selected flash/PSRAM/module configuration: **TBD**;
- desired expansion margin: **TBD**.

The gate passes only when the selected hardware exposes enough suitable, non-conflicting resources for every confirmed function with documented margin. If it does not, topology changes or an I/O-expansion strategy require a separate hardware decision.

## 5. USB and BLE requirements

### 5.1 USB

- The board shall expose the ESP32-S3 native USB device function to a host through a standards-compliant physical USB implementation.
- The device shall support USB HID keyboard operation.
- Connector type, protection, signal routing, power handling, host-presence sensing, and board-level USB details are **TBD**.
- The final design shall account for the ESP32-S3's shared internal USB PHY behavior and the chosen programming/debug approach before schematic approval.

### 5.2 Bluetooth LE

- The selected ESP32-S3 implementation shall support BLE HID keyboard operation and secure host pairing/bonding.
- Antenna implementation, RF layout, enclosure effects, regulatory scope, range target, bonded-host capacity, and pairing/reset user experience are **TBD**.
- Bluetooth Classic shall not be required.

### 5.3 Coexistence and mode selection

Here, coexistence means that one product supports both transports; it does not imply that key input is sent concurrently over both.

- USB shall be the preferred active keyboard transport whenever a valid USB host connection is detected.
- BLE shall provide keyboard transport when USB host operation is unavailable.
- Transitions shall avoid duplicate or stuck key states.
- Required behavior for an existing BLE link while USB is active—disconnect, remain connected without input, or another defined state—is **TBD**.
- Host-detection criteria, transition timing, manual override behavior, wake behavior, and failure fallback are **TBD**.
- Validation shall cover power-only USB attachment, USB host attach/detach, BLE connect/disconnect, resets during transitions, and simultaneous availability of both transports.

## 6. RGB lighting requirements

- RGB lighting shall be configurable and shall not prevent reliable keyboard input.
- LED type, quantity, placement, protocol, voltage, data topology, and whether lighting is per-key or zoned are **TBD**.
- The hardware design shall provide a documented peak and typical current budget before LED hardware is approved.
- Brightness limiting and a fully-off state shall be supported to protect the USB and future battery power budgets.
- Logic-level compatibility, signal integrity, decoupling, inrush behavior, thermal effect, and update-rate requirements shall be verified for the selected LEDs.
- RGB power behavior shall be defined separately for USB and future battery operation.
- No RGB control resource or connection is allocated in this phase.

## 7. Persistence requirements

- User configuration shall be stored in non-volatile flash accessible to the ESP32-S3; no external configuration storage is assumed.
- The storage budget shall cover key assignments, macros, shortcuts, profiles, RGB preferences, transport preferences, schema metadata, and integrity metadata.
- Writes shall be designed to tolerate resets and unexpected power loss without losing the last known-good configuration.
- Storage shall use wear-aware update behavior. Espressif's NVS is a candidate capability because it is flash-backed and includes wear levelling, but the final storage design is a later implementation decision.
- Factory defaults, schema migration, corruption detection/recovery, write frequency, partition size, and user-reset behavior are **TBD**.
- BLE bonding data shall be included in the storage and recovery budget even if it is managed separately from user profiles.

## 8. Battery requirements

Battery support is required as a future capability, but no battery circuit is finalized and battery operation is not cleared for implementation.

The following are all **TBD**:

- cell chemistry, count, capacity, and form factor;
- charger, protection, power-path, and regulation architecture;
- connector and serviceability;
- USB charging/current limits and behavior while operating;
- fuel gauging or voltage monitoring;
- low-battery indication and shutdown thresholds;
- sleep/wake strategy and wireless runtime target;
- RGB limits under battery power;
- transport behavior while charging;
- thermal, fault, safety, shipping, and certification requirements.

The hardware must not claim battery compatibility until these items are reviewed together and verified on the final electrical design.

## 9. TDP / power and thermal design requirements

No numeric thermal design power or complete system power budget can be assigned until the ESP32-S3 variant, RGB hardware, USB implementation, and battery circuitry are selected. Therefore the system TDP/power target is **TBD**.

Before hardware approval, a power and thermal design record shall include:

- ESP32-S3 active, BLE, USB, idle, and sleep consumption assumptions tied to the chosen part/module;
- RGB typical, configured-maximum, and electrical worst-case load;
- USB source/negotiated current limits and startup/inrush behavior;
- regulator and power-path losses;
- future battery charge and discharge loads;
- enclosure thermal assumptions and measured component temperatures;
- operating margin and protective limits.

USB-powered and future battery-powered cases shall be assessed separately. Measurements on representative hardware are required before limits are finalized.

## 10. Open items and required evidence

| Open item | Required evidence to close it |
| --- | --- |
| ESP32-S3 part/module and memory | Approved ordering code plus memory, availability, antenna, and resource rationale. |
| Matrix topology and wiring | As-built row/column map, continuity test, switch count, and documented diode orientation. |
| GPIO allocation | Reviewed resource budget after all hardware consumers and device constraints are known. |
| USB implementation | Reviewed connector, protection, routing, power, host-detection, programming, and debug plan. |
| BLE/RF design | Antenna/layout decision and validation plan including enclosure effects. |
| RGB hardware | Part number, count, topology, voltage/interface, current/thermal budget, and validation plan. |
| Persistence sizing | Configuration schema estimate, endurance/write assumptions, recovery behavior, and partition budget. |
| Battery circuitry | Complete battery/charger/protection/power-path design with safety and runtime requirements. |
| TDP/power targets | Mode-by-mode budget and representative measurements with margin. |

Until these items are closed, all related pin-level fields remain explicit **TBD**.
