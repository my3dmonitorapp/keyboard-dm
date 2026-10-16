# Keyboard75 Hardware Decision: Bluetooth-First, Standard ESP32

Date: 2026-10-11
Status: **Supersedes the earlier "ESP32-S3 sole target / native-USB-HID-required" baseline**
Decision owner: Daniele
Scope: Documentation and architecture only. No firmware, no pin assignments, no purchases, no flashing.

## 1. Decision

The handmade 75-key keyboard **does not need wired USB HID**. Bluetooth keyboard connectivity is sufficient. The primary hardware target is therefore changed **from the ESP32-S3 back to a standard ESP32**, preferably **ESP32-WROOM-32** or a similar suitable economical development board.

Consequences that reverse the previous baseline:

- **Remove** native USB HID as a mandatory capability for the 75-key keyboard. The standard ESP32 has no native USB device/OTG, so USB HID is not available on this target and must not be a requirement.
- **Keep** USB serial as the programming, firmware-update, and configuration interface.
- **Bluetooth LE (BLE) HID** is the primary keyboard transport.
- The desktop configurator remains **board-independent**; other ESP32 variants are supported later through an extensible board-capability system, not by implementing firmware for every model now.

## 2. Updated hardware requirements (summary)

- 75 mechanical keys through a diode-protected switch matrix (matrix still being soldered).
- **BLE HID** keyboard output (primary transport). Bluetooth Classic HID is a possible future option, not required.
- **USB serial** for programming, flashing, firmware updates, and receiving configuration from the desktop.
- **USB power** when connected to a computer or USB supply.
- **Battery power** optional for fully wireless use; charging and power-management circuitry to be designed separately (deferred, TBD).
- **Persistent configuration in ESP32 flash / NVS**: assignments, shortcuts, modifiers, macros, layers.
- **RGB** only if supported by the eventual LED hardware (TBD).
- Matrix dimensions, diode orientation, and GPIO allocation **remain unconfirmed (TBD)**.
- **No** GPIO pins are assigned in this document.

## 3. Verified standard-ESP32 facts (accessed 2026-10-11)

| Capability | Verified fact | Relevance to Keyboard DM |
| --- | --- | --- |
| GPIO count | The classic ESP32 exposes 34 physical GPIOs (numbered 0–39). On WROOM-32 modules, a subset is usable. | Sets the I/O ceiling for the 75-key matrix before any allocation. |
| Reserved flash pins | **GPIO6–GPIO11 are wired to the module's SPI flash** and must not be reused. | Reduces the usable pin budget; must be excluded from any matrix. |
| Input-only pins | **GPIO34–GPIO39 are input-only** (cannot drive outputs; no internal pull-up/pull-down). | Usable for **read/scan (column)** lines in a scanned matrix, not for driven row lines. |
| Strapping pins | **GPIO0, GPIO2, GPIO5, GPIO12, GPIO15** are boot/strapping pins — avoid or use with care. | Reduces the "safe" bidirectional budget until their boot-time behavior is reviewed. |
| Debug UART | **GPIO1 (TXD0) / GPIO3 (RXD0)** are UART0 used for flashing and logging. | Part of the intended USB-serial configuration path; reserved for programming/config, not the matrix. |
| USB | **No native USB device / OTG on the standard ESP32.** USB connectivity is via the board's **USB-UART bridge** (e.g. CP2102/CH340) or a routed UART. | **USB HID is not possible** on this target → confirms dropping it. **USB serial** (program + config) **is** the interface. |
| Bluetooth | The standard ESP32 supports **Bluetooth 5.0 (classic + BLE)** on the same die. ESP-IDF's official **`ble_hid_device_demo`** explicitly supports **ESP32** and implements **Keyboard, Consumer-Device, Mouse, and Vendor** HID reports. ESP-IDF also offers Classic-BT HID and dual-mode `esp_hid_device`. | **BLE HID keyboard is supported on the standard ESP32** — the primary requirement is met by the official toolchain. |
| Persistence | ESP32 Non-Volatile Storage (NVS) is flash-backed with wear leveling and works on the standard ESP32. | Satisfies "persistent configuration in flash/NVS" for assignments, macros, layers. |

