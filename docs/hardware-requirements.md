# Keyboard DM Hardware Requirements

Date: 2026-10-11  
Status: Phase 0 planning baseline  
Primary target MCU: standard ESP32 (ESP32-WROOM-32 class, part **TBD**)

## 1. Purpose and constraints

This document records verified standard-ESP32 capabilities, system-level hardware requirements, sizing analysis, and decisions that must be confirmed before implementation. It does not define a schematic, pinmap, PCB, or firmware design.

The physical key matrix is still being soldered. Every GPIO assignment, exact matrix connection, and diode orientation is therefore **TBD**. Per [BD-1](hardware-decision-2026-10-11-bt-first.md), the standard ESP32 is the primary target and supersedes the ESP32-S3-only baseline. No board has been purchased or asserted selected.

## 2. Verified standard-ESP32 facts

| Capability | Verified fact | Relevance to Keyboard DM |
| --- | --- | --- |
| GPIO count | The classic ESP32 exposes 34 physical GPIOs, numbered within GPIO0–GPIO39; the usable subset depends on the module and board. | Establishes the I/O ceiling before board selection or allocation. |
| Reserved flash pins | **GPIO6–GPIO11 are wired to SPI flash** on ESP32-WROOM-32 modules and must not be reused. | These pins are excluded from the matrix budget. |
| Input-only pins | **GPIO34–GPIO39 are input-only** and have no internal pull-up or pull-down resistors. | They may be used for read/scan column lines with appropriate external circuitry, but not driven row lines. |
| Strapping pins | **GPIO0, GPIO2, GPIO5, GPIO12, and GPIO15** are boot/strapping pins and must be avoided or used only after their boot-time behavior is reviewed. | They remain deprioritized in the provisional safe-pin budget. |
| UART0 | **GPIO1 (TXD0) and GPIO3 (RXD0)** are UART0 pins used for flashing and logging. | They are reserved for the intended USB-serial programming/configuration path, not the matrix. |
| USB | The standard ESP32 has **no native USB device/OTG**. Native USB HID is available on ESP32-S2/S3-class targets, not the standard ESP32; DevKit USB connectivity uses a USB-UART bridge or routed UART. | USB HID is not a target capability for the 75-key keyboard. USB serial remains available for programming, updates, and configuration. |
| Bluetooth | The standard ESP32 supports Bluetooth 5.0 (Classic + BLE) on the same die. ESP-IDF's official `ble_hid_device_demo` lists ESP32 as a supported target and implements Keyboard, Consumer-Device, Mouse, and Vendor reports. | Confirms BLE HID support for the primary keyboard transport. |
| Persistence | ESP32 NVS is flash-backed and provides wear levelling. | Supports persistent assignments, shortcuts, modifiers, macros, layers, profiles, and related settings. |

### Sources

Sources accessed 2026-10-11, as recorded by BD-1:

