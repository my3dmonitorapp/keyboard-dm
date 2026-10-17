#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
make -C "$repo_dir/firmware/host" clean
make -C "$repo_dir/firmware/host" test

if [ -n "${IDF_PATH:-}" ] && command -v idf.py >/dev/null 2>&1 &&
   command -v xtensa-esp32-elf-gcc >/dev/null 2>&1 &&
   command -v riscv32-esp-elf-gcc >/dev/null 2>&1; then
    "$repo_dir/firmware/build.sh" esp32
    "$repo_dir/firmware/build.sh" esp32c3
else
    "$repo_dir/firmware/build.sh" --check
fi
