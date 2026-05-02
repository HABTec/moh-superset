# MoH Superset — Customizations & Deployment Guide

This fork adds Ministry of Health branding, a custom landing page, and
ClickHouse driver support on top of Apache Superset 6.x. All customizations
are designed to be **upstream-merge-friendly** — they live in additive files
where possible, with minimal edits to Apache's source.

The same customizations work in two runtimes:
- **Docker dev** on Windows (current default during development)
- **Ubuntu native** (production deployment, this guide)

---

## 1. What's been customized

### 1.1 File inventory

| File | Status | Purpose |
|---|---|---|
| `superset/moh_branding.py` | **NEW** | Single source of truth — APP_NAME, APP_ICON, VERSION_STRING, THEME_DEFAULT, THEME_DARK, FEATURE_FLAGS |
| `superset/landing_view.py` | **NEW** | `MoHLandingView` — the FAB IndexView that renders the branded landing page at `/` |
| `superset/templates/superset/landing.html` | **NEW** | Landing page Jinja template — hero, dashboard tiles, top nav links, footer |
| `superset/static/assets/images/logomohnewww.png` | **NEW** | MoH logo asset, served at `/static/assets/images/logomohnewww.png` |
| `superset/initialization/__init__.py` | **MODIFIED** | One-line swap: `appbuilder.indexview = MoHLandingView` instead of `SupersetIndexView` |
| `Dockerfile` | **MODIFIED** | Added a single RUN block installing ClickHouse driver pins matching Open_ETL |
| `requirements/moh.txt` | **NEW** | ClickHouse drivers + production server pins for native installs |
| `superset_config.example.py` | **NEW** | Native (Ubuntu) Superset config **template** — copy to `superset_config.py` on the server. DB/Redis/Celery + `from superset.moh_branding import *` |
| `docker/pythonpath_dev/superset_config_docker.py` | **NEW** | Docker dev config shim — `from superset.moh_branding import *` |
| `docker/pythonpath_dev/.gitignore` | **MODIFIED** | Allow-list the shim above |

### 1.2 What each piece does

**`superset/moh_branding.py`** — Single Python module imported by both runtimes' config files. Contains:
- `VERSION_STRING = "MoH 6.0"` → shown in Settings → About
- `APP_NAME = "MoH Analytics Portal"` → window title, tooltip on logo
- `APP_ICON` → URL of the MoH logo
- `THEME_DEFAULT` / `THEME_DARK` → extends Apache's defaults with MoH brand tokens (`brandLogoUrl`, `brandAppName`, `colorPrimary` `#1a5cff`, `colorLink`). Superset 6.x reads logo from theme tokens, not from `APP_ICON` directly — both runtimes get the MoH logo automatically because both seed these dicts into the DB on startup.
- `FEATURE_FLAGS` → `ALERT_REPORTS`, `DATASET_FOLDERS`, `ENABLE_TEMPLATE_PROCESSING`

**`superset/landing_view.py`** — Replaces FAB's default index. Queries published dashboards from the metadata DB, picks the dashboard with the most top-level tabs as the "featured" hero, lists the rest as compact pills. Located at top-level (not under `superset/views/`) on purpose — importing through `superset.views` triggers an init cascade that uses `security_manager` before it's initialized, causing `AttributeError`.

**`superset/templates/superset/landing.html`** — Standalone HTML page (does not extend the SPA shell). Includes a server-rendered nav bar with links to the standard Superset list pages (`/dashboard/list/`, `/chart/list/`, `/tablemodelview/list/`, `/sqllab/`).

**`superset/initialization/__init__.py`** — Single line modified inside `configure_fab()`:
```python
# was: appbuilder.indexview = SupersetIndexView
from superset.landing_view import MoHLandingView
appbuilder.indexview = MoHLandingView
```

**`Dockerfile`** — One RUN block added in the `dev` stage to install ClickHouse drivers. Apache's `[postgres]` install line is unchanged, so future upstream syncs of the Dockerfile rebase cleanly.

**`requirements/moh.txt`** — Python deps for native (non-Docker) installs.

**Config shims** (`superset_config.py` at root, `docker/pythonpath_dev/superset_config_docker.py`) — Both end with `from superset.moh_branding import *` so the customization module is the only place to edit branding.

---

## 2. Architecture: how the layers fit together

