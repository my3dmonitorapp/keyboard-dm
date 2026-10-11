# Milestone S1.2 Brief — Complete Keyboard Action Editor (2026-10-11)

Status: Approved by owner. S1.1 passed visual review. Builds on S1.1 (commits 6893f1a→341f1f1, all verified: 63/63 tests).

## Goal
A universal programmable-keyboard configurator where any physical key can be assigned a real keyboard action or shortcut — a proper typed action system, not arbitrary text — ready for future ESP32-S3 USB HID and BLE HID firmware.

## Architecture freeze
- Python + PySide6, same files as S1.1: desktop_app/{app,layout_model,layouts,profile,project,device,__main__}.py + new action module.
- Dark theme, simple single-window layout, 250px right-hand inspector — preserved.
- SimulatedESP32S3Device stays the only device (follows active project).
- v1 JSON profiles: read, migrated, NEVER discarded or corrupted.
- No firmware, no flashing, no GPIO/matrix assumptions, no macro recording, no layers implemented yet, no system package installs, vendor reference files untouched.

## 1. Structured action model (new desktop_app/action.py)
Typed, serializable action objects with stable HID-oriented identifiers:
- SINGLE_KEY: A–Z, 0–9, Enter, Escape, Tab, Space, Backspace, Delete, F1–F24, Home/End/PageUp/PageDown/Insert, Print, Pause; arrows Left/Right/Up/Down and other standard keys. Left/right distinguished where HID distinguishes (L-Shift, L-Ctrl, etc.).
- MODIFIER: L-Ctrl, R-Ctrl, L-Shift, R-Shift, L-Alt, R-Alt, L-Super (Windows), R-Super. Must carry key-down/key-up semantics (HID modifier bit 0x01..0x20, usages 0x01–0x06).
- SHORTCUT: 1..4 modifiers (explicit left/right variants) + exactly one main key (covered by SINGLE_KEY set). Human-readable label like "Ctrl+Shift+S".
- MEDIA (consumer HID, separate domain): Volume Up (0xE9), Volume Down (0xEA), Mute (0xE2), Play/Pause (0xCD), Next Track (0xB0), Previous Track (0xB2).
- Each action: stable id string (e.g. "key:a", "mod:lctrl", "combo:ctrl+shift+key:s", "media:vol_up"), human label, typed fields, to_json()/from_json(), validation (reject unknown ids/keys, shortcut missing main key, modifier-only with 0 modifiers, mixed media in combo, >4 modifiers).
- Clean extension interface: an Action registry/protocol so future macros (ACTION_TYPE_MACRO placeholder) and layers can plug in without changing profile v2 shape (type field is a string namespace). Do NOT implement macros/layers.

## 2. Profile version 2 + safe v1 migration (desktop_app/profile.py)
- PROFILE_VERSION = 2. Profile = {profile_version: 2, key_count, keys: {<key_id>: {assignment: <Action json>}}}.
- Save: typed actions as JSON (type + fields).
- Load: v2 loads directly. v1 loads by migrating each string assignment: map known text forms (e.g. "A", "Ctrl+C", "F5", bare labels) to typed actions via a deterministic parser; anything unparsable keeps the raw text in a LEGACY action (type "legacy", raw field) — NEVER dropped, displayed as-is, re-saved intact.
- Reject: wrong/unknown profile_version (other than v1), bad key counts, invalid action payloads → raise ProfileError with a clear message (GUI shows it; S1.1 status-bar behavior preserved).
- Per-key-ID, size-agnostic (6/9/12/75/custom), per-project independence unchanged (project.py stays compatible).

## 3. GUI action editor (desktop_app/app.py inspector)
Replace the plain assignment QLineEdit with:
- Action-type selector (QComboBox): Single key / Shortcut / Modifier / Media.
- Single key: dropdown of all supported single keys (letters, digits, named, F-keys, arrows…) → label on keycap.
- Shortcut: 8 modifier checkboxes (L/R Ctrl/Shift/Alt/Super) + main-key dropdown (same key set); live combo label; manual selection always works. Optional press-to-record: if a native key-capture widget is reliable use it, but MUST provide the manual path as the guaranteed method (OS may intercept combos).
- Modifier-only: selecting a pure modifier (type=Modifier) uses the same checkboxes/keys (one modifier, or a named L/R modifier) with down/up semantics shown in label.
- Media: dropdown of the 6 media functions; stored in the separate media domain.
- Keycaps show the readable label (truncate smartly; tooltip full label). Empty key = "—" (no action).
- Edit existing: selecting an assigned key populates the controls from its stored action; changing type resets controls; Apply writes the action; a separate "Clear" removes the action.
- Works on 6- and 9-key layouts (inspector compact, no overflow).
- S1.1 behaviors preserved: unsaved-changes guard, save/save-as/open, status bar, provisional strip, layout switching.

## 4. Device integration (desktop_app/device.py)
- SimulatedESP32S3Device accepts structured actions: send_key_assignment(key_id, action) serializes to a canonical wire string (label-based) and stores; get_key_states returns wire strings; also a round-trip helper get_as_action(key_id) → Action so future firmware transport can reuse the same code path.
- All existing connection/transport/USB-preferred behaviors unchanged.

## 5. GUI + tests + docs
- Headless smoke test (--smoke) extended: assign a shortcut via GUI on a small layout, save, reopen, verify in JSON.
- pytest matrix (brief's verification list): single keys; every modifier; modifier down/up representation; shortcut serialize/restore; multiple modifiers; media actions; v1→v2 migration (incl. unparsable→legacy preserved); invalid action rejection; GUI assign/edit/save/reopen; all S1+S1.1 regression (63 existing tests must keep passing or be ported); device round-trips with structured actions.
- docs/changelog.md entry; README launch notes unchanged.

## Task split (5 sequential, bounded)
- T1: action.py model + registry + serialization/validation + unit tests. (Profile still v1; app still uses strings internally — T1 is additive.)
- T2: profile v2 + v1 migration + profile tests.
- T3: GUI action editor + keycap labels + editing/clear + regression tests for GUI.
- T4: device structured-action integration + round-trip tests.
- T5: full migration of remaining legacy tests onto v2, GUI smoke, docs, final regression run.
Each task: commit only after coordinator re-runs the full suite; ≤2 corrections per task.
