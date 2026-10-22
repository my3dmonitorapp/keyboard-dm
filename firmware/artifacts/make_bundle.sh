#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/../.." && pwd)
artifact_dir="$repo_dir/firmware/artifacts"
build_dir="$repo_dir/build"
source_commit=fe17403765c9348e5f053ecd5e89acd010eaa6e7
build_date=2026-10-22
version=f3.0.0

sha() { sha256sum "$1" | cut -d ' ' -f 1; }
size() { stat -c %s "$1"; }
copy_family() {
    local family=$1
    mkdir -p "$artifact_dir/$family"
    cp "$build_dir/$family/bootloader/bootloader.bin" "$artifact_dir/$family/bootloader.bin"
    cp "$build_dir/$family/partition_table/partition-table.bin" "$artifact_dir/$family/partition-table.bin"
    cp "$build_dir/$family/kbdm_$family.bin" "$artifact_dir/$family/kbdm_$family.bin"
    cp "$build_dir/$family/kbdm_$family.elf" "$artifact_dir/$family/kbdm_$family.elf"
}

copy_family esp32
copy_family esp32c3

write_manifest() {
    local family=$1 boot_offset=$2 flash_freq=$3
    local boot="$artifact_dir/$family/bootloader.bin"
    local part="$artifact_dir/$family/partition-table.bin"
    local app="$artifact_dir/$family/kbdm_$family.bin"
    local output="$artifact_dir/manifests/kbdm-$family.json"
    mkdir -p "$artifact_dir/manifests"
    {
        printf '{\n'
        printf '  "schema": "keyboard-dm/firmware-manifest/1",\n'
        printf '  "name": "kbdm-%s",\n' "$family"
        printf '  "version": "%s",\n' "$version"
        printf '  "chip_family": "%s",\n' "$family"
        printf '  "flash_size": "4MB",\n'
        printf '  "flash_mode": "dio",\n'
        printf '  "flash_freq": "%s",\n' "$flash_freq"
        printf '  "images": [\n'
        printf '    {"file_name": "bootloader.bin", "offset": %s, "sha256": "%s", "size_bytes": %s},\n' "$boot_offset" "$(sha "$boot")" "$(size "$boot")"
        printf '    {"file_name": "partition-table.bin", "offset": 32768, "sha256": "%s", "size_bytes": %s},\n' "$(sha "$part")" "$(size "$part")"
        printf '    {"file_name": "kbdm_%s.bin", "offset": 65536, "sha256": "%s", "size_bytes": %s}\n' "$family" "$(sha "$app")" "$(size "$app")"
        printf '  ]\n}\n'
    } > "$output"
}

write_manifest esp32 4096 40m
write_manifest esp32c3 0 80m

{
    printf 'Keyboard DM firmware artifact versions\n'
    printf 'version=%s\n' "$version"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'build_date=%s\n' "$build_date"
    printf 'esp_idf=v5.1.6\n'
} > "$artifact_dir/VERSIONS.txt"

{
    printf 'Keyboard DM verified firmware bundle\n'
    printf 'Build host: RTX (local system hostname: %s)\n' "$(hostname)"
    printf 'ESP-IDF: v5.1.6\n'
    printf 'Source commit: %s\n' "$source_commit"
    printf 'Build date: %s\n' "$build_date"
    printf 'Version: %s\n' "$version"
    printf 'Verification: compile-only; no physical device I/O; not hardware-tested.\n'
    printf 'Checksums below cover every generated payload file; BUNDLE.txt is excluded to avoid a self-referential digest.\n\n'
    find "$artifact_dir" -type f ! -name BUNDLE.txt -printf '%P\n' \
        | LC_ALL=C sort \
        | while IFS= read -r relative; do
            printf '%s  %s\n' "$(sha "$artifact_dir/$relative")" "$relative"
        done
} > "$artifact_dir/BUNDLE.txt"
