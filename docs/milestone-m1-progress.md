# M1 Progress (living document)

Baseline: main 832e733, 174 tests. Branch: feature/matrix-layout-editor.
Budget: 8 Codex tasks (0 used), 2 corrections/task, 90 min (0 min used). Start 2026-10-16.

- [x] M1-T1 — done (189 tests, verified: sparse cells, pin conflicts, roundtrip, to_layout) matrix data model + validation + serialization
- [x] M1-T2 — done (191 tests) GUI matrix setup + auto layout generation
- [x] M1-T3 — done (193 tests) per-key editing (width/position/label)
- [x] M1-T4 — done (196 tests) GPIO pinmap UI + live validation
- [x] M1-T5 — done (202 tests) persistence v3 (lossless save/reload, v2 migration)
- [x] M1-T6 — done (205 tests) matrix press/release simulation + keycap highlight
- [x] M1-T7 — done (206 tests, smoke green) integration sweep + docs + full regression
- [x] M1.1-A — done (211 tests) per-key visual offsets, complete width presets, occlusion-aware rendering
- [x] M1.1-B — done (233 tests) ESP32 GPIO safety validation and safe pin suggestions
- [x] M1.1-C — done (235 tests, smoke green) key inspector discoverability + final integration regression
- [ ] M1-T8 reserve

Log:
- 2026-10-16: repo recovery verified (clean, 174 tests), branch created, brief written. M1-T1 dispatched.
- 2026-10-16: T1 verified + committed (7fb7e60). Budget: 1/8 tasks.
- 2026-10-16: T2 verified + committed (56ce62d). Budget: 2/8 tasks.
- 2026-10-16: T3 verified + committed (c9ad7ec). Budget: 3/8 tasks.
- 2026-10-16: T4 verified + committed (d9b50d1). Budget: 4/8 tasks.
- 2026-10-16: T5 verified (independent 70-key 5x15 save/load round-trip, 3 typed action types preserved) + committed (4d9b6e8). Budget: 5/8 tasks.
- 2026-10-16: T6 verified (independent device press/release + empty-cell rejection) + committed (a96809e). Budget: 6/8 tasks.
- 2026-10-16: T7 verified (independent --smoke exit 0 + 206 tests) + committed ($(git rev-parse --short HEAD)). Budget: 7/8; 1 reserve held unused.
- 2026-10-16: M1 complete. Branch pushed, PR open for review: https://github.com/my3dmonitorapp/keyboard-dm/pull/1 (not merged). 206 tests, smoke exit 0. Budget used: 7/8 tasks, 1 reserve unused, no correction spend.

## M1.1 final state

235 tests pass; `.venv/bin/python -m desktop_app --smoke` exits 0. Since M1,
matrix keys gained independent half-unit visual offsets, the full 1u–6.25u width
preset set, occlusion-aware rendering, ESP32 GPIO safety validation, and a
highlighted selected-key inspector with cell identity and an appearance reset.
Matrix save/load/save/reload is covered at both `MatrixConfig` and `Layout`
layers, including assignment preservation and v1/v2 compatibility. PR #1 is
open, non-draft, cleanly mergeable, and not merged.
