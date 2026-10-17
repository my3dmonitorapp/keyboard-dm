# F0 — ESP32 firmware architecture and first-physical-demo plan

Status: planning only  

First physical target: Daniele's existing 9-key keyboard on an ESP32-class MCU; exact chip, board, wiring, flash layout, and current firmware are not yet identified or approved for writing

Scope through F6: integrated Keyboard DM firmware installation, BLE HID keyboard operation, USB-UART serial configuration/diagnostics, runtime-configured matrix, physical-key testing, and persistent configuration. F7 reuses the same firmware on the completed 75-key board. No GPIO allocation is made here.

This task changes documentation only. It defines no executable implementation, performs no hardware operation, and authorizes no flash, erase, or overwrite.
The integrated installer is the immediate F0 implementation target after M1.1, which is already merged to `main`.

## 1. System overview

Keyboard DM remains the source of truth for layout and typed assignments. The existing PySide6 application also owns the integrated firmware-installer flow: USB-port discovery, honest chip identification, compatible-build selection from a release-controlled manifest, pre-flash backup, guided `esptool` execution, verification, and reconnect. After installation, Keyboard DM converts the existing project-v3 JSON into a device envelope and sends it over the board's USB-UART CDC/COM serial path. The ESP32 scans the configured matrix and presents a BLE HID keyboard/consumer-control endpoint to the host PC. Reassigning keys or changing a validated matrix configuration updates NVS; it does not require reflashing firmware.

```text
+-----------------------+       USB cable / CDC serial       +------------------------+
| Keyboard DM desktop   | <================================> | ESP32-class target     |
| installer + project   | install, config, status,           | ROM loader + firmware  |
| v3/profile v2         | diagnostics                        | NVS -> scan -> dispatch |
+-----------------------+                                     +-----------+------------+
                                                                            |
                                                                            | BLE HID
                                                                            v
                                                               +------------------------+
                                                               | Host PC                |
                                                               | Windows 11 or Linux    |
                                                               +------------------------+
```

“USB serial” in this plan means the COM/tty interface presented either by a board's external CH340/CP2102-class USB-UART bridge or by another interface positively identified at F1. A bare standard ESP32-WROOM-32 has no native USB peripheral; the 9-key device must not be assumed to be WROOM-32 until read-back and board evidence agree. USB serial and BLE coexist: USB is configuration, diagnostics, and firmware loading; BLE is the keyboard HID surface accepted at F6.

## 2. Firmware architecture

### Components and tasks

| Component | Responsibility | Task/context and boundary |
|---|---|---|
| Application main | Initialize NVS, load and validate configuration, select last-known-good or safe mode, initialize queues, serial, scanner, and BLE in that order | Startup context; never enables matrix outputs until validation succeeds |
| Serial/protocol service | Incremental LF-framed JSON parser, request/response routing, upload staging, diagnostics subscriptions, and bounded buffers | Dedicated low-priority task; malformed input returns an error and cannot block scanning |
| Matrix scan engine | Runtime `rows`, `cols`, row/column GPIO arrays, drive/read direction, populated-cell mask, and scan cadence; implementation ceiling initially 16x16 | High-priority periodic task; publishes raw cell changes only. The 16x16 firmware ceiling is narrower than the desktop model's 32x128 editing ceiling and must be advertised/validated |
| Debounce/state machine | Per populated cell: stable up, debouncing-down, stable down, debouncing-up; time-based thresholds independent of scan count | Scanner task or immediately downstream; emits exactly one press/release transition per stable change |
| Key dispatch | Resolve `MX-rr-cc` to the configured typed action; maintain aggregate modifier/key/media state; sequence text; reserve a macro executor interface | Event task; emits complete HID state snapshots, not lossy edge-only reports |
| BLE HID endpoint | Advertising, pairing/bonding, connection state, HID report map, report queue, and release-all recovery | Bluetooth callbacks plus an application queue; callbacks do not scan or parse JSON |
| Configuration manager | Validate device envelope, stage/commit NVS slots, expose active/last-good status and generation | Serialized access; scanner receives an immutable validated snapshot |
| Diagnostics | Structured boot/config/BLE/scan counters and opt-in live key events | Serial service; rate-limited and never included in BLE HID |

FreeRTOS communication is by bounded queues/event groups. A configuration commit builds and validates a new immutable snapshot, pauses scanning, sends an all-released HID state, atomically swaps the snapshot, resets debounce state, and resumes. This prevents mixed pin maps and stuck keys.

### Matrix scanning and rollover

