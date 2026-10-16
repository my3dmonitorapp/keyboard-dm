# M1 — Visual Matrix Builder (Track A, desktop app)

Status: APPROVED 2026-10-16. Baseline: `main` @ 832e733, 174 tests passing.
Branch: `feature/matrix-layout-editor` (from main). No force-push, no history rewrite.

## Objective
Support arbitrary custom keyboard wiring, end to end in the PySide6 app:

1. User enters electrical matrix dimensions (rows × columns).
2. User defines which intersections contain switches (rows may have different key counts).
3. App auto-generates a graphical keyboard layout from the populated switches.
4. Per-key editing: width (half-un step: 0.5–6.25u), position, display label.
5. Independent ESP32 GPIO pin assignment per row and column, with electrical validation.
6. Existing shortcut, modifier, media-key and profile editors must continue to work.
7. Save + reload complete configurations (layout geometry, switches, widths, labels, pins) without losing any existing assignments.
8. Simulate matrix key presses/releases and highlight the corresponding visual keys.

The user's 75-key board is proposed as 5 rows × 15 cols — an EXAMPLE ONLY. Nothing may be hardcoded to 5×15, 75 keys, or any specific GPIO map. No hardware assumptions; pins are user-assigned data, validated for internal consistency only.

## Scope guardrails
- PySide6 app + tests only. No firmware, no flashing, no hardware.
- No new pip dependencies without explicit approval (reuse pure-Python + PySide6).
- Preserve all S1/S1.1/S1.2 functionality: built-in 6/9/12/75 layouts, custom grids, profiles v2, projects, action editor, simulated device, smoke entrypoint.
- Data model must be additive: existing project/profile file versions remain loadable unchanged.
- All new state must be serializable into the project/save format with a versioned schema (bump version, add fields; legacy files load with defaults).

## Task breakdown (max 8 Codex tasks total for M1)
- **M1-T1 — Matrix data model (core, no GUI):** `MatrixConfig` model: rows×cols dimensions, switch occupancy (set of (row,col) cells), per-key widths (half-u integers, i.e. width_u = n/2 with min 0.5, max 6.25), display labels, per-row and per-column GPIO pin assignments (int or None). Validation: cell bounds, no duplicate pins across rows+cols, pins in a configurable allowed range (default 0–39, standard ESP32), width bounds. Serialization to/from JSON dict (stable field names). Unit tests. Integrates with existing layout_model as a new layout source type "matrix" alongside current grid/custom.
- **M1-T2 — GUI matrix setup + auto layout generation:** UI to enter dimensions (rows, cols), toggle per-cell switches (click on grid cells, rows can be sparse), and generate the visual keyboard from populated switches (row-major ordering for default labels/IDs). New layout source selectable in the same place custom grids are created. Headless/GUI tests.
- **M1-T3 — Per-key editing in GUI:** selected-key panel edits width (dropdown/entries at 0.5u steps up to 6.25u), row/col position (or x/y offset consistent with existing geometry model), display label. Visual redraw respects widths and gaps. Tests incl. offscreen.
- **M1-T4 — GPIO pin assignment UI + validation:** per-row and per-column pin fields in a matrix pinmap panel; live validation messages (conflicts, out-of-range); invalid assignments blocked/warned, never silently accepted. Model-level validation from T1 drives it. Tests.
- **M1-T5 — Persistence v3:** bump project/profile save format to v3 (or matrix-additive extension): store matrix config (dimensions, switches, widths, labels, pins) alongside existing assignments keyed by stable key IDs. Lossless: save v3 → reload → everything identical; v2 files load unchanged; all existing assignments survive a convert. Migration from legacy default where matrix keys map by stable IDs. Tests: roundtrips + migration + assignment-preservation.
- **M1-T6 — Matrix press/release simulation + highlight:** simulated device can inject matrix events (row,col) or key events → the matching visual keycap highlights (press state + release). Use existing simulated device where possible; deterministic, testable headlessly. GUI highlight tests + simulation tests.
- **M1-T7 — Integration sweep + docs:** end-to-end smoke: create 5×15 example (or arbitrary 3×4) matrix → populate sparse rows → edit widths/labels/pins → simulate presses → save → reload → verify state; existing shortcut/modifier/media editors verified on matrix keys; smoke `--smoke` entrypoint extended as appropriate; update docs (desktop-app.md, product-specification.md matrix section, changelog, roadmap). Full regression (all 174+ tests green).
- **M1-T8 — Reserve:** corrections/blockers only.

Budget: 8 Codex tasks max (0 completed at start), 2 correction attempts per task, 90 min total execution. One Codex job at a time.

## Per-task Codex rules (restate in every prompt)
- Work in /home/daniele/projects/keyboard75 on branch feature/matrix-layout-editor.
- Use `.venv/bin/python -m pytest -q` for tests (system python not on PATH).
- Do NOT commit; leave changes uncommitted for reviewer verification.
- Final answer: max ~15 lines — what changed (files), test count + result, any deviations/assumptions, known issues. No file dumps, no long logs.
- Keep existing code style; additive changes only where possible.
