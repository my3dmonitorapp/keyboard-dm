# Milestone S1.1 Brief — Universal Keyboard Configurator (2026-10-11)

Status: Approved by owner. Builds directly on S1 (commits 6893f1a→243feae, all verified).
Architecture stays: Python + PySide6, simple interface, simulated device, no firmware, no flashing.

## Product direction
The app is a UNIVERSAL programmable keyboard configurator — not limited to 75 keys.
Must support custom ESP32-based boards: 6, 9, 12, 75 and user-defined key counts.
Known hardware the user owns (do NOT assume protocol-compatibility between them):
- a 9-key keyboard on an "ESP32 Mini" (exact model TBD)
- a commercial 12-key keyboard (controller unknown)
- a handmade 75-key board (being soldered), planned ESP32-S3 → the primary target.

## T0 — Investigation results (ALREADY DONE by coordinator, verified headlessly on S1)
- GUI save works: changed assignment reaches the JSON file (K05→"Ctrl+X" verified on disk).
- Close + reopen + open profile restores assignments (verified).
- Defects to fix (verified in source):
  - D1: no unsaved-changes tracking; window closes silently with edits lost.
  - D2: load_profile does blind dict lookup keyed by current layout key IDs → unhandled
    exception when a profile's key set doesn't match the layout (crash-risk; no clear error).
  - D3: save silently accepts non-.json paths; no save-success feedback; static title;
    fixed 1240x520 window for all layouts.
  - D4: profile.py hardcodes KEY_IDS = K01..K75; persistence must support variable key
    sets while accepting version-1 files already on disk.

## Frozen decisions (do not change)
- Profile stays `profile_version: 1`. v1 files with 75 keys must load unchanged.
- Stable key IDs: within each layout, K01..KN row-major (N = key count). IDs are per-layout;
  switching layouts must NOT silently discard assignments (shared key IDs carry over;
  new keys default to "NONE").
- Assignment max length stays 32 chars.
- Simulated device (SimulatedESP32S3Device) must adapt to the selected layout's key set —
  no hardcoded 75.
- Saving a local JSON profile is NEVER "writing to hardware". UI and docs must say so
  explicitly. Device writes stay simulator-only.
- Existing S1 tests must keep passing (adapt where APIs intentionally change).
- `reference/`, `reference-file-list.txt`, `.venv/` stay git-ignored/untouched.
- User data (profiles/projects) lives in the repo's `profiles/` directory (git-ignored;
  create with a README note) — NOT outside the workspace (sandbox is workspace-write only).

## Tasks (5 bounded Codex tasks, in order)

### T1 — Persistence hardening (fixes D1, D2, D3, D4)
- profile.py: validate_profile(profile, key_ids=None): if key_ids given, the profile's key
  set must equal exactly that set (clear error listing additions/missing); if None, validate
  well-formedness only (non-empty IDs matching ^K\d{2,3}$, assignments str ≤32).
  create_profile(assignments) unchanged in shape (works for any key set).
  save_profile: require path ending .json (append if missing OR fail — pick one, document).
  Keep DEVICE field; when key set != 75, DEVICE may still be "/project-esp32s3" for
  compatibility (do not overthink).
- app.py: dirty tracking (assignment apply, load, layout switch mark dirty; save clears).
  Title shows current profile name + "(unsaved)". closeEvent: if dirty →
  QMessageBox Save/Discard/Don't save. Loading another profile or switching layout while
  dirty → same warning. Local-vs-hardware distinction in UI: status line "Local profile:
  <filename or 'none'> — (unsaved)" and keep separate "Device: connected (simulated)".
  Load error handling: catch ProfileError (and no KeyError possible now) → QMessageBox
  with the clear message. Save success → status-bar message "Saved to <path>" (also print).

### T2 — Multi-size layouts
- desktop_app/layouts.py: built-in layouts with stable IDs:
  L06: 6 keys, 3 cols x 2 rows; L09: 9 keys, 3x3; L12: 12 keys, 4x3; L75: current
  PROVISIONAL layout (15x5, row-major K01..K75). All keys 1u at integer (x,y) offsets.
  Layout carries name, key_count, cols, rows, label ("built-in" or provisional note).
- Custom layouts: function make_custom_layout(count, cols=None, rows=None) → grid
  (rows derived when omitted), stable IDs K01..KN. Validate sensible bounds (2..500).
- app.py: Layout menu (or top-bar combo) listing built-ins + "Custom..." dialog
  (QDialog: key count, optional cols/rows) → rebuilds window grid from the new Layout.
  Switching preserves assignments for shared key IDs; new keys → "NONE"; marks dirty;
  warns (unsaved) when dirty. Device re-sync: simulated device adopts the new key set.

### T3 — UI polish (keep simple, dark theme)
- Consistent simple dark stylesheet (window, keycaps, inspector, menus) — keep the look
  light on cognitive load: no animations, no decorations beyond what's listed.
- Keycaps: styled like small keycaps (rounded, subtle 3D edge), comfortable padding,
  clear selected-state highlight (distinct border/glow), hover state.
- Window auto-sizes to the layout: 6/9/12 keys → compact window; 75 → current size.
  Grid adapts; smaller layouts don't leave empty voids.
- Provisional banner: visibly SMALLER/less intrusive (e.g., thin status strip or small
  label), still clearly labeled when active; hidden when layout is user custom/final.
- Inspector: keep exactly as-is (key ID, position, assignment, Apply) — only styling.
- Status bar: local profile name/unsaved state + simulated-device status.

### T4 — Keyboard projects
- A project = a named profile file in repo `profiles/` directory containing the v1
  profile fields PLUS optional "layout" block: {name, key_count, cols, rows,
  per-key geometry overrides if provided}. v1 files without a layout block stay valid
  (opening them into a matching-size layout works; into wrong size → clear error).
- File menu: "Projects" submenu (or section): "New/Save project... " (name + layout;
  writes profiles/<name>.kb75.json), "Open project..." (list .kb75.json files from
  profiles/), auto-refreshed list; opening a project switches layout + assignments.
- Project metadata: name, key count, layout name/geometry. Projects are independent.
  Documented example projects to create in profiles/ (git-ignored? NO — projects dir is
  user data: gitignore the *.kb75.json and *.json in profiles/, keep folder + README).
- Simulated device must work with the active project layout after switching.

### T5 — Tests, smoke, docs, regression
- New tests (all offscreen): each built-in size constructs with exact key counts (6/9/12/75)
  and stable IDs; profile JSON round-trips for 6, 9, 12, 75 (save → load → equal);
  GUI-driven save + reopen for at least 6 and 75; layout-switch preserves shared-key
  assignments and does NOT crash on wrong-size profile load (clear error, no exception);
  dirty-close warning fires with dirty state, not without; device works on 6/12 layouts;
  v1 75 file loads unchanged (legacy compatibility).
- Existing S1 tests: all still green (adapt to API changes, keep coverage equivalent).
- --smoke: extend the existing flow to also switch to a 12-key layout, assign a key,
  save+reload a project, verify, clean exit 0.
- Docs: desktop-app.md updated (layouts menu, custom layouts, projects, save semantics,
  local-vs-hardware note, profiles/ dir, commands). changelog S1.1 entry. Roadmap:
  Track A status → S1.1 complete, S2 TBD.
- Final: full pytest run + --smoke + launch GUI headlessly with each built-in layout and
  report widget counts.

## Verification bar (coordinator enforces after each task)
- Independent test re-run, independent source-reading of claimed behavior, independent
  headless GUI checks where claimed, git commit only after verification.