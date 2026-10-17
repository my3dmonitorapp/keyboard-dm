# ESP32 / ESP32-C3 family compatibility assessment

Status: F2-T4 build-layer decision. This assessment implements the shared-core,
separate-build requirement from the [F0 firmware architecture](../../firmware/DESIGN.md)
and the current [product specification](../product-specification.md). The first
9-key board remains unidentified; the later 75-key target is standard
ESP32-WROOM-32 class. The older S3-only Phase 0 brief is superseded by BD-1.

## Compatibility table

| Capability | ESP32 / WROOM-32 class | ESP32-C3 class | HAL/build consequence |
|---|---|---|---|
| CPU / clock | Xtensa LX6, up to 240 MHz, normally dual core | Single-core 32-bit RISC-V, up to 160 MHz | Separate `xtensa-esp32-elf` and `riscv32-esp-elf` binaries; timing is milliseconds, never cycle-counted in the core. |
| Flash | Module/board dependent; WROOM-32 commonly 4 MB | Package/module dependent; common modules have 4 MB | A 4 MB reference partition table is built, but F1 must verify real flash size before any manifest or write. |
| PSRAM | WROOM-32 normally has none; WROVER variants may add it | No general external PSRAM interface | Shared core uses fixed buffers and requires no PSRAM. |
| GPIO | 34 physical GPIOs; GPIO34–39 input-only/no internal pulls; module flash commonly consumes GPIO6–11 and sometimes 16–17 | 22 GPIOs; GPIO12–17 normally flash; GPIO18/19 default to USB Serial/JTAG | Family descriptors differ. Board row/column maps remain empty until verified. |
| Strapping | GPIO0, 2, 5, 12, 15 | GPIO2, 8, 9 | Conservatively denied as matrix lines in the initial descriptors; a reviewed BSP may be stricter, never guessed. |
| LEDC | 16 channels, high/low-speed groups | 6 low-speed channels | The HAL dynamically routes one low-speed LEDC channel to the one active matrix drive line, then returns it to input/high impedance. |
| ADC | ADC1 + ADC2; ADC2 conflicts with Wi-Fi; GPIO34–39 lack pulls | ADC1 on GPIO0–4 and ADC2 on GPIO5 | Matrix scanning is digital GPIO only; analog capability is not treated as matrix authorization. |
| Radio | Wi-Fi + Bluetooth Classic + BLE | Wi-Fi + BLE 5; no Bluetooth Classic | BLE-only firmware configuration works on both. Classic BT is disabled even on ESP32. |
| USB | No native USB controller or USB-OTG on classic ESP32; DevKits use an external USB-UART bridge | Fixed-function USB Serial/JTAG (CDC serial + JTAG), not USB-OTG | ESP32 console is UART0 at 115200; C3 console is `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG`. BLE remains the HID keyboard surface. |
| NVS | ESP-IDF NVS API | Same API | Same `kbd_dm` keys (`cfg_a`, `cfg_b`, `metadata`, version), but partitions/images are per-target and raw NVS is not assumed portable across devices. |
| Serial speed | Protocol default 115200 baud; ROM flashing commonly 460800 through a bridge | Native USB signals at USB full speed (12 Mbit/s), with no UART baud; bridge-equipped boards may use UART | `KBDM_SERIAL_BAUD=115200`; it configures UART0 only. `<PORT>` and actual reliable flash baud remain board/host evidence. |

GPIO facts follow Espressif's [ESP32 GPIO guide](https://docs.espressif.com/projects/esp-idf/en/v5.1/esp32/api-reference/peripherals/gpio.html)
and [ESP32-C3 GPIO guide](https://docs.espressif.com/projects/esp-idf/en/v5.1-rc1/esp32c3/api-reference/peripherals/gpio.html).
The C3 USB distinction and GPIO18/19 routing are documented in Espressif's
[v5.1 serial-connection guide](https://docs.espressif.com/projects/esp-idf/en/v5.1/esp32c3/get-started/establish-serial-connection.html).

## Source sharing and divergence

**Can one binary run on both ESP32 and ESP32-C3? No.** The classic ESP32 uses
Xtensa machine code while the C3 uses RISC-V machine code. They also select
different ESP-IDF targets, startup/linker material, GPIO capability tables,
reserved pins, and console transports. Each family therefore requires its own
cross compiler and its own build: `firmware/build.sh esp32` produces
`kbdm_esp32.bin`, while `firmware/build.sh esp32c3` produces
`kbdm_esp32c3.bin`. A binary must never be relabeled or used on the other
family.

This does not create two firmware forks. There is one untouched C11 core under
`firmware/shared`, referenced by the `kbdm_core` IDF component and the host
Makefile. Both family builds compile that same shared core and add their own
small target/capability layer.

The HAL divergence is limited to the cross compiler/IDF target, silicon GPIO
capability table, reserved flash/strap/USB pins, UART versus USB Serial/JTAG
console selection, and family sdkconfig. GPIO sampling, the single-active-line
LEDC policy, NVS A/B operations, BLE GATT reports, and the core state machines
share source. BSP pin maps contain zero rows/columns by default. F1 must identify
the 9-key chip and wiring before selecting either build or adding real pins.

## What an Arduino build would change

An Arduino-based build would still require a separate board package and binary
for each MCU family; Arduino cannot make Xtensa and RISC-V binary-compatible.
It would replace the explicit ESP-IDF project/sdkconfig/component integration
with an Arduino core, board definition, and pinned libraries, and it would need
equivalent implementations of BLE HID, serial transport, GPIO/LEDC handling,
and atomic NVS A/B behavior around the same shared state-machine semantics.
Unless those core, board-package, library, and partition versions were frozen,
the build would also be less reproducible. Arduino is retained only as a
possible preservation/recovery route if the original 9-key sketch and its exact
environment resurface; it is not the F2 build baseline. See
[`framework-decision.md`](framework-decision.md) for the full trade-off and
decision.

## Compatibility blockers before physical use

- Exact 9-key chip/module, flash size, board schematic, USB path, pins, diode
  direction, pull-ups, and current Arduino sketch/partition layout are unknown.
- The standard-ESP32 75-key board/module and matrix wiring remain unverified.
- The minimal F2 GATT transport must be interoperability-tested for keyboard and
  consumer-control reports on the acceptance host before F6.
- No F2 artifact or command authorizes flash, erase, GPIO testing, or activation.
