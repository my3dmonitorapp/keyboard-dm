# F3 recovery checkpoint — 2026-10-18

**State after recovery:**

| Item | Value |
|---|---|
| Development workspace (sole) | laptop `keyboard75` (`ssh` alias) `/home/daniele/projects/keyboard75` |
| VM `/root/kb75_ci` role | CI/build/recovery only — no source development |
| F3 branch | `feature/f3-desktop-installer` |
| Task status | T1 `a24cb20`, T2 `905b2aa`, T3 `2e0378e`, T4 `affd7ed` + ckpt `b4eee25`, T5 `6b9ddcc` + ckpt `33dff1d`, T6 (see below) |
| Desktop tests | 302 green (adds T6: 4 integration tests; InstallerPanel wired into real Keyboard75Window) |
| Firmware host tests | 68/68 (unchanged, F2 baseline) |
| Hardware interaction | NONE — mock backends only |

**T4 backup workflow:** `desktop_app/backup.py` (chunked read + SHA-256 verified,
private 0600 backup store outside the repo, `restore()` raises `BackupRestoreDenied`
until explicitly authorized), `tests/test_backup.py` (11 tests).

**T6 (F3-T6 — v0.1 checkpoint 1 of 4, final F3 task):**
- `desktop_app/app.py`: `Keyboard75Window` now embeds `InstallerPanel` in a
  `QStackedWidget` (`mainPageStack`); a checkable `Tools > Firmware Installer...`
  action (`firmwareInstallerAction`) switches the installer page in/out, banner
  and status bar shared. Default backend stays `MockFlashBackend`;
  `SafetyGate`/`RealFlashBackend` authorization gate untouched.
- `tests/test_gui_installer_integration.py`: 4 offscreen tests — reach/return,
  full mock install + restored backup digest, cancellation, editor-page
  regression (key grid intact, 75 keys).
- `V01_FINISH_LINE.md`: v0.1 scope, the four remaining checkpoints, acceptance
  criteria, verified state (302/302), blocking issues, not-in-v0.1.
- Full suite: 302/302. PR #4 updated (draft).

**Next (after user approval of T6 review):** checkpoint 2 (blank-device
provisioning + desktop→firmware serial config). Stop for review — do not
begin checkpoint 2 without explicit authorization.
