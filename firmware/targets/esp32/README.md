# ESP32 (WROOM-32-class) target

Build from the repository root after sourcing ESP-IDF v5.1.6:

```sh
firmware/build.sh esp32
```

The unverified BSP has zero rows and columns. Do not enable a pin map until F1
records the exact module, schematic, matrix wiring, straps, flash/PSRAM wiring,
and USB-UART bridge. Add a board as one `boards/<name>/Kconfig` plus
`board_pinmap.h`; the HAL and shared firmware sources remain unchanged.

Classic ESP32 has no native USB peripheral or USB-OTG. A WROOM-32 development
board normally exposes UART0 through CP210x/CH340-class USB-UART hardware. The
protocol UART default is 115200 baud; ROM flashing commonly uses 460800 baud.

Prefer `idf.py -p <PORT> flash`, which consumes generated offsets. The explicit
reference 4 MB factory-layout command is for release-manifest review only:

```sh
esptool.py --chip esp32 --port <PORT> --baud 460800 write_flash \
  0x1000 build/esp32/bootloader/bootloader.bin \
  0x8000 build/esp32/partition_table/partition-table.bin \
  0x10000 build/esp32/kbdm_esp32.bin
```

These commands are documentation, not authorization to flash a device.
