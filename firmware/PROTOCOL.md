# Keyboard DM serial console protocol v0.1

This is the wire specification for the implementation in
`firmware/shared/src/kb_protocol.c` and `firmware/shared/include/kb_protocol.h`.
It documents implemented behavior, including current limitations; declarations
reserved in the header are not treated as working commands.

## Transport and framing

- Each request is one UTF-8 JSON object terminated by LF (`0x0a`). A CR directly
  before LF is tolerated. The incremental reader waits for LF before parsing.
- The maximum request object is 1536 bytes, excluding the terminating LF. Once
  that limit is exceeded, bytes are discarded through the next LF and the frame
  fails.
- The top-level object permits only `id`, `cmd`, `params`, `version`, and
  `crc32`. `id` and `cmd` are required JSON strings; `params` is a required JSON
  object. The implementation stores at most 64 bytes of `id` plus its terminator
  and at most 31 bytes of command name. Unknown fields are rejected. Duplicate
  keys are not explicitly rejected and lookup selects the first match, so they
  are invalid client input and must not be sent.
- Requests use `{"version":"0.1","id":"client-id","cmd":"version","params":{}}`.
  The `version` field may instead be integer `1`, or may be omitted for current
  compatibility. Clients should send it explicitly.
- A success response is
  `{"id":"client-id","ok":true,"result":{...}}`. A command error is
  `{"id":"client-id","ok":false,"error":{"code":"...","message":"command rejected","details":{}}}`.
  Parse failures cannot safely recover an ID and therefore respond with an empty
  `id`. The shared response builder does not append LF; the transport adapter is
  responsible for framing outbound JSON.

JSON numbers accepted by this protocol are unsigned decimal integers. Parameter
objects are strict: fields not listed for that command are rejected. Empty
parameter objects must be exactly `{}` semantically. Strings used for IDs,
command names, upload IDs, phases, encodings, sources, and confirmation tokens
must not require JSON backslash escapes; the implementation rejects escapes in
those extracted values.

## CRC32

CRC values are unsigned decimal representations of standard CRC-32/IEEE as
implemented by `kb_crc32` (polynomial `0xedb88320`, initial/final XOR
`0xffffffff`). The integrity check used by v0.1 is the configuration-upload CRC:
it covers the exact decoded UTF-8 configuration bytes, before parsing, and is
required in the `start` request. Commit requires both the declared byte length
and this CRC to match. A `config_commit` request may supply a replacement CRC.

The top-level envelope field `crc32` is currently allow-listed but is not read or
verified. Clients must not rely on it and should omit it. The exported
`kb_protocol_line_crc32()` helper computes a CRC over a supplied JSON prefix plus
a closing `}`, but the v0.1 parser does not connect that helper to the envelope.
This is distinct from the embedded `crc32` in canonical configuration JSON,
which is checked by configuration validation, and from the enforced upload-byte
CRC described above.

## Commands

### `version`

Request params: `{}`.

Success result: `{"protocol":"0.1","active_protocol":1}`.

### `config_upload` and `config_commit`

Uploads are staged in memory, one at a time, with a maximum decoded size of 8192
bytes. A raw chunk is at most 1024 bytes and is base64 encoded. Use these steps:

1. Start with
   `{"phase":"start","upload_id":"u","encoding":"base64","total_bytes":123,"crc32":123456789}`.
   `total_bytes` is 1..8192 and `upload_id` is at most 32 bytes. Starting replaces
   any prior staging transfer. The result is
   `{"accepted":true,"next_seq":0}`.
2. Send chunks in strict order beginning at zero:
   `{"phase":"chunk","upload_id":"u","seq":0,"data":"..."}`.
   The ID must match, base64 must be valid, and decoded bytes may not exceed the
   declared total. Each success returns `accepted:true` and the incremented
   `next_seq`. Gaps and duplicates return `bad_state`; they are not idempotently
   acknowledged.
3. Commit either with `config_upload` params
   `{"phase":"commit","upload_id":"u"}` or with the separate `config_commit`
   command and params `{}`. `config_commit` also accepts an optional unsigned
   `crc32` override and an allow-listed `upload_id`; the implementation does not
   compare that command's `upload_id` to the staged ID. Commit verifies length
   and upload CRC, parses and validates the configuration, then applies it using
   the boot/NVS A/B path. Success is
   `{"generation":N,"status":"validated"}`.

