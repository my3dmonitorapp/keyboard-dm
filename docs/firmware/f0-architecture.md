# F0 — ESP32 firmware architecture and first-physical-demo plan

Status: planning only  
Target: standard ESP32, ESP32-WROOM-32 DevKit class (exact board not yet approved)  
Scope through F5: BLE HID keyboard, USB-UART serial configuration/diagnostics, runtime-configured matrix, and persistent configuration. No GPIO allocation is made here.

## 1. System overview

Keyboard DM remains the source of truth for layout and typed assignments. It converts the existing project-v3 JSON into a device envelope and sends it over the development board's USB-UART CDC/COM serial path. The standard ESP32 scans the configured matrix and presents a BLE HID keyboard/consumer-control endpoint to the host PC. Reassigning keys or changing a validated matrix configuration updates NVS; it does not require reflashing firmware.

```text
+-----------------------+       USB cable / CDC serial       +------------------------+
| Keyboard DM desktop   | <================================> | ESP32-WROOM-32 class   |
| project v3 + profile  |   config, status, diagnostics      |                        |
| v2 typed actions      |                                     | NVS -> scan -> dispatch |
+-----------------------+                                     +-----------+------------+
                                                                            |
                                                                            | BLE HID
                                                                            v
                                                               +------------------------+
                                                               | Host PC                |
                                                               | Windows 11 or Linux    |
                                                               +------------------------+
```

“USB CDC serial” in this plan means the COM/tty serial interface exposed by a DevKit's external CH340/CP2102-class USB-UART bridge. A bare standard ESP32-WROOM-32 has no native USB peripheral. USB serial and BLE coexist: USB is configuration, diagnostics, and firmware loading; BLE is the only keyboard HID surface in F0–F5.

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

The scanner and state model retain every populated key independently. With one correctly oriented diode per switch, the internal state and normal-protocol HID bitmap support full N-key rollover for all 75 populated keys. The optional HID boot-protocol representation is necessarily 6-key rollover and is not the F5 acceptance path.

### Actions and HID reports

`actions` values reuse `profile.py` typed assignment objects without renaming fields: `{"type":"key","key":"a"}`, `{"type":"shortcut","modifiers":["lctrl"],"key":"s"}`, `{"type":"media","key":"vol_up"}`, `{"type":"modifier","modifier":"lshift","event":"down"}`, or `null`. The current `legacy` form is preserved by the desktop for migration but is rejected for device activation because it has no deterministic HID meaning. A future `{"type":"text","text":"..."}` dispatcher is reserved; macro objects remain a schema extension.

The BLE HID report map should expose (the Report ID byte is handled by the HID transport and is not counted in the payload sizes below):

- Report ID 1, normal keyboard input: a 17-byte payload consisting of one modifier byte and a 16-byte bitmap for Keyboard/Keypad usages `0x00..0x7f`. The current desktop key catalog ends at `0x7e`, so every supported non-modifier usage has one bit and the payload is below the 64-byte ceiling. This is the full-NKRO F5 path.
- Report ID 2, consumer-control input: a one-byte bitmap for the six current media actions, with two bits reserved and required to be zero.
- Boot keyboard compatibility: the conventional 8-byte modifier/reserved/six-key report when a host explicitly selects boot protocol. Overflow is reported rather than silently dropping arbitrary keys.
- Output report for host LED state (Caps Lock and similar), even if F5 only records it diagnostically.

On connect, disconnect, configuration swap, and reboot, the endpoint clears aggregate state so no key remains stuck. Initial pairing uses bonded BLE HID with the security mode proven on the selected ESP32/host combination at F2. With no display confirmed, the F2 baseline is an explicitly user-initiated discoverable window and the strongest ESP-IDF-supported no-display association approved at the hardware gate; unattended permanent discoverability is not acceptable. On disconnect, firmware re-advertises to the bonded host, first using a reconnect-oriented window and then a bounded general-advertising window. Bonds survive ordinary reboot/config updates and are erased only by an explicit pairing-reset/factory-reset action.

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

Geometry can prove bounds and the `MX-rr-cc` mapping; it cannot electrically discover diode orientation. Upload therefore proves only that the declared `scan_mode` and `diode_direction` agree. G0 must supply continuity/diode-test evidence for the declaration. F3 verifies sampled idle/pressed levels before HID dispatch is enabled.

The current `matrix_model.py` serializes `rows`, `cols`, `switches`, `row_pins`, and `column_pins`, but does not yet serialize `scan_mode` or `diode_direction`. F4 must add those as explicit project/deployment data or require an explicit upload-time selection; firmware must never infer them from visual layout, `key_widths`, or `key_visual_offsets`.

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

The GPIO strings above are placeholders to demonstrate schema only; an actual upload requires integers approved at G0. Mapping is semantic and lossless for device-relevant data:

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