Only populated cells are dispatched, although all required electrical lines are scanned. Each cycle drives one output line at a time; all other drive lines are high-impedance, then the input lines are sampled after a configurable settling interval. The initial target is a stable 1 kHz-class whole-matrix scan with measured debounce defaults (provisionally 5 ms press and 5 ms release), both tunable in a later schema extension after hardware measurement.

The scanner and state model retain every populated key independently. With one correctly oriented diode per switch, the internal state and normal-protocol HID bitmap support full N-key rollover for all 75 populated keys. The optional HID boot-protocol representation is necessarily 6-key rollover and is not the F6 acceptance path.

### Actions and HID reports

`actions` values reuse `profile.py` typed assignment objects without renaming fields: `{"type":"key","key":"a"}`, `{"type":"shortcut","modifiers":["lctrl"],"key":"s"}`, `{"type":"media","key":"vol_up"}`, `{"type":"modifier","modifier":"lshift","event":"down"}`, or `null`. The current `legacy` form is preserved by the desktop for migration but is rejected for device activation because it has no deterministic HID meaning. A future `{"type":"text","text":"..."}` dispatcher is reserved; macro objects remain a schema extension.

The BLE HID report map should expose (the Report ID byte is handled by the HID transport and is not counted in the payload sizes below):

- Report ID 1, normal keyboard input: a 17-byte payload consisting of one modifier byte and a 16-byte bitmap for Keyboard/Keypad usages `0x00..0x7f`. The current desktop key catalog ends at `0x7e`, so every supported non-modifier usage has one bit and the payload is below the 64-byte ceiling. This is the full-NKRO F6 path.
- Report ID 2, consumer-control input: a one-byte bitmap for the six current media actions, with two bits reserved and required to be zero.
- Boot keyboard compatibility: the conventional 8-byte modifier/reserved/six-key report when a host explicitly selects boot protocol. Overflow is reported rather than silently dropping arbitrary keys.
- Output report for host LED state (Caps Lock and similar), even if F5 only records it diagnostically.

On connect, disconnect, configuration swap, and reboot, the endpoint clears aggregate state so no key remains stuck. Initial pairing uses bonded BLE HID with the security mode implemented in the hardware-free F2 build and proven on the selected ESP32/host combination during the authorized F4–F6 sequence. With no display confirmed, the baseline is an explicitly user-initiated discoverable window and the strongest ESP-IDF-supported no-display association approved at the hardware gate; unattended permanent discoverability is not acceptable. On disconnect, firmware re-advertises to the bonded host, first using a reconnect-oriented window and then a bounded general-advertising window. Bonds survive ordinary reboot/config updates and are erased only by an explicit pairing-reset/factory-reset action.

### NVS and safe boot

Use NVS namespace `kbd_dm`. Store one canonical UTF-8 JSON blob of approximately 2–4 KB per slot under `cfg_a` and `cfg_b`, accompanied by schema version, generation, length, and SHA-256 (or CRC plus SHA-256 from the transfer). A small `active` record identifies the committed generation. Upload is written to the inactive slot, read back, hashed, parsed, and fully validated before the active marker changes. The prior generation remains the last-known-good rollback candidate. NVS initialization/recovery must not erase BLE bonds implicitly.

Every boot validates before configuring GPIO:

| Rule | Required behavior |
|---|---|
| Shape | Require integer `rows`/`cols` in 1..16, pin-array lengths equal to dimensions, and no more than 256 cells |
| Pin presence/range | Every line has an integer GPIO supported by the confirmed chip/board capability descriptor; `null` desktop placeholders are not uploadable |
| Reserved resources | Reject the required deny-list including GPIO 6, 7, 8, and 15. For the current desktop policy, also remain consistent with `FLASH_RESERVED_PINS = {6,7,8,12,15}`; the approved board descriptor may be stricter (for example the WROOM flash bus and UART/strapping constraints) but never looser without a hardware decision |
| Uniqueness | Reject duplicates within or across `row_pins` and `col_pins` |
| Direction capability | Reject input-only GPIO for whichever side is driven. In the default row-driven mode this includes every row pin; input-only read pins also require external pull-ups because GPIO34–39 have none |
| Geometry | Each populated entry is unique, within bounds, and has exactly canonical `key_id = MX-{row:02d}-{col:02d}`; its key set equals the `actions` key set |
| Electrical mode | Require one of the two exact scan-mode/diode-direction pairs in section 3 |
| Action/schema | Accept only known protocol/config versions and supported action shapes; reject unknown required fields or features |

