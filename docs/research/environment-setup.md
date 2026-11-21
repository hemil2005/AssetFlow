# Environment setup — Odoo 19 + PostgreSQL

Two supported routes. Prefer Docker on Hemil's Windows machine; use the source route on daksh's
machine, where an editable Odoo 19 source already exists.

Do not commit real passwords. Use `.env` locally and keep it out of git.

## 0. Requirements (verified for 19.0)

| Component | Minimum | Notes |
|-----------|---------|-------|
| Python | 3.10 | 3.11 recommended; 3.12 works for the server, but some third-party dependencies lag |
| PostgreSQL | 13 | 16 is the safe choice |
| Odoo | 19.0 Community | this project targets 19 only |
| `wkhtmltopdf` | 0.12.6 | required for PDF reports; bundled in the Docker image |
| Node.js | optional | only for `rtlcss` / asset tooling |
| Docker | optional | Docker Desktop with WSL2 on Windows |

## 1. Docker route (recommended on Windows)

### 1.1 Start Docker Desktop

On Hemil's machine the Docker CLI is installed but the daemon was **not running** at the last check.
Start Docker Desktop and wait for "Engine running".

```powershell
docker info --format '{{.ServerVersion}}'
```

### 1.2 `docker-compose.yml` (create at repo root, do not commit secrets)

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-odoo}
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo -d postgres"]
      interval: 5s
      timeout: 5s
      retries: 20

  odoo:
    image: odoo:19.0
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8069:8069"
    environment:
      HOST: db
      PORT: 5432
      USER: odoo
      PASSWORD: ${POSTGRES_PASSWORD:-odoo}
    volumes:
      # The whole repo is mounted because the six addons live at the repo root.
      - ./:/mnt/extra-addons
      - odoo-data:/var/lib/odoo
    command: ["odoo", "--dev=all"]

volumes:
  db-data:
  odoo-data:
```

Why mount the repo root: flat-orchid's layout puts `assetflow_base/`, `assetflow_assets/`, ... at the
repo root, not inside an `addons/` folder. Odoo scans every mounted directory for
`__manifest__.py`; `.git`, `docs`, and `.opencode` are ignored because they have no manifest.

### 1.3 Start and create the database

```powershell
docker compose up -d
docker compose logs -f odoo
```

Open <http://localhost:8069>, choose **Create database**:

- Database name: `assetflow`
- Email: `admin`
- Password: choose one
- Demo data: **off** (the project ships its own demo data)

Then install the addons in dependency order:

```
assetflow_base
assetflow_assets
assetflow_booking
assetflow_maintenance
assetflow_audit
assetflow_reports
```

Apps -> Update Apps List, then search "AssetFlow". Installing `assetflow_reports` last pulls the
rest through `depends` if the manifests are correct.

### 1.4 Update and test inside Docker

```powershell
# after changing Python/XML in one addon
docker compose exec odoo odoo -d assetflow -u assetflow_assets --stop-after-init

# tests for one addon
docker compose exec odoo odoo -d assetflow -u assetflow_assets --test-enable --test-tags /assetflow_assets --stop-after-init

# restart the web server after schema/data changes
docker compose restart odoo
```

`--dev=all` reloads Python and XML on change, but manifest changes and new files still need a
restart. PostgreSQL data survives `docker compose down`; use `down -v` only when you intend to wipe
the database.

## 2. Source route (daksh's machine, or a Windows fallback)

### 2.1 Get Odoo 19 and a virtualenv

```powershell
git clone --branch 19.0 --depth 1 https://github.com/odoo/odoo.git C:\src\odoo19
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r C:\src\odoo19\requirements.txt
```

daksh already has this at `C:\Users\daksh\.local\odoo-19-src` with an editable install; do not create a
second source tree there.

### 2.2 PostgreSQL

Install PostgreSQL 16 with the Windows installer, then:

```powershell
# as the postgres superuser
createuser -d -R -S odoo
createdb -O odoo assetflow
```

Keep the `odoo` role password local; never commit it. If port 5432 is already used by Docker,
stop one of the two or publish Docker's Postgres on a different host port.

### 2.3 Run the server

```powershell
python C:\src\odoo19\odoo-bin `
  --addons-path=C:\src\odoo19\addons,E:\Mumur\AssetFlow `
  -d assetflow `
  --db_host=localhost --db_user=odoo --db_password=<local-password> `
  --dev=all
```

Open <http://localhost:8069>. The first database creation can also be done from the web page.

### 2.4 PDF reports on Windows

Install `wkhtmltopdf` 0.12.6 (`wkhtmltox-0.12.6-1.msvc2015-win64.exe`), add its `bin` folder to
`PATH`, and restart the shell. Without it, `qweb-pdf` reports fail while HTML reports still work.

## 3. First-run checklist

- [ ] Odoo 19 starts and `/web/login` loads.
- [ ] Database `assetflow` exists and has no demo data.
- [ ] `assetflow_base` installs without warnings in the log.
- [ ] The remaining five addons install in order, or via `assetflow_reports`.
- [ ] `admin` can open the AssetFlow root menu.
- [ ] A test employee can log in but sees no admin-only menus (see the RBAC matrix).
- [ ] A PDF report renders (proves `wkhtmltopdf`).
- [ ] `--test-enable` runs the module test suite green.

## 4. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `docker: ... pipe dockerDesktopLinuxEngine ... not found` | Docker Desktop not started | start it, wait for Engine running |
| Odoo page loads but addon is missing from Apps | addon path not mounted, or no `__manifest__.py` | check `docker compose exec odoo ls /mnt/extra-addons`; update Apps List |
| `ModuleNotFoundError: odoo` | venv not activated or requirements not installed | activate `.venv`, `pip install -r requirements.txt` |
| `psycopg2.OperationalError` | wrong host/user/password, or Postgres not running | test with `psql`; check Docker service health |
| PDF report 500s | `wkhtmltopdf` missing or wrong version | install 0.12.6, restart |
| XML view parse error after an edit | Odoo 19 requires `<list>`, not `<tree>`; check `position` values | fix XML, restart with `-u` |
| Changes not visible | Python module not reloaded, or assets cached | `--dev=all`, restart, hard-refresh browser |
| Tests cannot find a module | `--test-tags` typo, or tests not imported in `tests/__init__.py` | fix tag/imports |
| Port 8069 already in use | another Odoo instance | stop it or change the published port |

## 5. Hygiene

- Add `.env`, `*.log`, `.venv/`, `__pycache__/`, `*.pyc`, and `odoo-data/` to `.gitignore` when the
  first code lands.
- Keep the database disposable. Every schema change must be reproducible from a clean database and
  the addon manifests.
- Run the demo from a freshly created database before presenting; do not rely on hand-edited data.
