# Firmware foundation design

## Shared C11 core and HAL boundary

The shared core is strict C11 with standard-library headers only. Fixed-size
models make ownership and maximum memory use explicit, avoid allocator policy
at the platform boundary, and let the same validation and serialization code
run in host tests and on either ESP32 family.

`kb_hal_ops_t` is the only platform boundary. It contains pin direction,
write/read and input-pulldown operations; a monotonic-millisecond clock;
config-A, config-B, and metadata storage; the LF/JSON console transport; and
BLE report transport. Every operation returns a typed HAL error. An opaque
context keeps implementations resettable and avoids hidden global state. The
host fake provides one-shot storage/transport failures, corrupted pin reads,
and positive or negative clock jumps.

Chip pin legality is intentionally not compiled into shared code. A
`kb_hal_probe_t` supplies the available pin count plus board-approved reserved,
input-only, and external-pull-up-required lists. This is the separation point
between general validation and the F1-confirmed board descriptor.

## Configuration representation

The in-memory model retains the F0 device-envelope meaning:

- protocol/config schema versions, chip class, generation, and CRC32;
- a matrix up to 16 by 16;
- indexed row/column pins, scan mode, and pull-up source;
- a sparse populated-cell list with canonical `MX-rr-cc` identities;
- board-wide or per-switch diode direction; and
- exactly one nullable typed action for every populated cell.

Actions match the desktop v2 vocabulary without field renaming: `key`,
`shortcut`, `media`, and `modifier`. The C model additionally resolves each
name to its HID usage or modifier bit. It covers keyboard/keypad usages
`0x04..0x7e`, sided modifiers `0xe0..0xe7`, and the desktop's six consumer
usages. `legacy` is intentionally rejected for activation because it has no
deterministic HID meaning. Text and macros remain future schema extensions.

Canonical JSON is compact, uses a fixed field order, and emits populated cells
and action keys in row-major order. CRC32 is the IEEE reflected CRC-32 over that
canonical UTF-8 object with the `crc32` member omitted; the stored decimal
`crc32` member is then appended. This avoids a self-referential checksum and
makes semantically identical in-memory ordering produce identical bytes.
Schema-v1 accepts direct UTF-8 strings but only ASCII `\u` escapes. Non-empty
`extensions` are conservatively rejected because this fixed model cannot
preserve unknown JSON losslessly for CRC round trips.

Validation accumulates structured `{code, field, index, related_index}` items
instead of returning a bare boolean. It checks versions, geometry, pin counts,
pin range/capability, uniqueness, populated bounds/duplicates, scan/diode
pairing, typed HID usages/modifiers, external pull-up requirements, and CRC.

## Protocol boundary

`kb_protocol.h` freezes the F0 LF-framed command names, limits, envelope field
names, protocol version, parse result types, and the parse/apply signatures.
The incremental serial router, transfer staging, response generation, and
command application remain F2-T3 work. The foundation does implement the
bounded device-config JSON parser needed to validate the checked-in protocol
fixture corpus; it parses into a temporary config so failures cannot partially
overwrite caller output.

## Target separation and framework decision

`targets/esp32/` and `targets/esp32c3/` remain separate because GPIO
capabilities, reserved resources, BLE/transport setup, build target, partition
layout, and SDK configuration differ by chip family. T4 owns those adapters and
must provide only `kb_hal_ops_t` and a reviewed `kb_hal_probe_t` to shared code.

The approved F0 recommendation is ESP-IDF 5.x rather than Arduino. The final
framework/version decision, SDK configuration, and any Arduino compatibility
choice live exclusively in each target integration/build layer, never in the
shared core. This task installs no cross toolchain and produces no target code.

## F0 discrepancies and conservative choices

The requested `docs/firmware/f0-architecture.md` is absent from this branch at
its `main` base. The approved document was read from the existing
`feature/f0-architecture` ref. That document currently has sections 1 through
9, not the referenced sections 10 and 11.

The document calls the integer wire protocol version `1`, while this task calls
the release “JSON-over-LF v0.1.” The header therefore exposes both the display
string `0.1` and active integer version `1`.

F0 shows a board-wide diode-direction string and omits config generation/CRC
from its example envelope. This task explicitly requires board-wide or
per-switch direction plus generation and CRC32. Schema v1 preserves the F0
string form for board-wide direction and adds an `MX-rr-cc` keyed object for
per-switch direction, followed by top-level decimal `generation` and `crc32`.
It also makes `pull_up_source` explicit rather than inferring whether the read
side has external resistors.

F0 mentions CRC plus SHA-256 for persistence/transfer. This foundation provides
the required CRC32 for canonical config integrity. Transfer SHA-256 remains a
protocol/storage implementation concern for T3 and is not silently replaced by
CRC32.

## Scanner and configuration governance state machines

The scanner configures only the selected drive side as an output, one line at a
time, and immediately returns it to high impedance. The opposite side remains
input-only. Sparse populated intersections alone own debounce state and emit
events; reads still cover every input line so the electrical scan is complete.
Debounce is time-based on both edges, defaults to 25 ms, and validates in the
inclusive 5–100 ms range. `switch_id` is the stable zero-based index in the
validated populated list; action translation remains downstream work.

Boot persistence uses canonical JSON in A/B slots and a CRC-protected metadata
record containing active and last-good slot/generation. A commit writes and
reads back the inactive slot before publishing metadata, so a failed or partial
slot write cannot change the active generation. Recovery consumes the
last-good pointer: a second recovery at that generation is a no-op. This
generation rule deliberately prevents A/B/A oscillation (the ABA case); a new
successful config commit establishes a new last-good pointer. Empty storage is
`NO_CONFIG`, while present-but-invalid data or corrupt metadata enters
`SAFE_MODE`. Neither state invokes scanner initialization or GPIO operations.

Host persistence currently bounds a canonical config blob at 8192 bytes, which
matches the fake HAL slot capacity. Transfer hashing, protocol parsing, action
dispatch, scan settling delays, and target-specific pull-up setup remain later
integration work.