If the newest slot fails, record `rollback`, boot the previous valid generation, and report both generations and the validation error. If neither slot is valid, enter safe mode: all matrix pins remain inputs/high-impedance, no key reports are sent, serial protocol/status remains available, and BLE may advertise only a non-keying diagnostic identity if needed. Invalid configuration must never assert pins, crash, boot-loop, or erase the last-known-good slot.

Diagnostics are structured protocol messages, not free-form text mixed into responses. Minimum state includes boot reason, firmware/protocol versions, active generation/hash, validation/rollback/safe-mode status, BLE state, dropped-event counters, scan timing overruns, and rate-limited errors. Human-readable ESP-IDF logs may remain on the monitor UART during development, but protocol clients must be able to distinguish them (production protocol mode should emit JSON lines only).

## 3. Diode direction and scan-mode validation

Names describe conventional current through a closed switch diode, from anode to cathode. Firmware supports exactly two modes:

| `scan_mode` | `diode_direction` | Driven side | Read side / active sample | Valid input-pin use |
|---|---|---|---|---|
| `drive_rows_low_read_cols_pullup` | `col_to_row` | One row low; other rows high-impedance | Columns pulled up; pressed reads low | Input-only GPIO may be a column only, with an external pull-up where internal pull-up is unavailable |
| `drive_cols_low_read_rows_pullup` | `row_to_col` | One column low; other columns high-impedance | Rows pulled up; pressed reads low | Input-only GPIO may be a row only, with an external pull-up where internal pull-up is unavailable |

The paired values are intentionally redundant: they make wiring intent reviewable and prevent a mode from silently reversing an asserted diode direction. Firmware rejects `drive_rows_low_read_cols_pullup` + `row_to_col`, `drive_cols_low_read_rows_pullup` + `col_to_row`, unknown/null values, any output-side input-only pin, missing pull-up capability where the selected pin needs an external resistor, and any populated cell outside the declared geometry.

Geometry can prove bounds and the `MX-rr-cc` mapping; it cannot electrically discover diode orientation. Upload therefore proves only that the declared `scan_mode` and `diode_direction` agree. F1 must supply continuity/diode-test evidence for the declaration. F5 verifies sampled idle/pressed levels and matrix positions before relying on HID dispatch.

The current `matrix_model.py` serializes `rows`, `cols`, `switches`, `row_pins`, and `column_pins`, but does not yet serialize `scan_mode` or `diode_direction`. F5 must add those as explicit project/deployment data or require an explicit upload-time selection; firmware must never infer them from visual layout, `key_widths`, or `key_visual_offsets`.

## 4. Desktop <-> firmware protocol

### Framing and common envelope

Protocol version 1 is UTF-8, line-delimited JSON over the CDC/COM serial byte stream, initially at 115200 baud, 8 data bits, no parity, 1 stop bit, and no flow control: one ASCII character occupies one byte, each JSON object is compact and single-line, and LF (`0x0A`) terminates the frame. CR immediately before LF may be ignored. Strings containing non-ASCII are UTF-8 and byte counts/hashes use the encoded bytes. Maximum inbound line length is 1536 bytes; overlength or malformed frames are discarded through LF and receive an error when an `id` can be recovered.

Every request is `{"id":"client-unique-id","cmd":"name","params":{...}}`. Exactly one response carries the same `id`: success is `{"id":"...","ok":true,"result":{...}}`; failure is `{"id":"...","ok":false,"error":{"code":"stable_code","message":"human text","details":{}}}`. IDs are strings of 1–64 printable ASCII characters and may not be reused while outstanding. Unsolicited events have `event` instead of `id` and occur only after subscription, except critical boot diagnostics.

### Commands