### Sources (accessed 2026-10-11)

1. ESP-IDF `examples/bluetooth/bluedroid/ble/ble_hid_device_demo` README — supported targets include **ESP32**; reports: Keyboard, Consumer Devices, Mouse, Vendor.
2. ESP-IDF Bluetooth HID Device/Host API reference (esp32) — `esp_hid_device` (Classic or LE HID), keyboard class definitions.
3. Standard-ESP32 pinout references (flux.ai, studopieters.nl, wevolver.com, randomnerdtutorials.com, oceanlabz.in) — 34 GPIOs; GPIO6–11 flash-reserved; GPIO34–39 input-only; GPIO0/2/5/12/15 strapping; GPIO1/3 UART0.
4. ESP32 USB HID reference (industrialmonitordirect.com) — original ESP32 / WROOM / WROVER **lack native USB OTG**; native USB HID is limited to ESP32-S2/S3.

These facts establish capability and the I/O budget; they do **not** select an ordering code or assign pins. The exact module and usable pins remain **TBD** pending board selection and the as-built matrix.

## 4. 75-key matrix GPIO feasibility (no pins assigned)

### 4.1 Usable-pin estimate (standard ESP32 / WROOM-32)

- Physical GPIO: 34 (0–39).
- Minus flash-reserved (6–11): **6 pins unavailable.**
- Minus strapping to avoid (0, 2, 5, 12, 15): **5 pins deprioritized.**
- Minus debug/config UART0 (1, 3): **2 reserved for programming/config.**
- Result: approximately **~21 safe bidirectional pins** plus **~6 input-only pins (34–39, usable as read/column lines)**, i.e. **~27 usable signal lines** before counting RGB, battery/charging, expansion, and the antenna/RF constraints.

> This is an estimate for feasibility, not an allocation. Strapping pins may become usable if their boot behavior is engineered around it, but that is a Phase 1 decision.

### 4.2 Matrix shapes vs. the I/O budget

| Candidate matrix | Capacity | Lines (R+C) | Fits in ~27 usable? | Notes |
| --- | ---: | ---: | --- | --- |
| 15 × 5 | 75 | 20 | **Yes (comfortable)** | Exact capacity; 15 driven rows + 5 read columns. |
| 5 × 15 | 75 | 20 | **Yes (comfortable)** | Electrically equivalent; transpose to match soldering. |
| 13 × 6 | 78 | 19 | **Yes (best headroom)** | 3 unused intersections; fewest lines. |
| 10 × 8 | 80 | 18 | **Yes (best headroom)** | Fewest lines; 5 unused intersections. |
| 17 × 5 | 85 | 22 | **Marginal** | 22 lines is near the top of the usable budget; leave margin for RGB/battery/expansion. |

**Feasibility verdict:** A standard direct-scan 75-key matrix (18–20 lines) **fits** on a standard ESP32 without an I/O expander at the common sizes (15×5, 13×6, 10×8). Rows are driven (need bidirectional/output pins); columns are read (the input-only pins 34–39 are valid column lines). The as-built row/column wiring and continuity results will fix the real topology; **no pins are assigned here.**

### 4.3 GPIO-expansion option (only if the as-built needs more)

If the physical build ends up with more than ~22–24 lines, or if RGB/battery/expansion consume the last pins, the standard, low-cost remedy is an **I²C GPIO expander** (e.g. MCP23017 family or similar) to extend the matrix lines. This is a **contingency, not a requirement**, and any such choice is a later Phase 1 decision. No expander is assumed in the initial design.

## 5. Board-independent architecture (documentation-only, to be reflected in the spec)

The configurator and firmware are organized so that **none of the following are hard-wired to one board type**:

1. **Layout & key assignments** — the board-agnostic domain model (keys, layout, the S1.2 typed actions, profile v2). Identical for every supported board.
2. **Board capabilities & GPIO configuration** — a per-board descriptor: which GPIOs exist / are reserved, matrix pinmap, RGB pin, battery/charging pins, available transports (ble / usb-hid / usb-serial). A "board capability" object; swap it per target. No pin is hard-coded into the layout or profile model.
3. **Desktop-to-device configuration transport** — the link the desktop uses to push profile/actions to the device. For the standard ESP32 this is **USB serial** (JSON/profile payload over the serial console). Defined as a pluggable transport (serial now; other transports later).
4. **Bluetooth HID keyboard output** — the on-device HID layer that turns resolved actions into HID reports (Keyboard + Consumer-Device for media). Consumes the same typed actions regardless of board.
5. **Future RGB & battery** — optional capability blocks keyed to the board descriptor and enabled only when the hardware is present/confirmed.

**Board capability matrix (planned, not implemented firmware):**

| Board | BLE HID | USB HID | USB serial config | Notes |
| --- | --- | --- | --- | --- |
| **Standard ESP32 (WROOM-32)** — **PRIMARY** | Yes | **No** (no USB OTG) | Yes | 75-key target. BLE keyboard + serial config. |
| ESP32-C3 | Yes | No | Yes | RISC-V, Bluetooth 5 BLE; serial config. |
| ESP32-S2 | No | Yes | Yes | USB HID keyboard; no Bluetooth. |
| ESP32-S3 | Yes | Yes | Yes | USB + BLE; kept as a future/secondary option, not the primary. |

Multi-board support is achieved by **adding a board capability descriptor**, not by forking the firmware or the desktop app. The **standard ESP32 is implemented first**; other variants are deferred behind the same verification gate and an extensible capability system.

## 6. Recommended economical controller (recommendation, not a purchase)

The simplest, most economical standard ESP32 suitable as the 75-key target is a **generic ESP32-WROOM-32 development board (DevKit class) with 4 MB flash**, exposing the standard DevKit pinout (~30–34 GPIOs) and an on-board **USB-UART bridge** (CP2102/CH340) for serial. This class is widely available, inexpensive, and matches the feasibility analysis above. This is a **recommendation of the economical class**, not an asserted existing purchase or selected board.

## 7. Preserved constraints

- **Do not rewrite** the working S1.2 desktop application.
- **Do not start firmware,** flash, or modify vendor reference software.
- **Preserve** the S1.2 **typed keyboard actions** and the **profile v2** format wherever possible (they are board-agnostic and remain valid for the standard-ESP32 firmware).
- **Preserve the mandatory hardware verification gate** before any firmware: actual matrix wiring, diode orientation, continuity testing, and confirmed GPIO mapping (now for the standard ESP32).

## 8. Open decisions requiring Daniele's confirmation

1. Final **board**: confirm the economical ESP32-WROOM-32 DevKit class (or name a specific board/module + flash size).
2. **Matrix topology** from the as-built hardware (row/column wiring, diode orientation, continuity).
3. **GPIO allocation** once the topology + RGB + battery + debug are all known.
4. **Battery scope**: confirm whether to proceed with a battery/charger/power-path design now or defer.
5. **RGB**: confirm LED hardware (type, count, protocol, current budget) or defer.
6. **Host compatibility set**, latency/rollover/debounce/wake/reconnect targets.

These are Phase 1 inputs and must not be guessed to accelerate firmware.

## 9. Change note

- **2026-10-11:** Primary MCU changed from ESP32-S3 to **standard ESP32 (WROOM-32 class)**; native USB HID removed as a requirement; USB serial retained as the config/update interface; BLE HID confirmed as the primary transport on this target; board-independent capability architecture adopted; standard-ESP32 matrix GPIO feasibility assessed (fits, ~27 usable lines, no pins assigned); economical board class recommended.