1. [ESP-IDF `ble_hid_device_demo` README](https://github.com/espressif/esp-idf/tree/master/examples/bluetooth/bluedroid/ble/ble_hid_device_demo) — ESP32 supported target and Keyboard, Consumer-Device, Mouse, and Vendor reports.
2. [ESP-IDF ESP32 Bluetooth HID Device API](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_hidd.html) — HID device support and keyboard report definitions.
3. [ESP32 Series Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf) and community standard-ESP32 pinout references from [Flux](https://www.flux.ai/p/blog/esp32-pinout-everything-you-need-to-know), [StudioPieters](https://www.studiopieters.nl/esp32-pinout/), [Wevolver](https://www.wevolver.com/article/esp32-pinout), [Random Nerd Tutorials](https://randomnerdtutorials.com/esp32-pinout-reference-gpios/), and [OceanLabz](https://www.oceanlabz.in/esp32-pinout-gpio-pins/) — GPIO count and flash, input-only, strapping, and UART0 constraints.
4. [ESP32 USB HID reference](https://industrialmonitordirect.com/blogs/news/esp32-usb-hid) — standard ESP32/WROOM/WROVER lack native USB OTG; native USB HID is limited to ESP32-S2/S3.
5. [ESP-IDF ESP32 Non-Volatile Storage Library](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/storage/nvs_flash.html) — flash-backed key-value storage with wear levelling.

These facts establish capability and an I/O budget, not a selected ordering code or pinmap. The exact board/module, flash capacity, and resulting usable I/O remain **TBD**.

## 3. MCU and memory requirements

- The primary target shall be a standard ESP32, preferably an ESP32-WROOM-32 DevKit-class board or a similar economical board with an on-board USB-UART bridge. The exact board/module and ordering code are **TBD**; this class recommendation is not a purchase or selection.
- A 4 MB flash configuration is the recommended economical class, not a finalized capacity. Exact flash capacity, antenna option, board form factor, and module-versus-board choice are **TBD**.
- The selected standard-ESP32 implementation shall support BLE HID and expose USB serial through its USB-UART bridge or a routed UART.
- The memory selection shall be based on a documented budget covering BLE HID, matrix state, typed actions, user profiles, macros, layers, RGB state/effects if included, NVS, update needs, diagnostics, and operating margin.
- External PSRAM is not assumed and shall not be treated as required unless the memory budget demonstrates that need and a compatible selected module provides it.
- Reserved resources, strapping constraints, flash connections, UART0/USB-serial, debugging, RGB, battery functions, and expansion needs must all be considered before any matrix line is assigned.

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

The provisional matrix demand is therefore 18–20 signal lines for the examples above. After excluding GPIO6–GPIO11, deprioritizing the five strapping pins, and reserving GPIO1/GPIO3 for UART0, BD-1 estimates approximately 21 safe bidirectional pins plus six input-only pins, or about **27 usable signal lines** before RGB, battery, expansion, and RF/board constraints are counted. This is a feasibility estimate, not an allocation.

**Feasibility verdict:** a direct-scan 18–20-line matrix in the 15 × 5, 5 × 15, 13 × 6, or 10 × 8 candidate shapes fits within the approximate 27-line standard-ESP32 budget. Driven rows must use suitable bidirectional/output-capable GPIOs; read columns may use input-only GPIO34–GPIO39 with appropriate external circuitry. The as-built wiring determines which orientation and topology apply. **No pins are assigned here.**

Before selecting a matrix topology or MCU/module variant, the hardware review shall create an I/O budget with separate entries for:

- matrix row lines: **TBD**;
- matrix column lines: **TBD**;
- UART0 and USB-UART bridge resources for programming/configuration: **TBD at board level**;
- RGB data/control resources: **TBD**;
- battery charging, power-state, enable, and monitoring resources: **TBD**;
- debugging, boot, manufacturing test, and recovery resources: **TBD**;
- reserved or unavailable resources created by the selected flash/module/board configuration: **TBD**;
- desired expansion margin: **TBD**.

The gate passes only when the selected hardware exposes enough suitable, non-conflicting resources for every confirmed function with documented margin. If the as-built matrix or other confirmed functions exceed that budget, an I²C GPIO expander such as the MCP23017 class is a documented contingency. It is not an initial requirement or assumed design choice, and selecting one would require a later hardware decision.

## 5. USB and BLE requirements

### 5.1 USB serial

- The standard-ESP32 board shall expose USB serial through an on-board USB-UART bridge or a routed UART.
- USB serial shall be the programming, flashing, firmware-update, diagnostic, and configuration interface.
- USB HID is not a target capability or requirement for the 75-key keyboard on the standard ESP32, which has no native USB device/OTG support.
- Connector type, USB-UART bridge, protection, power handling, routing, and board-level details are **TBD** pending exact board/module selection.

### 5.2 Bluetooth LE

- BLE HID shall be the primary keyboard transport on the selected standard-ESP32 implementation, with secure host pairing/bonding and defined reconnect behavior.
- Antenna implementation, RF layout, enclosure effects, regulatory scope, range target, bonded-host capacity, and pairing/reset user experience are **TBD**.
- Bluetooth Classic HID is a possible future option but is not required.

### 5.3 Input and configuration-channel behavior

- BLE is the keyboard input transport. USB serial is used for configuration and updates only; there is no USB-versus-BLE input-transport priority for the 75-key target.
- BLE connect/disconnect and device-reset state transitions shall avoid duplicate or stuck key states.
- Pairing, reconnect, wake, reset, configuration-session, and failure-recovery behavior are **TBD**.
- Validation shall cover BLE connect/disconnect, resets during key activity and configuration, USB-serial attach/detach, and recovery from interrupted configuration without treating USB serial as an HID path.

## 6. RGB lighting requirements

- If RGB hardware is included, its lighting shall be configurable and shall not prevent reliable keyboard input.
- LED type, quantity, placement, protocol, voltage, data topology, and whether lighting is per-key or zoned are **TBD**.
- The hardware design shall provide a documented peak and typical current budget before LED hardware is approved.
- Brightness limiting and a fully-off state shall be supported to protect the USB and future battery power budgets.
- Logic-level compatibility, signal integrity, decoupling, inrush behavior, thermal effect, and update-rate requirements shall be verified for the selected LEDs.
- RGB power behavior shall be defined separately for USB and future battery operation.
- No RGB control resource or connection is allocated in this phase.

## 7. Persistence requirements

- User configuration shall be stored in non-volatile flash/NVS accessible to the standard ESP32; no external configuration storage is assumed.
- The storage budget shall cover key assignments, macros, shortcuts, modifiers, layers, profiles, RGB preferences if applicable, schema metadata, and integrity metadata.
- Writes shall be designed to tolerate resets and unexpected power loss without losing the last known-good configuration.
- Storage shall use wear-aware update behavior. Espressif's NVS is a candidate capability because it is flash-backed and includes wear levelling, but the final storage design is a later implementation decision.
- Factory defaults, schema migration, corruption detection/recovery, write frequency, partition size, and user-reset behavior are **TBD**.
- BLE bonding data shall be included in the storage and recovery budget even if it is managed separately from user profiles.

## 8. Battery requirements

Battery power is optional and deferred. No battery circuit is finalized, and battery operation is not cleared for implementation.

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

No numeric thermal design power or complete system power budget can be assigned until the standard-ESP32 board/module, RGB hardware, USB-UART/power implementation, and battery scope/circuitry are selected. Therefore the system TDP/power target is **TBD**.

Before hardware approval, a power and thermal design record shall include:

- standard-ESP32 active, BLE, USB-serial-connected, idle, and sleep consumption assumptions tied to the chosen board/module;
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
| Standard-ESP32 board/module (class: WROOM-32 DevKit) and memory | Approved ordering code plus flash, availability, antenna, USB-UART, and resource rationale. |
| Matrix topology and wiring | As-built row/column map, continuity test, switch count, and documented diode orientation. |
| GPIO allocation | Reviewed resource budget after all hardware consumers and device constraints are known. |
| USB-serial implementation | Reviewed USB-UART bridge or routed-UART path, connector, protection, routing, power, programming, configuration, and debug plan. |
| BLE/RF design | Antenna/layout decision and validation plan including enclosure effects. |
| RGB hardware | Part number, count, topology, voltage/interface, current/thermal budget, and validation plan. |
| Persistence sizing | Configuration schema estimate, endurance/write assumptions, recovery behavior, and partition budget. |
| Battery circuitry | Complete battery/charger/protection/power-path design with safety and runtime requirements. |
| TDP/power targets | Mode-by-mode budget and representative measurements with margin. |

Until these items are closed, all related pin-level fields remain explicit **TBD**.