| Command | Exact `params` | Success `result` |
|---|---|---|
| `version` | `{}` | `{"firmware_version":"x.y.z","build_id":"...","chip_class":"esp32","protocol_versions":[1],"active_protocol":1,"config_schema_versions":[1]}` |
| `ping` | `{"nonce":"optional string"}` | `{"nonce":"same value","uptime_ms":1234}` |
| `config_upload` | Start: `{"phase":"start","upload_id":"u1","encoding":"base64","total_bytes":3210,"sha256":"64 lowercase hex"}`; chunk: `{"phase":"chunk","upload_id":"u1","seq":0,"data":"base64"}`; commit/abort: `{"phase":"commit|abort","upload_id":"u1"}` | Start/chunk: `{"phase":"start|chunk","upload_id":"u1","accepted":true,"next_seq":0}` (incremented after a chunk); commit: `{"phase":"commit","generation":7,"sha256":"...","status":"validated"}`; abort: `{"phase":"abort","discarded":true}`. Use raw chunks <=1024 bytes so encoded request lines stay below 1.5 KB; any envelope >1.5 KB must use this flow |
| `config_get` | `{"source":"active|last_good"}` to open; then `{"transfer_id":"g1","seq":0}` | Open: `{"transfer_id":"g1","encoding":"base64","total_bytes":3210,"sha256":"...","chunks":4}`; chunk: `{"transfer_id":"g1","seq":0,"data":"base64","eof":false}` |
| `config_status` | `{}` | `{"state":"validated|rollback|safe_mode","active_generation":7,"last_good_generation":6,"active_sha256":"...|null","error":null|{"code":"...","message":"..."}}` |
| `key_event` | `{"enabled":true|false}` | `{"enabled":true|false}`; while enabled, debounced events are emitted as specified below |
| `gpio_test` | `{"pin":34,"samples":8,"pull":"none|up|down"}` | `{"pin":34,"mode":"input","samples":[1,1,0,1,1,1,1,1],"high":7,"low":1}`. Read-only/high-impedance; reject active matrix, flash, UART, unsupported, or output-drive requests. External pull-up requirements still apply |
| `factory_reset` | `{"confirm":"ERASE_CONFIG_AND_BONDS"}` | `{"accepted":true,"reboot_required":true}` after erasing both config slots and BLE bonds; firmware remains safe until reboot |
| `reboot` | `{"delay_ms":0}` where 0..5000 | `{"accepted":true,"delay_ms":0}` sent before restart |

Only one upload/download transfer may be active. Duplicate chunk `seq` may be acknowledged if its decoded bytes match; gaps, conflicting duplicates, hash/length mismatch, timeouts, and validation errors abort staging without changing the active generation.

### Device configuration envelope

```json
{
  "protocol_version": 1,
  "config_schema_version": 1,
  "chip_class": "esp32",
  "matrix": {
    "rows": 2,
    "cols": 2,
    "row_pins": ["<GPIO_R0>", "<GPIO_R1>"],
    "col_pins": ["<GPIO_C0>", "<GPIO_C1>"],
    "diode_direction": "col_to_row",
    "scan_mode": "drive_rows_low_read_cols_pullup",
    "populated": [
      {"row": 0, "col": 0, "key_id": "MX-00-00"},
      {"row": 1, "col": 1, "key_id": "MX-01-01"}
    ]
  },
  "actions": {
    "MX-00-00": {"type": "key", "key": "a"},
    "MX-01-01": {"type": "shortcut", "modifiers": ["lctrl"], "key": "s"}
  },
  "meta": {
    "project_name": "Demo",
    "project_version": 3,
    "profile_version": 2,
    "matrix_schema_version": 1,
    "updated": "2026-10-16T00:00:00+00:00"
  },
  "extensions": {}
}
```

The GPIO strings above are placeholders to demonstrate schema only; an actual upload requires integers established at F1 and approved for use at F4/F5. Mapping is semantic and lossless for device-relevant data:

| Existing Keyboard DM field | Device envelope |
|---|---|
| project `project_version` (currently 3), `name` | `meta.project_version`, `meta.project_name` |
| embedded profile `profile_version` (currently 2), `updated` | corresponding `meta` fields |
| `matrix.rows`, `matrix.cols`, `matrix.row_pins` | same names |
| `matrix.column_pins` | `matrix.col_pins` (the only deliberate pin-field rename) |
| each `[row,col]` in `matrix.switches` | one `matrix.populated` entry plus deterministic `MX-rr-cc` |
| `keys[key_id].assignment` | `actions[key_id]`, unchanged typed object or `null` |
| `matrix.key_widths`, `key_labels`, `key_visual_offsets`; `layout` geometry | desktop-only presentation data, not needed to scan or dispatch; retained in the desktop project, never interpreted as wiring |

The populated key-ID set, action key set, and project matrix switch set must be identical. Thus all device-relevant existing JSON maps 1:1 in meaning, while presentation fields remain at their source. Reconfiguration is a config upload/NVS commit, never a firmware rebuild. `scan_mode` and `diode_direction` are the explicit additive gap described in section 3.

### Worked lines

For readability, this example uses a tiny base64 payload; a real device envelope uses start/chunk/commit and a real SHA-256.

```json
{"id":"42","cmd":"config_upload","params":{"phase":"start","upload_id":"u1","encoding":"base64","total_bytes":3210,"sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}}
{"id":"42","ok":true,"result":{"phase":"start","upload_id":"u1","accepted":true,"next_seq":0}}
```

After `{"id":"stream","cmd":"key_event","params":{"enabled":true}}` is acknowledged, a debounced transition is:

```json
{"event":"key_event","seq":81,"key_id":"MX-03-07","row":3,"col":7,"state":"pressed","timestamp_ms":91842}
```

## 5. Toolchain recommendation

Use Espressif ESP-IDF v5.x with its CMake/Ninja build flow and freeze the exact tested v5.x tag in F2 project metadata. It provides the supported ESP32 BLE HID stack, NVS, FreeRTOS/task control, partition configuration, logging, and `esptool` integration without Arduino framework abstractions. It also makes SDK version and configuration reproducible. Arduino/PlatformIO can accelerate sketches, but adds framework/version indirection and gives less explicit control over BLE callbacks, tasks, NVS recovery, partitioning, and reproducible official-example alignment; it is not recommended for this firmware baseline.

The baseline flashing workstation is Windows 11 x64 with Git, Python as installed/managed by ESP-IDF, the ESP-IDF v5.x tools environment, the selected board's signed CH340/CP2102 driver if Windows does not supply it, and either:

1. VS Code plus Espressif's ESP-IDF extension, configured to the frozen ESP-IDF installation; or
2. the matching “ESP-IDF Command Prompt/PowerShell” environment for command-line work.

The ESP-IDF target must come from the F1-confirmed chip family and matching build manifest; neither the generic `esp32` target nor `<PORT>` may be baked into source:

```text
idf.py set-target <IDF_TARGET>
idf.py build
idf.py -p <PORT> flash
idf.py -p <PORT> monitor
idf.py -p <PORT> flash monitor
```

These are developer-reference commands, not authorization to execute them. The integrated app uses the manifest-defined images/offsets and remains subject to the F4 authorization gate.

`esptool` is the lower-level inspection, backup, and flashing engine. The integrated installer must use automatic chip detection first and compare that result with read-back identity and the selected build manifest; it must never force `--chip` merely to bypass a mismatch. Developer builds may use `idf.py` so partition offsets come from generated build metadata, while distributable builds must publish those offsets and all images in the manifest consumed by Keyboard DM. On Linux, the equivalent port is typically `/dev/ttyUSB*` or `/dev/ttyACM*`, with distro-specific serial permissions, but Windows 11 is the installer baseline unless F1 records another host.

The USB cable may remain attached while BLE is paired. They are independent surfaces: CDC/COM serial transports configuration and diagnostics over USB; BLE wirelessly transports HID keyboard/consumer reports. Standard ESP32 does not enumerate as a native USB keyboard.

### Integrated installer and configuration capabilities

The installer is a workflow inside the existing Keyboard DM PySide6 application, not a separate utility. Destructive controls remain disabled until identity, compatibility, backup outcome, and authorization state are explicit. A firmware-build registry entry is immutable release metadata containing at least `target_name`, firmware `version`, exact `chip_family`, supported flash size(s), image filenames and offsets, and SHA-256 for every image (or for a single merged image). Missing, unknown, ambiguous, or incompatible data is a hard error; the application must not guess a board or offer an override that silently weakens compatibility.

| Required application capability | Delivered in | Verification milestone / evidence |
|---|---|---|
| Enumerate ESP32 candidates over USB serial; distinguish automatic DTR/RTS bootloader reset from the confirmed manual reset/IO0 path | F3 | F3 simulated-port and hot-plug tests plus read-only observation of the F1-identified 9-key port; F4 proves download-mode entry under authorization |
| Read exact ESP32 chip family, revision, and detected flash size with `esptool`; report unknown or conflicting identity without guessing | F1 identifies the first device; F3 integrates the flow | F1 evidence record and repeated F3 read-back comparison against board markings/design |
| Select only a compatible Keyboard DM build from the manifest (`chip_family`, flash size, target, version, image offsets, SHA-256) | F3 | Manifest fixture matrix covers exact match, corrupt hash, unknown device, ambiguity, and incompatibility; every unsafe case blocks flashing |
| Guide `esptool` flashing with phase/progress display, post-write verification, cancellation boundaries, and structured actionable errors | F3 | F3 dry-run/fake-process tests cover success and failure phases; F4 is the first authorized real flash and verify |
| Before replacement, dump full flash to `.bin` where supported and read/export NVS separately; present written recovery limitations for missing external reset, encrypted/custom flash, unknown layout, or lost configuration paths | F1 produces the first backup/recovery plan; F3 integrates it | F1 hashes and records read-back artifacts or an explicit unsupported result; F4 cannot enable write until the reviewed backup result and limitations are acknowledged |
| Reconnect after installation by waiting for USB re-enumeration, rescanning serial ports, identifying the device again, and showing serial/BLE pairing notes | F3 | F3 re-enumeration simulations and F4 real post-flash identity/version response |
| Configure matrix rows, columns, GPIO mappings, scan/diode mode, and populated switch positions in Keyboard DM | F5 | F5 validates the reviewed 9-key wiring record and rejects incomplete, duplicate, reserved, or incapable GPIO assignments |
| Upload configuration over USB serial without reflashing, using section 4 | F5 | F5 upload/read-back/hash round-trip and generation increment on the real 9-key device |
| Stream detected physical key transitions and report `row`, `col`, and `switch-ID` for each press | F5 | F5 operator presses every populated 9-key position and confirms the live report against the wiring record |
| Save typed keyboard actions persistently in the ESP32 NVS actions profile | F2 firmware support; F5 desktop workflow | F5 power-cycle read-back and changed-action persistence on the 9-key device |
| Operate as a Bluetooth HID keyboard | F2 firmware support | F6 end-to-end acceptance produces the assigned Bluetooth keystroke and repeats it after an assignment-only update without reflashing |

