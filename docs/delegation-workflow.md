# Keyboard DM — Development Workflow (Hermes → Codex on RTX)

Updated 2026-10-12. **RTX Ubuntu desktop (`daniele@10.8.0.6`) is the sole
authoritative development host.** Codex CLI 0.149.1, native install at
`~/.local/bin/codex`, invoked as `~/.local/bin/codex -m gpt-5.6-sol` via the
SSH alias `rtx`.

## Authoritative host model (supersedes the earlier laptop-only rule)

- **Development host:** RTX Ubuntu (`daniele-MS-7A40`, Ubuntu 26.04, `x86_64`,
  12 cores, ~30 GB RAM). Repo lives at `~/projects/keyboard75`. This is the only
  machine where coding, commits, and pushes happen.
- **Laptop (10.8.0.x):** GUI/visual test client ONLY. It keeps a separate GitHub
  checkout to *run* the PySide6 app visually. It is NOT used for Codex,
  authoritative coding, firmware builds, or primary Git commits. Development
  must not depend on the laptop being powered on.
- **CI VM (`/root/kb75_ci`):** independent, read-only verification only —
  firmware host test suite + `esp32`/`esp32c3` ESP-IDF compiles and desktop
  pytest against *published* commits. VM never develops.
- **GitHub:** the authoritative published source. Every verified change is
  committed on the appropriate feature branch, pushed to GitHub, and the
  corresponding PR updated immediately. A task is not complete while its
  verified changes exist only locally.

## Model & authentication (RTX)

- **Selected model: `gpt-5.6-sol`**, always pinned explicitly with
  `-m gpt-5.6-sol`.
- **Explicitly NOT Astra / Astra Pro / any variant** — never used, no
  automatic model switching.
- **Auth on RTX: an API key** stored in `~/.codex/auth.json` (key value never
  shown or copied between machines). Codex is the native installed binary
  (`codex-cli 0.149.1`), on PATH for the `daniele` user.
- Do NOT run Codex with `HOME` redirected — the auth lives in the user's home.

## Exact execution pattern (from Hermes on the VPS)

```bash
ssh rtx 'export PATH=$HOME/.local/bin:$PATH; cd ~/projects/keyboard75;
  timeout 600 ~/.local/bin/codex exec -s workspace-write --ephemeral -m gpt-5.6-sol \
  "<task prompt>" </dev/null'
```
- `rtx` = SSH alias for `daniele@10.8.0.6` (dedicated key
  `~/.ssh/id_ed25519_rtx`, `IdentitiesOnly yes`).
- `</dev/null` — never hang on stdin (no TTY).
- Run **inside** `~/projects/keyboard75` (Codex trusted-dir check); use
  `--skip-git-repo-check` only if outside a repo.
- After a run: `echo $?`, `git -C ~/projects/keyboard75 status`, `git diff`
  before accepting.

## GitHub access (RTX)

- **Dedicated repository-scoped deploy key**, distinct from the Finance AI key:
  - Alias: `github-keyboard-dm` → `user git`,
    `IdentityFile ~/.ssh/id_ed25519_github_keyboard_dm`, `IdentitiesOnly yes`.
  - Repo origin: `git@github-keyboard-dm:my3dmonitorapp/keyboard-dm.git`.
  - Registered in GitHub → Deploy keys with **Allow write access**.
  - The Finance AI alias (`github-finance-ai`, key
    `~/.ssh/id_ed25519_github_finance_ai`) is untouched and still serves the
    other repos. No shared key is ever mixed between the two.
- Read/write verified by temp-branch push + delete (no branch left).

## Build & test split
- Desktop + firmware-**host** tests run on RTX:
  - `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q` (353/353)
  - `make -C firmware/host clean test` (12 binaries)
- Full **firmware compile** (`esp32`, `esp32c3`) stays on the CI VM per policy.

## Safety limits
- Sandbox `workspace-write` (never `danger-full-access`); writes limited to the
  Keyboard DM repo.
- No hardware flashing, no physical device operations, no production
  deployment, no system/package changes outside the project without
  explicit authorization.
- Preserve the 12-key vendor reference app in the repo.
- User keyboard profiles, device flash dumps, Bluetooth bonding data and all
  credentials stay OUT of the repository and never in chat.
- Keep the 9-key original flash backup private with an independent copy on the
  CI VM; GitHub source control is not a backup for ignored/private files.
- Max 2 troubleshooting attempts per failed run, then stop and report; no
  unattended unlimited iteration.
- Never swap provider/model silently on failure — report the error verbatim.

## Hermes orchestration loop
1. Compose a scoped task prompt (one feature/batch, self-contained).
2. Run one Codex execution block on `rtx`; read the final message.
3. Inspect changes (`git status`, `git diff`), run the relevant test suite on
   RTX, and cross-verify on the CI VM for firmware/published code.
4. On pass: review the diff, commit on the feature branch, **push to GitHub
   immediately**, update the PR, report the SHA + tests + PR URL.
5. Stop at the end of the approved scope; report a concise verified summary —
   never dump raw file contents into the chat.
