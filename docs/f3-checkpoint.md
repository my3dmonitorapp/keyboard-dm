# F3 recovery checkpoint — 2026-10-18

**State after recovery:**

| Item | Value |
|---|---|
| Development workspace (sole) | laptop `keyboard75` (`ssh` alias) `/home/daniele/projects/keyboard75` |
| VM `/root/kb75_ci` role | CI/build/recovery only — no source development |
| F3 branch | `feature/f3-desktop-installer` |
| Task status | T1 `a24cb20`, T2 `905b2aa`, T3 `2e0378e`, T4 `affd7ed` + ckpt `b4eee25`, T5 `6b9ddcc` |
| Desktop tests | 298 green (T1 16 + T2 17 + T3 14 + T4 11 + T5 5 + existing) |
| Firmware host tests | 68/68 (unchanged, F2 baseline) |
| Hardware interaction | NONE — mock backends only |

**T4 backup workflow:** `desktop_app/backup.py` (chunked read + SHA-256 verified,
private 0600 backup store outside the repo, `restore()` raises `BackupRestoreDenied`
until explicitly authorized), `tests/test_backup.py` (11 tests).

**Next (after user approval of T5 `6b9ddcc` review):** T6 (final task of F3).
Pause for review after each verified task per the corrected workflow.