## 6. Hardware verification gate and required information

F1 is an identify-and-preserve gate for Daniele's existing 9-key keyboard, the first physical device. It may use non-writing `esptool` identity/read commands and a full-flash/NVS read-back where supported, but it authorizes no erase, flash, overwrite, configuration upload, or other mutation. Before F4 can write anything, Daniele must separately and explicitly authorize that exact recorded device after reviewing the backup artifacts and recovery limitations. The 12-key board is entirely off-limits: do not connect it for this work, inspect it with tools, erase it, or write it.

F1 must record all of the following:

- **Exact module/board:** photographs, visible markings and ordering identity (WROOM-32, WROOM-32E, WROVER, S2/S3/C3, or other), board model/revision/design evidence, chip family/revision from automatic `esptool` detection, flash size, PSRAM if any, and a trustworthy pinout/schematic. Also identify the USB bridge/native-USB design and whether DTR/RTS provides automatic bootloader entry. Board markings, design evidence, and tool read-back must agree; otherwise identity remains unknown and flashing stays blocked.
- **Current device state:** stable physical identifier, USB VID/PID and serial number when present, observed ports, current firmware identity/version if it exposes one, partition table and security/read-protection observations where readable, boot log, and current functional behavior.
- **Backup and recovery plan:** full address-range flash dump to a timestamped `.bin` plus SHA-256 where supported, a separately identified NVS readout where its partition can be established, exact restore command/offset plan, and an explicit limitations statement. The statement must cover read protection/encryption, secure boot or flash encryption, unknown/custom bootloader and partition layouts, efuses, lack of external reset/boot controls, device-specific secrets/calibration, and the possibility that overwriting the only working configuration or communications path is not recoverable from the dump alone. Failure or uncertainty is recorded honestly and blocks F4 unless Daniele knowingly authorizes the documented limitation.
- **9-key matrix:** row count, column count, exact GPIO for every indexed row/column, connector mapping, every populated `(row,column)` / `MX-rr-cc`, and continuity results.
- **Diodes and pull-ups:** orientation at every populated position, recorded as anode-to-row/cathode-to-column or anode-to-column/cathode-to-row, continuity/diode-test evidence, pull-up location/value, and measured idle/pressed expectations. Input-only GPIO34–39 require external pulls on applicable ESP32 variants.
- **Power:** USB-only or external regulated supply, board regulator/source, common ground, current limit, and confirmation that two supplies will not back-feed each other.
- **Hosts:** exact flashing workstation and BLE pairing host—Windows build/adapter/driver or Linux distribution/kernel/BlueZ/adapter—so installer, pairing, bonding, reconnect, and HID evidence match reality.

Gate evidence must also reconcile the 9-key board against flash pins, strapping pins, UART0, antenna keep-out, and all non-matrix consumers. F1 produces a reviewed board capability record, wiring record, backup inventory, and recovery plan; this document intentionally supplies no guessed identity or pin assignment.

## 7. Roadmap to first physical demo

This is an implementation roadmap, not a calendar estimate. Each stage produces a deliverable and has a verification gate; passing a software-only gate never implies permission to operate on hardware.

