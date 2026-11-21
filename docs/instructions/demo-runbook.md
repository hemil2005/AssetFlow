# Demo runbook

One command builds a fresh, seeded AssetFlow database in the local Docker Compose stack and serves
it at a known URL. Use it before every demo; never demo on a database you have been clicking in.

Status: `scripts/demo.ps1` targets `scripts/seed_demo.py` and `scripts/demo_narrative.py`, which live
on the demo feature branch (`feat/assetflow-demo` at the time of writing). Run the script from a
checkout that contains the six addons and both seed scripts.

## 1. Prerequisites

- Windows 10/11 with Windows PowerShell 5.1 or PowerShell 7.
- Docker Desktop running, with Compose v2 (`docker compose version`).
- Free host port `8069`; roughly 3 GB of disk; internet on the first run to pull `postgres:16` and
  `odoo:19.0`.
- No local Python or Odoo install: everything runs in containers.

## 2. The command

```powershell
./scripts/demo.ps1
```

It finishes by printing `http://localhost:8069` (or the port Docker publishes) and the six logins.
Every run drops the target database first, including with `-SkipSeed`; the flags only skip the data
steps, never the reset.

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `-Database` | `assetflow_demo` | Database to drop, recreate, install into, and seed. |
| `-Port` | `8069` | Host port printed in the URL. If `docker-compose.yml` publishes another port, the script prints a warning and uses the published one. |
| `-Password` | `$env:ASSETFLOW_DEMO_PASSWORD`, else `AssetFlow!2026` | Password for the five seeded users. Never printed. |
| `-SkipSeed` | off | Install the addons only. |
| `-SkipNarrative` | off | Do not run `scripts/demo_narrative.py`. |
| `-Force` | off | Allow dropping a database outside the demo naming pattern. |

Examples:

```powershell
# Local demo password, kept out of the repo and out of scrollback.
$env:ASSETFLOW_DEMO_PASSWORD = 'LocalOnly!42'
./scripts/demo.ps1

# Fast environment check without demo data.
./scripts/demo.ps1 -SkipSeed -SkipNarrative
```

`admin` is Odoo's built-in account and keeps the fresh-database default password (`admin` on a
stock Odoo 19 image). The five seeded logins share the demo password above. Change both before
reusing the database for anything but a local demo.

## 3. What the command does

1. Checks that Docker is running and `docker compose` works, and stops with a readable message if
   not.
2. Creates `.env` from `.env.example` if it is missing. The Postgres password is never read or
   printed; the db container is reached over its local socket.
3. Starts the stack and waits for `pg_isready` to succeed.
4. Refuses to drop a database outside the demo naming pattern unless `-Force` is given, then runs
   `dropdb --if-exists --force` and `createdb`.
5. Installs the six addons in dependency order with `--without-demo --stop-after-init` and fails on a
   non-zero exit (or a traceback/CRITICAL line in the log).
6. Pipes `scripts/seed_demo.py` into `odoo shell` with `ASSETFLOW_DEMO_PASSWORD` set, and checks the
   seed's completion marker and KPI assertions.
7. Runs `scripts/demo_narrative.py` the same way unless `-SkipNarrative` is given.
8. Restarts Odoo, waits for HTTP, and prints the URL and the six logins.

`odoo shell` rolls back its transaction when it exits, so the wrapper appends `env.cr.commit()` after
the piped script. If you run a seed by hand, do the same or the data disappears.

Logs are written to `odoo-data/logs/` (git-ignored): `up`, `dropdb`, `createdb`, `install`, `seed`,
`narrative`, `restart`. Live server output: `docker compose logs -f odoo`.

## 4. What the seed creates

- Users: `maya.manager` (Asset Manager), `dev.head` (Department Head, IT), `priya.employee`,
  `raj.employee`, `auditor` (Sam); `admin` is promoted to the AssetFlow admin group.
- Organization: departments IT, Operations, Facilities (child of Operations); categories Electronics
  (24-month warranty), Furniture, Vehicles, Rooms.
