# Keyboard DM firmware foundation

This directory contains the host-verified core and two separate ESP-IDF target
builds. Builds do not contact a device; flashing is always a separate, gated
operation.

## Layout

- `shared/include/` and `shared/src/` contain the dependency-free C11 core.
- `kb_runtime` gates scanner startup on validated boot state, schedules matrix
  scans, dispatches events into HID state, and incrementally services the
  serial protocol from caller-supplied bytes and time.
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

The host suite is the only build supported on this machine at present. Run the
clean build and all tests with:

```sh
make -C firmware/host clean test
```

The Makefile uses only the local C compiler and standard library. Every test
binary is compiled with `-std=c11 -Wall -Wextra -Werror`. No ESP-IDF, Arduino,
CMake, package installation, network access, device connection, or flashing is
required or attempted.

The current suite covers config validation and structured field errors,
canonical config JSON round trips and CRC checking, valid/malformed protocol
fixtures with output-integrity checks, CRC32 known vectors, fake-HAL fault
injection, and end-to-end runtime gating/scanning/HID/config-update behavior.
`clean test` first removes `firmware/host/build/`, so stale objects cannot
affect the result.

## ESP-IDF builds

The frozen reference is ESP-IDF v5.1.6. Run one family build at a time:

```sh
firmware/build.sh esp32
firmware/build.sh esp32c3
```

Cross-compilation is **not possible on this machine right now**: the root
filesystem is 99% full (about 1.6 GB free), and neither the
`xtensa-esp32-elf` nor `riscv32-esp-elf` toolchain is installed. Do not attempt
an installation until space has been deliberately freed; this repository does
not install system-wide dependencies.

To enable both target builds, provide all of the following:

1. Enough free disk space for a recursive ESP-IDF checkout, its Python
   environment, both compiler toolchains, and two build trees.
2. The host prerequisites listed by Espressif for the host OS.
3. A user-owned recursive checkout of the exact `v5.1.6` tag.
4. The ESP32 and ESP32-C3 tools installed by that checkout's installer.
5. The checkout's `export.sh` sourced in the shell that runs `build.sh`, so
   `IDF_PATH`, `idf.py`, `xtensa-esp32-elf-gcc`, and
   `riscv32-esp-elf-gcc` resolve to the v5.1.6 environment.

For example, after satisfying items 1 and 2:

```sh
mkdir -p "$HOME/esp"
git clone --recursive --branch v5.1.6 https://github.com/espressif/esp-idf.git "$HOME/esp/esp-idf-v5.1.6"
"$HOME/esp/esp-idf-v5.1.6/install.sh" esp32,esp32c3
. "$HOME/esp/esp-idf-v5.1.6/export.sh"
firmware/build.sh esp32
firmware/build.sh esp32c3
```

These commands are instructions for a suitably provisioned machine; they were
not run as part of F2. `build.sh` never downloads a toolchain and, when the SDK
or selected compiler is absent, prints the setup instructions and exits without
cross-compiling. Therefore its zero exit status alone is not proof that a target
binary was produced. `firmware/ci.sh` always runs the host suite and adds both
IDF builds only when both toolchains are already exported. Target output is
isolated in `firmware/build/<family>/`.

The default `unverified` BSP contains no matrix GPIO assignments. A new board
adds a board Kconfig and pin-map header; it does not copy or fork firmware code.
See each target README for transport details and manifest/flash offsets.
The serial console implemented by the shared core is specified in
[`PROTOCOL.md`](PROTOCOL.md). Physical-board work remains gated by
[`CONTRIBUTING.md`](CONTRIBUTING.md).