| Stage | Implementation deliverable | Verification gate | Hardware/write boundary |
|---|---|---|---|
| F0 — architecture (done) | This plan defines installer, firmware, protocol, preservation rules, capability mapping, and acceptance sequence | Document review confirms every required installer/application capability has an owner and test milestone | Documentation only; no device operation |
| F1 — G0 identification of the 9-key board | Record exact chip family/revision, flash size, board design, USB/download-mode design, wiring, current firmware/state, and security/layout observations; acquire and hash full-flash `.bin` and NVS read-back where supported; write the restore procedure and recovery limitations | Daniele reviews the board capability/wiring record, backup inventory, and recovery plan; conflicts or unreadable data remain explicitly unknown | **Identify/read/backup only. No flash, erase, overwrite, config upload, or authorization implied. Never touch the 12-key board** |
| F2 — Firmware v0, built but not installed | Reproducible, compiled, checked-out build with safe boot that leaves unconfigured GPIO high-impedance; section 4 serial protocol; runtime rows/GPIO/populated-position configuration; scan/debounce; A/B NVS config/actions persistence; BLE HID output | CI/host tests validate build artifacts and manifest, schema/parser corpus, pin-policy fixtures, interrupted NVS commits, scan/debounce simulation, HID report bytes, and safe-boot behavior | No hardware yet |
| F3 — Desktop installer v1 | Existing PySide6 app gains port detection, automatic identity read-back, manifest-based compatible-build selection, mandatory pre-flash full/NVS backup workflow, guided `esptool` progress/verification/structured errors, and post-flash re-enumeration/reconnect | Automated tests use fake serial ports, captured F1 identity data, manifest/error fixtures, simulated `esptool` output, corrupt downloads/hashes, backup failures, and disconnect/reconnect cases; a read-only pass may repeat F1 observations | Write controls remain locked; no real flash is part of this gate |
| F4 — first authorized flash to the 9-key board | After Daniele separately authorizes the exact device and reviewed recovery plan, run the installer backup check, compatible build selection, flash, verification, reconnect, and a section 4 serial configuration round-trip | Preserve installer log, artifact/manifest hashes, pre-flash backup hashes, verification result, post-flash identity/version, and upload/read-back equality | First write occurs only after separate explicit authorization immediately before this stage |
| F5 — configure and test the 9-key board | Keyboard DM edits rows/columns/GPIO/scan mode/populated positions, uploads without reflashing, streams each physical press as row/column/switch-ID, and saves typed actions persistently to NVS | Press and release every populated position; compare live events to the F1 wiring record; reject invalid configs; power-cycle and confirm generation/hash and actions persist; assignment updates do not invoke `esptool` | Authorized device only; no further firmware flash is needed for configuration/action changes |
| F6 — acceptance | Run exactly: **Keyboard DM -> firmware install -> matrix configuration -> save to ESP32 -> Bluetooth keypress -> change assignment WITHOUT reflashing -> still works** | Evidence includes installer verification, config generation/hash, correct Bluetooth result before and after assignment change, power-cycle persistence, reconnect behavior, and no stuck/duplicate key | Acceptance is on the 9-key board; any repeat flash still requires explicit authorization |
| F7 — later 75-key reuse | When soldering is complete, identify/approve the 75-key electronics and select from the same compatible firmware builds; only the runtime configuration is new | Validate all populated positions, rollover, scan timing, GPIO safety, persistence, and BLE behavior against the completed board's reviewed wiring record | A new device-specific identity/backup/authorization gate applies; no 12-key involvement |

The 9-key keyboard is physical device #1. The unfinished 75-key keyboard is a later reuse milestone, demonstrating that board geometry and actions are configuration rather than firmware forks. No flashing is permitted without Daniele's separate explicit authorization, and the 12-key board remains entirely off-limits.

## 8. Future extensions

Layers, macros, and RGB are out of scope through F6, but the boundaries above avoid a redesign:

- **Layers:** extend `actions` values with a layer-switch action and add a top-level `layers` object keyed by stable layer ID. Matrix key IDs stay unchanged; dispatcher state selects the action map.
- **Macros:** add a typed `macro` action referencing a top-level `macros` table of bounded, validated steps. Execution belongs behind the dispatcher queue, not inside the scanner.
- **RGB:** add a top-level `rgb` configuration and board capability fields; an RGB task consumes key/state events without owning matrix GPIO or BLE.

`protocol_version` versions framing/command semantics; `config_schema_version` versions persisted meaning. Unknown optional data lives under namespaced `extensions`; required future features must declare a minimum supported schema/capability and be rejected cleanly by older firmware. Version/capability negotiation happens before upload, and migration creates a new NVS generation while retaining the old slot. This lets later desktop releases add all three features without changing `MX-rr-cc`, existing typed action objects, or the serial framing.

## 9. Risks and open questions

