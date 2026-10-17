# Keyboard DM firmware foundation

This directory contains the host-verified core and two separate ESP-IDF target
builds. Builds do not contact a device; flashing is always a separate, gated
operation.

## Layout

- `shared/include/` and `shared/src/` contain the dependency-free C11 core.
- `host/` contains the fake HAL, test harness, JSON fixture corpus, and Makefile.
- `components/kbdm_core/` references (and never copies) every shared C source.
- `components/kbdm_idf_hal/` implements LEDC/GPIO matrix I/O, NVS A/B storage,
  the serial console, monotonic time, and a BLE GATT HID transport.
- `targets/esp32/` and `targets/esp32c3/` provide separate family capability,
  console, BSP, and sdkconfig layers. They produce different binaries.

`kb_hal.h` is the only platform boundary. Shared code contains no platform SDK
headers and no mutable global state. The config parser writes its caller-owned
output only after the complete JSON document has parsed successfully.

## Host build and tests

Run:

```sh
make -C firmware/host test
```

The Makefile uses only the local C compiler and standard library. Every test
binary is compiled with `-std=c11 -Wall -Wextra -Werror`. No ESP-IDF, Arduino,
CMake, package installation, network access, device connection, or flashing is
required or attempted.

The current suite covers config validation and structured field errors,
canonical config JSON round trips and CRC checking, valid/malformed protocol
fixtures with output-integrity checks, CRC32 known vectors, and fake-HAL fault
injection.

Use `make -C firmware/host clean` to remove host build products.

## ESP-IDF builds

The frozen reference is ESP-IDF v5.1.6. Run one family build at a time:

```sh
firmware/build.sh esp32
firmware/build.sh esp32c3
```

The script prints exact user-local installation steps and exits successfully if
the SDK/cross compiler is absent. It never downloads a toolchain. `firmware/ci.sh`
always runs the host suite and adds both IDF builds only when both toolchains are
already exported. Target output is isolated in `firmware/build/<family>/`.

The default `unverified` BSP contains no matrix GPIO assignments. A new board
adds a board Kconfig and pin-map header; it does not copy or fork firmware code.
See each target README for transport details and manifest/flash offsets.
