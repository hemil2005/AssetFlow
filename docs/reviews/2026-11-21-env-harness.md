# Review: `chore/env-harness` @ `b091256`

- **Date:** 2026-11-21
- **Reviewer:** northern-envelope
- **Target:** `origin/chore/env-harness` @ `b091256` (based on `0543fbb`)
- **Verdict:** **approved for merge.** Merge commit `2440d94`.

## Scope

`docker-compose.yml`, `.env.example`, `scripts/test.ps1`, and the README "Local development"
section. No addon code, no docs, no `.gitignore` change.

## Findings

No merge blockers.

Minor, non-blocking:

1. **`restart: unless-stopped` on a dev stack** can mask a crash by restarting Odoo while you are
   reading logs. Consider `restart: "no"` for the dev compose, or document that `docker compose logs
   odoo` may show a restarted container.
2. **Healthcheck user.** `pg_isready -d postgres` does not pass `-U`; it proves the server accepts
   connections, not that the configured user/database pair is usable. `pg_isready -U
   ${POSTGRES_USER:-odoo} -d postgres` is a slightly stronger signal.
3. **Failure regex.** `FAIL|ERROR:` in the log is a useful guard, but an expected error log line can
   cause a false failure. Keep the exit code and `odoo.tests.stats` as the primary signals and treat
   the regex as a secondary check; the current behavior is conservative, which is acceptable.
4. **Rebase note.** The branch was based on `0543fbb`; the merge to `main` was clean, but future
   changes should rebase on `main` before pushing so the README stays in sync with the docs.

## Checks run

- `docker compose config --quiet` with the branch worktree: **OK**.
- PowerShell parser on `scripts/test.ps1`: **OK**.
- `scripts/test.ps1` on the branch (no addons): fails early with a readable "Addon folder(s) without
  `__manifest__.py`" message and exit 1, before touching Docker: **OK**.
- Docker server 29.7.2 reachable on this machine: **OK**.
- Not run here: `docker compose up -d` + the real install/test path. patient-wallaby ran the stack
  and a throwaway-addon smoke test; the six real addons are not on this branch, so the first real
  run will be on a branch that contains them.

## Summary

The harness is small, readable, and does the right preflight checks. It is safe to merge and is the
runner cruising-barbet should reuse for gate evidence once the addon fixes land.