| Risk / open question | Required control or decision | Gate |
|---|---|---|
| The exact 9-key chip, module, board revision/design, flash size, USB interface, power path, firmware, and wiring are unconfirmed | F1 records markings, design evidence, automatic read-back, current behavior, and measurements; disagreement is “unknown,” never a guessed match | F1 blocks F4 |
| Download-mode entry may fail on a board without automatic DTR/RTS bootloader control | Confirm the schematic/buttons first. Manual procedure template: (1) close every serial monitor; (2) connect USB and select the recorded port; (3) press and hold **BOOT/IO0**; (4) while holding it, tap and release **EN/RESET**; (5) keep holding BOOT/IO0 while the tool begins connecting; (6) release BOOT/IO0 only after the tool reports a connection. If there is no EN/RESET control, hold confirmed IO0 low while power-cycling, begin connection, then release it after connection. Never short or press a guessed pin; adapt the labels only from the F1 board record | Procedure is documented at F1, simulated in F3, and used on the 9-key board only under F4 authorization |
| `esptool` automatic detection and a forced `--chip` value may disagree | Automatic detection is authoritative input, checked against board evidence and manifest. Do not retry with a forced family to make flashing proceed; expose the mismatch as a structured error and investigate cabling, download mode, bridge, and device identity | F1/F3 block F4 |
| Unknown, encrypted, read-protected, secure-booted, or custom-bootloader flash may be incomplete or unrestorable | Preserve raw output and security observations, hash every readable dump, export NVS separately only when its location is established, and state that a byte dump may not restore efuses, keys, calibration, encryption state, boot chain, or a lost proprietary config path. No “backup successful” claim without a verified readable range and restore plan | F1 review; explicit residual-risk authorization required for F4 |
| Existing running firmware may hold the serial port, reset repeatedly, change baud, or interfere with identity/backup | Close Keyboard DM monitoring and other port owners, record normal boot output first, then use the confirmed manual download-mode template above for ROM-level reads. Read failure is not permission to erase or write | F1; structured guidance in F3 |
| Windows USB-UART drivers, COM numbering, reset behavior, or port stability may change during automatic flashing | Record VID/PID/serial/location when available, match re-enumerated devices by stable identity rather than COM number alone, wait/rescan with a bounded timeout, distinguish driver/access/disconnect errors, and provide signed CH340/CP210x driver guidance for the identified bridge | F3 simulations; F4 real reconnect |
| Pre-flash backup could be skipped or confused with a backup from another board | Bind backup metadata and hashes to the stable physical/USB identity, chip read-back, flash size, timestamp, and manifest; disable write until the current session's backup outcome and limitations are acknowledged | F3/F4 |
| A corrupt or incompatible firmware artifact could be selected | Registry matching requires exact chip family/target and supported flash size, verifies SHA-256 before use, and refuses unknown/ambiguous cases; no compatibility override | F2 manifest production; F3 selection tests; F4 final check |
| The current desktop lacks `scan_mode` and `diode_direction` | F5 decides whether these are additive project-v3 matrix fields or a separate explicit deployment record; they may not be inferred | F5 |
| The desktop GPIO policy (`{6,7,8,12,15}` reserved and input-only `{35,36,37,38,39}`) is not a complete cross-family board policy | F1 produces the authoritative per-board descriptor; desktop and firmware validation must agree and may be stricter than the generic policy | F1/F2/F5 |
| Full NKRO depends on one correctly oriented diode per switch and the normal bitmap report | Verify all diode orientations, multi-key combinations, and host acceptance; boot protocol remains 6KRO | F1 measurements; F5/F6 behavior |
| Pairing security, bonded-host count, advertising timeouts, and recovery UX vary by host | Record the approved host and test pairing, reboot, disconnect, reconnect, assignment changes, and bond reset behavior | F4–F6 |
| Scan/debounce timing, BLE parameters, and diagnostics rate limits need physical measurement | Treat current defaults as hypotheses; retain 115200 8N1 initially and capture timing/error counters under real presses and chords | F5/F6 |
| NVS capacity may be inadequate | Size two 2–4 KB configuration slots, metadata, NVS overhead, action profiles, and BLE bonding with margin against the F1 flash/partition record | F2 design; F4/F5 verification |
| The 75-key topology, GPIOs, diode orientation, pull-ups, and continuity remain unknown while soldering continues | Defer it to F7 and apply a fresh device-specific identity/wiring/backup/authorization gate; no value in this plan is its pin assignment | F7 |
| Text entry is layout/locale sensitive and absent from the current typed-action model | Define literal-text versus HID-usage semantics separately; do not include it in F6 acceptance | Future |
| The 12-key board could be confused with an eligible target | It is wholly excluded from F0–F7: do not connect, inspect, back up, erase, flash, or configure it as part of this work | All stages |
