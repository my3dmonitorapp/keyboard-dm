# Framework decision: Arduino versus ESP-IDF

Status: accepted for F2 new-firmware builds. This decision specializes the
[F0 architecture](../../firmware/DESIGN.md) for an unidentified Arduino-era
9-key device and a later ESP32-WROOM-32-class 75-key board.

## Decision drivers

F0 requires validated dynamic GPIO configuration, safe boot with all matrix
lines high-impedance, canonical config in NVS A/B slots, rollback metadata,
custom BLE HID keyboard plus consumer control, and an LF/JSON serial config
surface. The same C core must build for ESP32 and ESP32-C3 without claiming
binary compatibility.

| Criterion | Arduino core for ESP32 | ESP-IDF |
|---|---|---|
| Existing 9-key baseline | Likely the fastest route to understand or restore the board if its original sketch resurfaces | Cannot reproduce an unknown sketch or partition layout without evidence |
| BLE HID / consumer control | Convenient libraries, but behavior and transitive versions vary by core/library release | Direct supported Bluedroid/GATT APIs, explicit report/service ownership and sdkconfig |
| NVS A/B and safe boot | Preferences/NVS wrappers are easy, but atomic slot/read-back/rollback behavior is application work with less visible lifecycle control | Native NVS handles, explicit commits/errors/partitions, and deterministic startup ordering |
| Dynamic GPIO / tasks | Familiar sketch loop and quick experiments | Explicit GPIO/LEDC/FreeRTOS control and capability gating fit the safety model |
| Serial | `Serial` is an effective working baseline | UART console on ESP32 and fixed USB Serial/JTAG console on C3 are selected per target |
| Reproducibility | Depends on Arduino core, board package, IDE, and library versions unless separately locked | CMake, sdkconfig defaults, partition CSV, exact IDF tag, and two isolated target builds are reviewable in-tree |
| Multi-family maintenance | Board menus simplify sketches but can hide family-specific defaults | `IDF_TARGET`, compiler, Kconfig, and family HAL divergence are explicit |

## Decision

Use ESP-IDF v5.1.6 as the frozen v5.1 reference for the new firmware. The task
called v5.1 “LTS”; Espressif's published lifecycle instead gave v5.1 a normal
30-month support window ending 2025-12-30, so it is already EOL at this
document's 2026-10-17 date. The pin exists to reproduce F2, not to claim current
vendor support. Before a production or network-facing release, schedule a
reviewed migration to a then-supported stable/LTS ESP-IDF and rerun both target
builds plus BLE/NVS/device acceptance. Espressif's lifecycle guidance is in the
[v5.1 version policy](https://docs.espressif.com/projects/esp-idf/en/v5.1.3/esp32/versions.html).

Arduino remains an interim preservation and flash-recovery path for the 9-key
board only if its original sketch, exact board package, libraries, and partition
settings resurface. Preserve and inspect that material; do not translate,
compile, upload, erase, or overwrite it during F2. It does not become the new
firmware baseline and does not justify guessing that the board is ESP32-C3.

The practical result is one shared core, two ESP-IDF binaries, and no default
GPIO assignments. Framework choice does not relax the F1 identity/backup gate
or authorize physical-device work.
