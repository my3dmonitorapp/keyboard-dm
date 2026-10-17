# Keyboard DM firmware foundation

This directory contains the host-verified, platform-independent foundation for
Keyboard DM firmware. It does not contain flashable firmware and no command in
this directory contacts a device.

## Layout

- `shared/include/` and `shared/src/` contain the dependency-free C11 core.
- `host/` contains the fake HAL, test harness, JSON fixture corpus, and Makefile.
- `targets/esp32/` and `targets/esp32c3/` are documented placeholders for the
  later target integration task.

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