- Assets `AF-0001`..`AF-0009` as in [demo-data.md §3](../spec/demo-data.md#3-assets), including
  `AF-0001` allocated to Priya, `AF-0009` allocated and overdue, `AF-0005` in maintenance, `AF-0007`
  lost, `AF-0008` retired.
- Bookings tomorrow 09:00-10:00 (Room B2, Priya) and 10:00-11:00 (Projector, Dev).
- One pending maintenance request for the van, one pending transfer `AF-0001` Priya -> Raj.
- An in-progress IT audit cycle: `AF-0006` damaged, `AF-0007` missing, `AF-0002` line deliberately
  left pending.
- KPI assertions run inside the seed and abort the run on a mismatch, so a green seed is evidence
  that the dataset matches the spec: 4 available, 2 allocated, 1 maintenance today, 0 active
  bookings, 1 pending transfer, 1 upcoming return, 1 overdue return, 1 open maintenance.

Dates are relative to the day you run the seed, so the dataset does not age.

## 5. Demo order

Run the seven steps in [demo-data.md §8](../spec/demo-data.md#8-demo-order). Summary:

1. `admin`: departments, categories, and promoting staff in the Employee Directory.
2. `maya.manager`: register an asset, then allocate `AF-0001` to Raj — blocked with the holder and a
   Transfer action offered.
3. `priya.employee`: request the transfer; `dev.head` approves; history shows both.
4. `priya.employee`: book Room B2 09:00-10:00. `raj.employee` tries 09:30-10:30 (rejected), then
   10:00-11:00 (accepted).
5. `priya.employee`: raise maintenance for the van; `maya.manager` approves (asset flips) and
   resolves it.
6. `admin`/`auditor`: open the audit cycle, mark missing/damaged, close it, show the Lost/damaged
   states and the PDF.
7. `admin`: dashboard KPIs and notifications.

## 6. Reset

Re-run the command; it drops and recreates the database, so there is no state to clean by hand:

```powershell
./scripts/demo.ps1
```

If the database was built with a different Postgres user or password (for example after editing
`.env`), reset the volumes once. This deletes **every** local database in this project:

```powershell
docker compose down -v
./scripts/demo.ps1
```

Never repair the demo with manual SQL; change the seed and reinstall, as
[demo-data.md §7](../spec/demo-data.md#7-reset-routine) requires.

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `docker compose up` fails: "port is already allocated" / "address already in use" | Something else owns 8069 | Stop it (`netstat -ano \| findstr :8069`) or change the mapping in `docker-compose.yml`, then re-run. |
| "The Docker engine is not running" | Docker Desktop is closed or still starting | Start Docker Desktop, wait for "Engine running", re-run. |
| "docker compose is not available" | Old standalone Docker or Compose v1 | Update Docker Desktop; verify `docker compose version`. |
| Script will not start: "running scripts is disabled" | Execution policy | `powershell -ExecutionPolicy Bypass -File scripts/demo.ps1`. |
| `dropdb`/install fails with "password authentication failed" | The volumes were created with a different `POSTGRES_PASSWORD` than `.env` now has | Restore the original password in `.env`, or `docker compose down -v` then re-run (deletes local data). |
| Addon install fails with "module not found" | The checkout lacks the addons or the branch is wrong | Check out `feat/assetflow-demo` (or another branch with the six `assetflow_*` folders) and re-run. |
| PDF is blank or the report action errors | `wkhtmltopdf` is missing or crashing in the container | Check `docker compose exec odoo wkhtmltopdf --version`; if it fails, pull a fresh image (`docker compose pull odoo`, `docker compose up -d --force-recreate odoo`) and rebuild the demo. Demo the HTML report in the browser if PDFs cannot be fixed in time. |
| Login refused for a seeded user | Password differs from the one the seed used | Set `$env:ASSETFLOW_DEMO_PASSWORD` (or pass `-Password`) and re-run the script: passwords are applied at seed time, so changing the variable alone does not update the database. |
| Login refused for `admin` | Admin password was changed on this database | With a fresh database use `admin`/`admin`; otherwise set a known password with `odoo shell` or recreate the database. |
| "Odoo did not answer within 120 seconds" | Odoo is still starting or crash-looping | `docker compose logs --tail=100 odoo`; if the DB is fine, `docker compose restart odoo` and open the URL again. |
| Seed stops on a KPI assertion | Seed and addon code disagree | Fix the seed or the addon, not the database; the assertion is the point. |
