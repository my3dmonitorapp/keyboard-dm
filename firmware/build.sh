#!/usr/bin/env bash
set -u

reference_version=5.1.6
requested=${1:-esp32}
family=$requested

print_install_help() {
    cat <<'EOF'
ESP-IDF v5.1.6 toolchain missing; target build skipped (host tests remain usable).
Install the frozen SDK in a user-owned directory, then export its environment:
  mkdir -p "$HOME/esp"
  git clone --recursive --branch v5.1.6 https://github.com/espressif/esp-idf.git "$HOME/esp/esp-idf-v5.1.6"
  "$HOME/esp/esp-idf-v5.1.6/install.sh" esp32,esp32c3
  . "$HOME/esp/esp-idf-v5.1.6/export.sh"
Then run: firmware/build.sh esp32    # or: firmware/build.sh esp32c3
EOF
}

case "$family" in esp32|esp32c3) ;; --check) family=esp32 ;; *)
    echo "usage: $0 [esp32|esp32c3|--check]" >&2; exit 2;; esac

compiler=xtensa-esp32-elf-gcc
[ "$family" = esp32c3 ] && compiler=riscv32-esp-elf-gcc
if [ "$requested" = --check ]; then
    tools_present=true
    command -v xtensa-esp32-elf-gcc >/dev/null 2>&1 || tools_present=false
    command -v riscv32-esp-elf-gcc >/dev/null 2>&1 || tools_present=false
else
    tools_present=true
    command -v "$compiler" >/dev/null 2>&1 || tools_present=false
fi
if [ -z "${IDF_PATH:-}" ] || ! command -v idf.py >/dev/null 2>&1 ||
   [ "$tools_present" != true ]; then
    print_install_help
    exit 0
fi
if ! idf.py --version 2>/dev/null | grep -q "v${reference_version}"; then
    echo "ESP-IDF is present but is not reference v${reference_version}." >&2
    echo "Source the matching export.sh; refusing an unreviewed SDK build." >&2
    exit 2
fi
if [ "$requested" = --check ]; then
    echo "ESP-IDF v${reference_version} target environment is available."
    exit 0
fi

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
exec idf.py -C "$repo_dir/firmware" -B "build/$family" \
    -D "IDF_TARGET=$family" build