```
                       ┌───────────────────────────────────────┐
                       │   superset/moh_branding.py            │
                       │   — single source of truth —          │
                       │   APP_NAME, APP_ICON, THEME_DEFAULT,  │
                       │   THEME_DARK, FEATURE_FLAGS, ...      │
                       └─────────────┬─────────────────────────┘
                                     │
                  ┌──────────────────┴──────────────────┐
                  │                                     │
                  ▼                                     ▼
┌────────────────────────────┐         ┌───────────────────────────────────┐
│ superset_config.py         │         │ docker/pythonpath_dev/             │
│ (project root)             │         │ superset_config_docker.py          │
│                            │         │                                   │
│ from superset.moh_branding │         │ from superset.moh_branding        │
│   import *                 │         │   import *                        │
│                            │         │                                   │
│ + DB/Redis/Celery for      │         │ (loaded via Apache's              │
│   native Ubuntu            │         │  superset_config.py at the end)   │
└─────────────┬──────────────┘         └─────────────┬─────────────────────┘
              │                                      │
              ▼                                      ▼
        Ubuntu native run                       Docker dev compose
   (SUPERSET_CONFIG_PATH=...)                  (docker compose up)
```

Edit `superset/moh_branding.py` once → both runtimes pick it up on next restart.

---

## 3. Native Ubuntu installation (no Docker)

Tested on Ubuntu 22.04 LTS. Adapt paths/users for your environment.

### 3.1 System dependencies

```bash
sudo apt update && sudo apt install -y \
  python3.11 python3.11-venv python3.11-dev \
  build-essential libssl-dev libffi-dev libsasl2-dev libldap2-dev \
  default-libmysqlclient-dev pkg-config \
  postgresql postgresql-contrib redis-server \
  git curl

# Node 22 — needed only if you'll rebuild the frontend
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

### 3.2 Postgres metadata database

```bash
sudo -u postgres psql <<'SQL'
CREATE USER superset WITH PASSWORD 'CHANGE_ME_strong_password';
CREATE DATABASE superset OWNER superset;
GRANT ALL PRIVILEGES ON DATABASE superset TO superset;
SQL
```

### 3.3 Clone the customized fork

```bash
cd ~
git clone https://github.com/HABTec/moh-superset.git
cd moh-superset
git checkout moh-customizations
```

### 3.4 Python virtualenv + install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip uv

# Apache extras: postgres + clickhouse (declared in pyproject.toml)
uv pip install -e ".[postgres,clickhouse]"

# MoH-specific pins (ClickHouse drivers matching Open_ETL + production server)
uv pip install -r requirements/moh.txt
```

### 3.5 Build the frontend (one-time + after JS changes)

```bash
cd superset-frontend
npm ci
npm run build           # outputs to ../superset/static/assets
cd ..
```

### 3.6 Copy the config template & configure secrets

The repo ships [`superset_config.example.py`](superset_config.example.py) as a
template. Copy it to `superset_config.py` (gitignored locally so any hand-edits
stay on the server) and let it read secrets from environment variables:

```bash
cp superset_config.example.py superset_config.py
# Optionally edit superset_config.py — but the env-var defaults usually suffice.
```

Generate a strong secret key once and persist the env vars:

```bash
SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(42))")

cat >> ~/.bashrc <<EOF

# --- MoH Superset ---
export SUPERSET_CONFIG_PATH=$HOME/moh-superset/superset_config.py
export SUPERSET_SECRET_KEY="$SECRET"
export SUPERSET_DATABASE_URI="postgresql://superset:CHANGE_ME_strong_password@localhost:5432/superset"
export SUPERSET_REDIS_HOST=localhost
export SUPERSET_REDIS_PORT=6379
export FLASK_APP=superset
EOF

source ~/.bashrc
```

`superset_config.py` reads each `SUPERSET_*` env var with a safe default — no
secrets ever land in source.

### 3.7 Initialize Superset

```bash
source ~/moh-superset/.venv/bin/activate
cd ~/moh-superset

superset db upgrade           # runs all migrations
superset fab create-admin     # follow prompts to create the admin user
superset init                 # creates roles & permissions
# Optional, only if you want the example dashboards:
# superset load-examples
```

### 3.8 Run

**Quick start (dev mode, Flask dev server):**
```bash
superset run -h 0.0.0.0 -p 8088 --with-threads --reload --debugger
```

**Production (gunicorn):**
```bash
gunicorn \
  --bind 0.0.0.0:8088 \
  --workers 4 \
  --timeout 120 \
  --worker-class gevent \
  "superset.app:create_app()"
```

**Celery worker** (for alerts, scheduled reports, async SQL Lab, thumbnails) — separate terminal:
```bash
source ~/moh-superset/.venv/bin/activate
celery -A superset.tasks.celery_app:app worker -O fair -c 4
```

**Celery beat** (scheduler) — separate terminal:
```bash
celery -A superset.tasks.celery_app:app beat
```