Use Espressif ESP-IDF v5.x with its CMake/Ninja build flow and freeze the exact tested v5.x tag in F1 project metadata. It provides the supported ESP32 BLE HID stack, NVS, FreeRTOS/task control, partition configuration, logging, and `esptool` integration without Arduino framework abstractions. It also makes SDK version and configuration reproducible. Arduino/PlatformIO can accelerate sketches, but adds framework/version indirection and gives less explicit control over BLE callbacks, tasks, NVS recovery, partitioning, and reproducible official-example alignment; it is not recommended for this firmware baseline.

The baseline flashing workstation is Windows 11 x64 with Git, Python as installed/managed by ESP-IDF, the ESP-IDF v5.x tools environment, the selected board's signed CH340/CP2102 driver if Windows does not supply it, and either:

1. VS Code plus Espressif's ESP-IDF extension, configured to the frozen ESP-IDF installation; or
2. the matching “ESP-IDF Command Prompt/PowerShell” environment for command-line work.

The concrete board target is `esp32`; `<PORT>` is the owner-confirmed COM port and must never be baked into source:

```text
idf.py set-target esp32
idf.py build
idf.py -p <PORT> flash
idf.py -p <PORT> monitor
idf.py -p <PORT> flash monitor
```

`esptool.py --chip esp32 --port <PORT> ...` is the lower-level recovery/inspection path; normal builds and flashes should use `idf.py` so partition offsets come from the generated build metadata. On Linux, the equivalent port is typically `/dev/ttyUSB*` or `/dev/ttyACM*`, with distro-specific serial permissions, but Windows 11 is the documented F1 baseline unless G0 selects Linux.

The USB cable may remain attached while BLE is paired. They are independent surfaces: CDC/COM serial transports configuration and diagnostics over USB; BLE wirelessly transports HID keyboard/consumer reports. Standard ESP32 does not enumerate as a native USB keyboard.

## 6. Hardware verification gate and required information

G0 is a hard stop before F1 writes any device. The owner must provide and approve all of the following:

- **Exact module/board:** photographed markings and ordering identity (WROOM-32, WROOM-32E, WROVER, or other), development-board model/revision, flash size, PSRAM if any, and a trustworthy pinout/schematic. Also identify whether serial is via the module/board's external CH340/CP2102 USB-UART bridge or some other routed UART. The standard WROOM-32 does **not** have native USB pins; any claim that GPIO15/16 are “native module USB” signals a different device/board or documentation error and must be resolved before proceeding.
- **Sacrificial/approved test target:** a new board or a board explicitly verified and approved for Keyboard DM. **Never flash the existing 9-key or 12-key boards; their current firmware must not be overwritten.** Record a photo/serial label so the target cannot be confused.
- **First-test matrix:** row count, column count, exact GPIO for every indexed row/column, connector mapping, every populated `(row,column)` / `MX-rr-cc`, and continuity results. A small dedicated test matrix is acceptable.
- **Diodes:** orientation at every populated position, recorded as anode-to-row/cathode-to-column or anode-to-column/cathode-to-row, plus diode-test/continuity evidence and confirmation that all positions agree.
- **Pull-ups:** whether column (or selected read-side) pull-up resistors exist, their measured/marked value, whether they are external or internal, and idle/pressed voltage expectations. Input-only GPIO34–39 require external pulls.
- **Power:** USB-only or external regulated 3.3 V; board regulator/source, common ground, current limit, and confirmation that two supplies will not back-feed each other.
- **Host:** exact BLE pairing host and version—Windows 11 build/adapter/driver or Linux distribution, kernel, BlueZ, and adapter—so pairing, bonding, reconnect, and HID test notes match reality. Also confirm the OS of the flashing workstation if it differs from the Windows 11 baseline.

Gate evidence must also reconcile the selected board against flash pins, strapping pins, UART0, antenna keep-out, and all non-matrix consumers. Approval produces a reviewed board capability record and pin map; this document intentionally supplies neither.

## 7. Roadmap to first physical demo

Effort is expressed as tasks, not calendar dates.

