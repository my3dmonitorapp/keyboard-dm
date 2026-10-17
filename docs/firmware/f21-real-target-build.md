# F2.1 — Real Target Build Verification (VM CI, 2026-10-17)

Environment: isolated Ubuntu VM, ESP-IDF v5.1.6 (xtensa-esp32 + riscv32-esp-elf
12.2.0 toolchains), repo cloned from GitHub origin (no rsync). No laptop work,
no hardware touched, no flashing.

## Results (final)

| Target   | Result | App binary                | Size        | SHA-256 |
|----------|--------|---------------------------|-------------|---------|
| esp32    | PASS   | kbdm_esp32.bin            | 0xc0020 (50% free)       | 5bba19ae6a39769095d975b4ae668e69deed6110383464383b4133572686421b |
| esp32c3  | PASS   | kbdm_esp32c3.bin          | 0xcff30 (46% free)       | 3a48f1b011dc3d53dac1874da89ef36c10b660163a4fd43649941ea262ba6a44 |

Supporting artifacts (esp32 build):
- bootloader.bin        6ce4a70678b58133508912fd19155f15a5c097052eee17889b8f33bee43c790f
- partition-table.bin   a11982a2601a607baadac94c0f21fdb7fdbf910249ed5ba58af40be62c2ee98a

Logs: /root/kb75_ci/logs/esp32.log, /root/kb75_ci/logs/esp32c3.log
Artifact copies: /root/kb75_ci/artifacts/

## Root causes fixed in this commit
1. KBDM_* Kconfig wiring: each target's main/Kconfig.projbuild only rsource'd the
   board Kconfig; the root Kconfig.projbuild (KBDM_SCAN_PERIOD_MS,
   KBDM_RUNTIME_TASK_STACK, KBDM_RUNTIME_TASK_PRIORITY) was never reached.
   Added `rsource "../../../Kconfig.projbuild"` line to both targets.
2. ESP32-C3 BLE host flag: the HAL uses classic BLE 4.2 gap API
   (esp_ble_gap_start_advertising / esp_ble_gap_config_adv_data), which IDF only
   compiles into the host stack when BT_BLE_42_FEATURES_SUPPORTED is on. C3
   defaults to BLE 5.0. Enabled CONFIG_BT_BLE_42_FEATURES_SUPPORTED in
   targets/esp32c3/sdkconfig.defaults (per-device board choice, not a global
   default change).

## Known limitations
- Compilation + linking only. First real hardware bring-up still pending
  (F1 identify board + backup; flashing requires explicit separate
  authorization). C3 binary uses BLE 4.2 host stack — BLE 5.0-only features
  (periodic advertising, etc.) are not available on this build by design.
- sdkconfig.defaults at repo root is required by the IDF build; an earlier
  working-tree deletion was restored (git checkout) — it remains tracked.
