# F3 recovery checkpoint — 2026-10-18 (after mandatory workflow correction)

**State after recovery:**

| Item | Value |
|---|---|
| Development workspace (sole) | laptop `keyboard75` (`ssh` alias) `/home/daniele/projects/keyboard75` |
| VM `/root/kb75_ci/f3/work` | **recovered, not a git repo**; VM is CI/build-only going forward |
| VM state checkpoint | `/root/kb75_ci/f3/checkpoints/f3-vm-state-20261018T075558Z.tar.gz` + `file-manifest-20261018T075558Z.sha256` (on VM) |
| VM→laptop transfer | reviewed Git patch `f3-t4-final.patch`, applied via `git apply` (no rsync, no overwrite) |
| F3 branch | `feature/f3-desktop-installer` = `affd7ed` |
| F3 commit chain | `a24cb20` (T1) → `905b2aa` (T2) → `2e0378e` (T3) → `affd7ed` (T4) |
| F3 draft PR | **https:/...[truncated]