| Stage | Work / rough effort | Exit criteria | Test method | Main risk |
|---|---|---|---|---|
| G0 — owner hardware-gate approval | 1) identify and photograph target; 2) document power/USB-UART; 3) continuity/diode/pull-up measurements; 4) approve capability record and pin map | Every item in section 6 is answered; target is not either protected 9-/12-key board; owner explicitly authorizes that target | Document review plus multimeter evidence; read-only chip identity/flash-size check if approved | Wrong board or wiring could damage hardware or erase valued firmware |
| F1 — serial/NVS bring-up, no BLE | 1) create ESP-IDF project/config; 2) serial ping/version/echo; 3) A/B NVS roundtrip and interrupted-write recovery; 4) safe-mode status | Reboot preserves a test blob; corrupted newest slot rolls back; serial replies match IDs; no matrix output and no BLE | Automated host request corpus, power-cycle, staged corruption/interruption test on approved target | USB-UART/flash-size mismatch; NVS partition assumptions |
| F2 — BLE HID proof, fixed key | 1) adapt official ESP32 BLE HID path; 2) define report map; 3) pairing/bonding/re-advertising; 4) fixed software-triggered test key | One explicit serial/test trigger produces exactly one press and release on approved host; bonded reboot/reconnect works; disconnect clears state | OS key-event viewer/text editor plus BLE logs; repeat connect/disconnect/reset cases; no matrix required | Host-specific security/report compatibility or duplicate/stuck reports |
| F3 — configured scanner/debounce | 1) immutable runtime matrix config; 2) electrical mode driver; 3) debounce; 4) NKRO state aggregation; 5) key-event diagnostics | Approved small matrix produces one correct press/release per populated cell, rejects invalid pin/mode configs, and passes multi-key/stuck-key tests | Logic analyzer/multimeter plus opt-in `key_event`; chord tests with BLE dispatch initially disabled, then enabled | Diode/pull-up polarity, noise, unsafe pin assumptions, scan timing |
| F4 — Keyboard DM upload integration | 1) deterministic project-v3/profile-v2 conversion; 2) add explicit electrical fields; 3) chunk/CRC/hash/retry client; 4) status and rollback UI | Desktop uploads and reads back the same device-relevant config; every `matrix.switches` cell maps to `MX-rr-cc`; assignment change survives reboot without flash | Golden envelope fixtures, malformed/interrupted transfers, device read-back/hash comparison, safe rollback | Current desktop lacks electrical fields; action/schema drift; serial disconnect mid-commit |
| F5 — first physical demo | 1) load approved wiring config; 2) pair approved host; 3) end-to-end key map; 4) change one assignment and re-upload | Physical switch emits the correct BLE keystroke; changing it in Keyboard DM changes the next BLE result after config upload/reboot if required, with no firmware flash; no stuck/duplicate key | Record before/after keystrokes, device generation/hash, power-cycle persistence, and a small simultaneous-key test | In-progress 75-key wiring; host BLE variability; demo wiring differs from recorded map |

The F5 matrix may be the approved small test matrix. Full 75-key validation is a later acceptance gate once construction and wiring are complete.

## 8. Future extensions

Layers, macros, and RGB are out of scope through F5, but the boundaries above avoid a redesign:

- **Layers:** extend `actions` values with a layer-switch action and add a top-level `layers` object keyed by stable layer ID. Matrix key IDs stay unchanged; dispatcher state selects the action map.
- **Macros:** add a typed `macro` action referencing a top-level `macros` table of bounded, validated steps. Execution belongs behind the dispatcher queue, not inside the scanner.
- **RGB:** add a top-level `rgb` configuration and board capability fields; an RGB task consumes key/state events without owning matrix GPIO or BLE.

`protocol_version` versions framing/command semantics; `config_schema_version` versions persisted meaning. Unknown optional data lives under namespaced `extensions`; required future features must declare a minimum supported schema/capability and be rejected cleanly by older firmware. Version/capability negotiation happens before upload, and migration creates a new NVS generation while retaining the old slot. This lets later desktop releases add all three features without changing `MX-rr-cc`, existing typed action objects, or the serial framing.

## 9. Risks and open questions

- The 75-key keyboard is still being wired. Final topology, GPIOs, diode orientation, pull-ups, and continuity are unknown; no value in this plan is a pin assignment.
- The exact ESP32 module, board revision, flash size, USB-UART bridge, and power path are unconfirmed. WROOM/WROVER differences can change usable pins and memory planning.
- The task's reference to `scan_mode`/`diode_direction` is ahead of the current `matrix_model.py`; F4 must decide whether these become additive project-v3 matrix fields or a separate explicit deployment record. They may not be inferred.
- The current desktop GPIO policy (`{6,7,8,12,15}` reserved and input-only `{35,36,37,38,39}`) is not a complete board datasheet policy and differs from the broader WROOM guidance that GPIO6–11 are flash-connected and GPIO34–39 are input-only. G0 must produce one authoritative per-board descriptor and align desktop/device validation.
- Full NKRO depends on one correctly oriented diode per switch and use of the normal bitmap report; boot protocol remains 6KRO. Host acceptance of the chosen bitmap report must be proven at F2/F3.
- Pairing association/security, bonded-host count, advertising timeouts, and recovery UX need an approved Windows 11 or Linux test target.
- Exact scan/debounce timing, BLE connection parameters, and diagnostics rate limits require measurement. Defaults in this plan are hypotheses, not acceptance values; the initial serial setting is fixed at 115200 8N1 for interoperability.
- NVS partition size must accommodate two 2–4 KB JSON slots, metadata, NVS overhead, and BLE bonding with margin on the confirmed flash device.
- Text entry is layout/locale sensitive and is not present in the current desktop typed-action model. Its future semantics (literal text versus HID usage sequence) need a separate decision.
- F5 may and should use a new small verified diode matrix if the 75-key board is unfinished. The protected existing 9-key and 12-key boards are never demo targets.