Abort with `config_upload` params `{"phase":"abort","upload_id":"u"}`. It
clears the active-transfer flag and returns `accepted:true`; the implementation
does not compare the abort ID. A failed CRC or invalid configuration also ends
the transfer without changing the active configuration.

### `config_get`

Params may be `{}`, `{"source":"active"}`, or
`{"source":"last_good"}`. Omitted source means active. Active success embeds
the canonical object directly as `{"config":{...}}`. No chunked download is
implemented. `last_good` currently returns `not_found` even when boot metadata
has a last-good generation.

### `config_status`

Request params: `{}`. Success is
`{"state":N,"active_generation":G}`, where `state` is the numeric
`kb_boot_state_t`: 0 no config, 1 loading, 2 valid, 3 recovering, or 4 safe mode.
`boot_status` is an implemented alias with the same request and response.

### `key_event`

Params: `{"enabled":true}` or `{"enabled":false}`. Success echoes the resulting
boolean as `{"enabled":...}`. This toggles the protocol context flag only. The
current shared protocol and target console do not serialize unsolicited key
event frames, and event injection parameters are not accepted.

### `gpio_test`

Unavailable in v0.1. The name and argument storage are reserved in the public
header, but the parser does not recognize the command, so a wire request returns
`unknown_command`. No GPIO sampling, pull change, or activation is performed by
this protocol implementation.

### `factory_reset`

The only accepted params are
`{"confirm":"ERASE_CONFIG_AND_BONDS"}`. The implementation erases every HAL
storage slot: config A, config B, and configuration metadata. It then clears
active and last-good runtime configuration, disables matrix outputs, and returns
`{"accepted":true,"reboot_required":true}`. Despite the confirmation token's
name, the current store-slot enum contains no BLE bond slot, so this
implementation does **not** establish that platform BLE bonds were erased.

This is destructive on a running target and is not part of host testing or the
F2 workflow. The command string is only a confirmation token, not physical-board
authorization.

## Other declared names

`ping` is parsed with `{}` but reaches the `unsupported` response. `boot_status`
is implemented as noted above. `reboot` is declared in the header but, like
`gpio_test`, is not recognized by the parser. These are not usable v0.1
features.

## Versioning rules

- `"0.1"` is the human-readable protocol release and integer `1` is its active
  wire version. A supplied request version must be exactly one of those two
  representations; other values fail as `bad_version_or_envelope`.
- Framing/envelope/command semantic changes that break v0.1 clients require a
  new active wire version. Additions may use a new command or new version, but
  v0.1's strict parameter field sets mean new fields cannot silently be sent to
  old firmware.
- Persisted configuration has its own `protocol_version` and
  `config_schema_version`. Passing serial negotiation does not imply that a
  configuration schema is accepted; upload commit performs that validation.
- Clients should call `version` before other operations and must not infer
  support from constants present in a header.

## Error codes

| Wire code | Meaning |
|---|---|
| `invalid_command` | Empty/overlong/non-UTF-8/malformed JSON, bad params, or another parse failure not mapped more specifically. |
| `bad_version_or_envelope` | Missing/invalid envelope members, forbidden envelope field, or unsupported supplied version. |
| `unknown_command` | Command name is not in the parser's implemented command table. |
| `bad_state` | No active upload, wrong upload ID/sequence/data/length state, or another command-state failure. |
| `bad_crc` | Staged byte count or upload CRC did not match at commit. |
| `bad_config` | Uploaded/configured data could not be parsed, serialized, or validated. |
| `not_found` | Requested active/last-good configuration is unavailable. |
| `bad_params` | Apply-time confirmation or required service state is absent; parse-time parameter errors normally map to `invalid_command`. |
| `hal_error` | Persistent-storage HAL operation failed. |
| `unsupported` | A parsed command has no apply implementation (currently `ping`). |

An output buffer that is too small produces the internal
`KB_PROTOCOL_APPLY_BUFFER_TOO_SMALL` result and no complete wire error object;
transport adapters must allocate for the largest documented response.
