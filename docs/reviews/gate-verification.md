# Independent gate verification protocol

Use this when a free session can run Odoo/PostgreSQL on a machine where the code under review is
**not** being edited. The verifier produces evidence; the reviewer (northern-envelope) keeps the
verdict. The verifier does not edit addon code, docs, or the shared working tree.

## 1. Rules

- Work from a **pushed commit SHA**, never the shared working tree and never uncommitted files.
- Use a separate `git worktree` in a temp folder and a **dedicated database**.
- Do not edit `assetflow_*`, `docs/**`, or another agent's branch.
- Do not change the review verdict. Report PASS/FAIL/BLOCKED per finding; the reviewer decides.
- No credentials in output. Use a local throwaway password and scrub it from logs.
- If the shared tree is mid-edit, wait for the next push; do not test a dirty tree.

## 2. Setup

```powershell
# choose a temp worktree and a DB unique to this SHA
$sha = "<full-sha>"
$wt  = "C:\Users\daksh\AppData\Local\Temp\af-gate-$($sha.Substring(0,8))"
git -C E:\Coding\Projects\AssetFlow worktree add --detach $wt $sha

# database
$db = "af_gate_$($sha.Substring(0,8))"
createdb -U odoo $db
```

Server routes:

```powershell
# source + venv
& C:\Users\daksh\.local\odoo-19-src\.venv\Scripts\python.exe `
  C:\Users\daksh\.local\odoo-19-src\odoo-bin `
  -d $db --addons-path=C:\Users\daksh\.local\odoo-19-src\addons,$wt `
  --db_host=127.0.0.1 --db_port=5433 --db_user=odoo --db_password=<local> `
  --stop-after-init -i assetflow_base,assetflow_assets,assetflow_booking
```

If the source is run from the venv, use that interpreter; if Docker is used, mount `$wt` at
`/mnt/extra-addons` and use the same module list. Do not use flat-orchid's database.

Drop the database and remove the worktree when done:

```powershell
dropdb -U odoo $db
git -C E:\Coding\Projects\AssetFlow worktree remove --force $wt
```

## 3. Install and test

```powershell
# install (fresh DB; must be zero warnings/errors for the addons)
<odoo> -d $db -i assetflow_base,assetflow_assets,assetflow_booking --stop-after-init

# tests
<odoo> -d $db `
  -u assetflow_base,assetflow_assets,assetflow_booking `
  --test-enable `
  --test-tags /assetflow_base,/assetflow_assets,/assetflow_booking `
  --stop-after-init
```

Capture the exit code, the test summary (`N tests, 0 failures, 0 errors`), and the tail of the log.
A traceback in the log is a FAIL even if the process exits 0.

## 4. Mechanical checks for B1-B10

| Finding | Check | PASS when |
|---------|-------|-----------|
| B1 | `git ls-files $wt \| Select-String '__pycache__\|\.pyc$'` | zero matches; `.gitignore` contains `__pycache__/` and `*.pyc` |
| B2 | inspect `security/ir.model.access.csv` + security XML for `assetflow.allocation` and `assetflow.transfer`; run an RPC test as an employee | record rules exist for both; no `base.group_user`; employee cannot read another's allocation or write a transfer; `state` is not writable through the form/RPC |
| B3 | inspect base ACL for `hr.employee`; check the directory model/views | no `base.group_user` ACL on `hr.employee`; if HR is reused, reads go through `hr.employee.public` and ADR-0002 is updated; if custom, `assetflow.employee` exists |
| B4 | grep for `auth_signup` / signup controller; run a signup HTTP test if present | signup creates an internal user + employee with no AssetFlow group; portal-only signup is a FAIL |
| B5 | check `assetflow.department` model/menu and admin tab | model + menu + CRUD test exist |
| B6 | check admin-only promotion buttons/service | promote/demote writes groups; employee cannot write groups |
| B7 | run lifecycle tests: dispose from allocated, lost from available, retire without reason, maintenance from lost | invalid transitions raise; destructive actions are admin-only and require a note |
| B8 | create allocation directly with no holder; create allocation for unavailable asset; approve transfer for unallocated asset; approve twice | all rejected/guarded; asset state and holder stay consistent |
| B9 | return without condition/notes | raises; valid return writes condition + notes and reopens the asset |
| B10 | book non-bookable, lost, maintenance asset; write `state` directly; create a current-window booking; book during an allocation | all rejected/guarded; current booking reserves immediately; allocation and maintenance conflicts enforced |

## 5. Concurrency evidence

### Double allocation

1. Create an active allocation for an asset.
2. Open a second cursor/transaction and attempt a direct SQL insert with `state = 'active'` for the
   same asset.
3. Expect the partial unique index to reject it. Also attempt two API `create` calls in parallel
   threads and assert exactly one commits.

### Booking overlap

1. Create booking A for `[09:00, 10:00)`.
2. In two parallel transactions, create `[09:30, 10:30)` and `[09:45, 10:45)`; assert exactly one
   succeeds and the other sees the conflict or a `LockError` that maps to a user error.
3. Adjacent `[10:00, 11:00)` must succeed.

A sequential unit test that only exercises the Python check is not sufficient evidence for the lock
guarantee; say so if you cannot force the race.

## 6. Report format

Send one Murmur message per push:

```
Subject: Gate evidence <short-sha> — X PASS / Y FAIL / Z BLOCKED
Body:
- SHA, database, Odoo version, Postgres version, command used
- B1: PASS — 0 tracked pyc; gitignore lines ...
- B2: FAIL — employee can write transfer state via RPC (traceback snippet)
- ...
- Tests: 12 run, 0 failed, 0 errors; exit 0
- Log warnings: none / list
- Not covered: ...
```

Do not paste secrets. Keep snippets short; full logs stay on the verifier's machine.

## 7. Boundaries

- The verifier may create a runner script **outside** the repo (temp folder) or, after coordinating
  with patient-wallaby, reuse `scripts/test.ps1`. Do not add a second harness to the repo.
- The verifier does not push addon changes. If a fix is needed, report it to flat-orchid and the
  reviewer.
- The reviewer records the evidence in `docs/reviews/review-log.md` and updates the verdict.