Open http://your-server-ip:8088. The MoH logo, primary color, and landing
page should all be active.

### 3.9 Production polish: systemd + nginx

**`/etc/systemd/system/superset.service`** (replace `youruser`):
```ini
[Unit]
Description=MoH Superset web
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/moh-superset
EnvironmentFile=/home/youruser/superset.env
ExecStart=/home/youruser/moh-superset/.venv/bin/gunicorn \
    --bind 127.0.0.1:8088 --workers 4 --timeout 120 --worker-class gevent \
    "superset.app:create_app()"
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**`~/superset.env`** (chmod 600 it — contains secrets):
```
SUPERSET_CONFIG_PATH=/home/youruser/moh-superset/superset_config.py
SUPERSET_SECRET_KEY=<paste your generated key>
SUPERSET_DATABASE_URI=postgresql://superset:STRONG_PW@localhost:5432/superset
SUPERSET_REDIS_HOST=localhost
SUPERSET_REDIS_PORT=6379
FLASK_APP=superset
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now superset
sudo systemctl status superset
```

Replicate for `superset-worker.service` and `superset-beat.service` (same
EnvironmentFile, different `ExecStart`).

**Nginx in front** (TLS + caching), `/etc/nginx/sites-available/superset`:
```nginx
server {
    listen 443 ssl http2;
    server_name analytics.moh.gov.et;

    ssl_certificate     /etc/letsencrypt/live/analytics.moh.gov.et/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/analytics.moh.gov.et/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

---

## 4. Docker development (Windows) — quick reference

For development on Windows where native is impractical:

```powershell
# Port overrides (in .env at project root) avoid local conflicts
docker compose up
# → http://localhost:8090 (or whatever you've set SUPERSET_PORT to)
```

Edits to Python source / templates / `superset/moh_branding.py`:
```powershell
docker compose restart superset superset-worker superset-worker-beat
```

Edits to `pyproject.toml` / `Dockerfile` / new system packages:
```powershell
docker compose down
docker compose up --build
```

---

## 5. Maintenance

### 5.1 Syncing with Apache upstream

The fork is set up so syncs are minimally disruptive:

```bash
git fetch upstream                      # apache/superset
git checkout master
git merge upstream/master               # or rebase, your preference
git push origin master                  # back to HABTec/moh-superset

git checkout moh-customizations
git rebase master                       # replay our changes on top
# resolve conflicts (usually only the one-line in initialization/__init__.py)
git push --force-with-lease origin moh-customizations
```

Most files are NEW (no conflicts possible). Only `superset/initialization/__init__.py`
and `Dockerfile` have small modifications, and conflicts there should be obvious.

### 5.2 Changing brand colors / logo / app name

Edit [superset/moh_branding.py](superset/moh_branding.py). Restart Superset:
- Docker: `docker compose restart superset`
- Native: `sudo systemctl restart superset` (and worker)

### 5.3 Adding a new database driver

1. Edit [requirements/moh.txt](requirements/moh.txt) — add the pip package
2. Edit the [Dockerfile](Dockerfile) RUN block — add the same package
3. On Ubuntu: `uv pip install -r requirements/moh.txt && systemctl restart superset`
4. On Docker: `docker compose up --build`

### 5.4 Customizing the landing page further

- **Layout / styling**: [superset/templates/superset/landing.html](superset/templates/superset/landing.html) — pure HTML/CSS, hot-reloads in dev mode
- **What's listed / featured logic**: [superset/landing_view.py](superset/landing_view.py) — the `MoHLandingView.index()` method
- **Add data to the template**: pass extra kwargs to `self.render_template(...)` from the view

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Logo still shows Superset default | Browser cache, or `THEME_DEFAULT` not re-seeded | Hard-refresh; restart `superset` container/service |
| `Can't load plugin: sqlalchemy.dialects:clickhousedb.connect` | ClickHouse drivers not installed | `uv pip install -r requirements/moh.txt` (or `docker exec ... uv pip install ...` for runtime fix) |
| `AttributeError: 'NoneType' object has no attribute 'database_after_insert'` | Importing a view too early during FAB setup | Don't import from `superset.views.*` inside `configure_fab()` — use top-level modules like `superset.landing_view` |
| `ClickHouse Code: 215. NOT_AN_AGGREGATE` errors on charts | Time column alias collision with `dateTrunc` wrapper | Add a pre-truncated calculated column to the dataset; use it as the X-axis with `No time grain` |
| Landing page works but menu links broken | Routes haven't changed; the React SPA still owns `/dashboard/list/` etc. | Click any link in the landing nav — they go to the standard Superset SPA which has its own React menu |
