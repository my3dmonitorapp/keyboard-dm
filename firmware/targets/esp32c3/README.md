# ESP32-C3 target

Build from the repository root after sourcing ESP-IDF v5.1.6:

```sh
firmware/build.sh esp32c3
```

The unverified BSP has zero rows and columns. A verified board adds only
`boards/<name>/Kconfig` and `board_pinmap.h`; it does not fork firmware sources.

ESP32-C3 provides fixed-function USB Serial/JTAG on GPIO18/19. It enumerates a
CDC serial/JTAG interface and can flash/debug without an external bridge, but it
is not USB-OTG and cannot become an arbitrary USB HID device. Some C3 boards
instead expose UART through a USB-UART bridge. The configured 115200 value is
protocol metadata for native USB; USB itself has no UART baud rate.

Prefer `idf.py -p <PORT> flash`. The explicit reference 4 MB factory-layout
command is for release-manifest review only (C3 bootloader offset is 0):

```sh
esptool.py --chip esp32c3 --port <PORT> --baud 460800 write_flash \
  0x0 build/esp32c3/bootloader/bootloader.bin \
  0x8000 build/esp32c3/partition_table/partition-table.bin \
  0x10000 build/esp32c3/kbdm_esp32c3.bin
```

No command here authorizes flashing, erasing, or changing a physical board.
