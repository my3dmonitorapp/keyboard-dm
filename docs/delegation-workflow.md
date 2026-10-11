# Keyboard75 — Development Workflow (Hermes → Codex)

Verified 2026-10-11, Codex CLI 0.161.0 on `dev-machine` (SSH alias `/project`).

## Model & authentication
- **Selected model: `gpt-5.6-sol`** (GPT-5.6-Sol, "Latest workhorse model for coding",
  supported_in_api=true, not deprecated).
- **Explicitly NOT Astra.** The user's laptop global config has
  `model = "gpt-6-astra"` — we override it every run with `-m gpt-5.6-sol`.
  Astra / Astra Pro / any variant: never used, no automatic model switching.
- **Auth: existing ChatGPT login (OAuth) on the laptop.** No API keys, no new
  subscriptions, no separately billed calls. ChatGPT auth and global Codex
  config are untouched.
- Do NOT run Codex with `HOME` redirected — the ChatGPT auth lives in the
  user's home and a redirected HOME yields 401 Unauthorized.

## Exact execution pattern (invoke from the VPS)
```bash
ssh /project 'export PATH=$HOME/.local/bin:$PATH; cd /projects/<project>;
  timeout 600 codex exec -s workspace-write --ephemeral -m gpt-5.6-sol --json \
  -o /tmp/kb75_lastmsg.txt "<task prompt>" </dev/null > /tmp/kb75_run.out 2> /tmp/kb75_run.err'
```
- `</dev/null` — never hang on stdin (non-interactive sessions have no TTY).
- `export PATH` — codex is not on the default PATH of non-interactive SSH
  sessions.
- Must run **inside** `/projects/<project>` (Codex trusted-dir check).
- Verify: `echo $?` after the run; read `/tmp/kb75_lastmsg.txt` (final answer);
  parse the JSONL in `/tmp/kb75_run.out` for `item.completed` / `turn.completed`
  events; check `git -C /projects/<project> status` and
  `git diff` for modified files before accepting.
- `--ephemeral` keeps the local session out of Codex history; drop it if
  conversation continuity across runs is ever needed.

## Safety limits
- Sandbox `workspace-write` (never `danger-full-access`): writes limited to the
  Keyboard75 repo; unrelated personal files untouched.
- No hardware flashing, no production deployment, no system/package changes
  outside the project without explicit authorization.
- Preserve the existing 12-key vendor reference app in the repo.
- Max 2 troubleshooting attempts per failed run; then stop and report.
- No unattended unlimited iteration loops.
- Failure means report the error verbatim — never silently swap provider/model.

## Verified smoke test (2026-10-11)
Command (read-only): `codex exec -s read-only --ephemeral -m gpt-5.6-sol --json
"Reply in exactly three words: ready to work"` → **RC=0**, full event stream
(thread.started → turn.started → item.completed → turn.completed), final
answer: "ready to work". PASS.

## Hermes orchestration loop
1. Compose a scoped task prompt (one feature/batch at a time, self-contained —
   Codex has no chat history).
2. Run one execution block; read the last message + JSONL.
3. Inspect changes: `git status`, `git diff`, run the project test suite if
   changes touched code.
4. If tests fail: craft a correction prompt from the failure output, re-run
   (counts toward the 2-attempt limit).
5. On pass: review diff, `git add`/`commit` with a descriptive message, move on.
6. Stop after the approved scope; report a concise verified summary (counts,
   paths, test results) — never dump raw file contents into the chat.

## Archived finding (local-Ollama attempt, 2026-10-10, not pursued further)
An isolated profile `.codex-home//project_local.config.toml` was created to
point Codex at the local Ollama (`local-llm:11434`) per the earlier plan.
Last known issue: with an isolated CODEX_HOME the request still landed on
api.openai.com (routing pitfall — `base_url` in `[models."tag"]` alone does
not bind provider routing in 0.161.0). Left in place, unused, for reference.
Per Daniele's 2026-10-11 decision it is superseded by the ChatGPT-login
configuration above and no further troubleshooting is scheduled.
