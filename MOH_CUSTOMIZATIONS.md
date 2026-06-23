# MoH Superset — Customizations & Deployment Guide

This fork adds Ministry of Health branding, a custom landing page,
ClickHouse driver support, and an **AI Assistant page** (admin-only chat
backed by Gemini, Claude, or OpenAI via Superset's MCP server) on top of
Apache Superset 6.x. All customizations are designed to be
**upstream-merge-friendly** — they live in additive files where possible,
with minimal edits to Apache's source.

The same customizations work in two runtimes:
- **Docker dev** on Windows (current default during development)
- **Ubuntu native** (production deployment, this guide)

---

## 1. What's been customized

### 1.1 File inventory

| File | Status | Purpose |
|---|---|---|
| `superset/moh_branding.py` | **NEW** | Single source of truth — APP_NAME, APP_ICON, VERSION_STRING, THEME_DEFAULT, THEME_DARK, FEATURE_FLAGS, cache/performance settings |
| `superset/landing_view.py` | **NEW** | `MoHLandingView` — the FAB IndexView that renders the branded landing page at `/` |
| `superset/templates/superset/landing.html` | **NEW** | Landing page Jinja template — hero, dashboard tiles, top nav links, footer |
| `superset/static/assets/images/logomohnewww.png` | **NEW** | MoH logo asset, served at `/static/assets/images/logomohnewww.png` |
| `superset/initialization/__init__.py` | **MODIFIED** | One-line swap: `appbuilder.indexview = MoHLandingView` instead of `SupersetIndexView` |
| `Dockerfile` | **MODIFIED** | Added a single RUN block installing ClickHouse driver pins matching Open_ETL |
| `requirements/moh.txt` | **NEW** | ClickHouse drivers + production server pins for native installs |
| `superset_config.example.py` | **NEW** | Native (Ubuntu) Superset config **template** — copy to `superset_config.py` on the server. DB/Redis/Celery + `from superset.moh_branding import *` |
| `docker/pythonpath_dev/superset_config_docker.py` | **NEW** | Docker dev config shim — `from superset.moh_branding import *` |
| `docker/pythonpath_dev/.gitignore` | **MODIFIED** | Allow-list the shim above |
| `superset/moh_ai_chat.py` | **NEW** | Flask blueprint for the AI Assistant page (`/ai-chat/`). Supports Gemini, Claude, OpenAI via `MOH_AI_PROVIDER` env var |
| `superset/templates/superset/ai_chat.html` | **NEW** | AI chat UI — auto-embeds Superset URLs from the bot reply as inline iframes |
| `superset/templates/head_custom_extra.html` | **NEW** | Global responsive CSS for mobile dashboards — breakpoints at 901px, 767px, 640px, 380px. Handles grid collapse, touch targets (44x44px), chart sizing |
| `docker/requirements-local.txt` | **NEW** | AI provider SDKs installed on every container start (`google-genai`, `anthropic`, `openai`) |
| `docker-compose.override.yml` | **MODIFIED** *(gitignored)* | Adds `superset-mcp` service running the bundled MCP server on port 5008 |
| `docs/AI_CHAT_INTEGRATION.md` | **NEW** | Line-by-line integration guide for the AI Assistant |

### 1.2 What each piece does

**`superset/moh_branding.py`** — Single Python module imported by both runtimes' config files. Contains:
- `VERSION_STRING = "MoH 6.0"` → shown in Settings → About
- `APP_NAME = "MoH Analytics Portal"` → window title, tooltip on logo
- `APP_ICON` → URL of the MoH logo
- `THEME_DEFAULT` / `THEME_DARK` → extends Apache's defaults with MoH brand tokens (`brandLogoUrl`, `brandAppName`, `colorPrimary` `#1a5cff`, `colorLink`). Superset 6.x reads logo from theme tokens, not from `APP_ICON` directly — both runtimes get the MoH logo automatically because both seed these dicts into the DB on startup.
- `FEATURE_FLAGS` → `ALERT_REPORTS`, `DATASET_FOLDERS`, `ENABLE_TEMPLATE_PROCESSING`, `GLOBAL_ASYNC_QUERIES` (parallel chart loading)
- `CACHE_CONFIG` / `DATA_CACHE_CONFIG` / `THUMBNAIL_CACHE_CONFIG` → Redis-backed caches on separate DBs (1/2/3), 24h/1h TTL
- `GLOBAL_ASYNC_QUERIES_REDIS_CONFIG` → Redis DB 4 for async query state
- `RESULTS_BACKEND` → Redis DB 5 for SQL Lab results (replaces filesystem backend)

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

**`superset/moh_ai_chat.py`** + **`ai_chat.html`** — Self-contained Flask blueprint registered via `BLUEPRINTS = [ai_chat_bp]` in `moh_branding.py` (no edits to `init_views()`). Handler reads `MOH_AI_PROVIDER` and dispatches to `_ask_gemini`, `_ask_claude`, or `_ask_openai`; each opens an MCP session against `superset-mcp:5008` and runs the agent loop. Replies that contain a Superset explore/dashboard URL are auto-embedded inline as iframes (`?standalone=3`). Full details in [`docs/AI_CHAT_INTEGRATION.md`](docs/AI_CHAT_INTEGRATION.md).

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

Tested on Ubuntu 22.04 LTS. Run as your normal user (not root); use `sudo` where shown.

**Read the verification block after every step.** Skipping a verification is
the #1 cause of "the install said success but the browser is stuck loading"
problems. The most-skipped step is the **frontend build** — without it the
React SPA never loads and every page is a blank spinner.

### 3.1 System packages

```bash
sudo apt update && sudo apt install -y \
  python3.11 python3.11-venv python3.11-dev \
  build-essential libssl-dev libffi-dev libsasl2-dev libldap2-dev \
  default-libmysqlclient-dev pkg-config \
  postgresql postgresql-contrib redis-server git curl

# Node 22 — REQUIRED. Even if you won't actively develop the React SPA,
# you must build it once so the browser has assets to load.
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

**Verify:**
```bash
python3.11 --version    # Python 3.11.x
node --version          # v22.x.x
psql --version          # 14+
redis-cli ping          # PONG
```

### 3.2 Postgres metadata DB

```bash
DB_PASS='CHANGE_ME_strong_password'   # pick a strong one, you'll reuse it
sudo -u postgres psql <<SQL
CREATE USER superset WITH PASSWORD '${DB_PASS}' CREATEDB;
CREATE DATABASE superset OWNER superset;
GRANT ALL PRIVILEGES ON DATABASE superset TO superset;
\c superset
GRANT ALL ON SCHEMA public TO superset;
SQL
```

**Verify:**
```bash
psql "postgresql://superset:${DB_PASS}@localhost:5432/superset" -c "SELECT 1;"
# Should print "1" on a single row. If "password authentication failed":
#   - re-check DB_PASS matches the CREATE USER line above
#   - check /etc/postgresql/*/main/pg_hba.conf: local entries should be md5 not peer
```

### 3.3 Clone the fork and switch to your branch

```bash
cd ~
git clone https://github.com/HABTec/moh-superset.git
cd moh-superset
git checkout moh-customizations
```

**Verify:**
```bash
git log --oneline -1    # should show your most recent moh-customizations commit
ls superset/moh_branding.py   # if this file is missing you cloned the wrong branch
```

### 3.4 Python venv + dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip uv

# Apache extras
uv pip install -e ".[postgres,clickhouse]"

# MoH additions (ClickHouse drivers + AI SDKs + numpy<2.0 + gunicorn)
uv pip install -r requirements/moh.txt
```

**Verify:**
```bash
which python    # should print .../moh-superset/.venv/bin/python
which superset  # same .venv path
python -c "import superset; print(superset.__file__)"   # should be in .venv/lib/.../superset/
```

### 3.5 Frontend build — **REQUIRED**, do not skip

This step compiles the React SPA. Skipping it = every page in the browser is
a blank spinner because the JS bundles don't exist. Takes 5-10 min on a
reasonably-sized VM.

```bash
cd ~/moh-superset/superset-frontend
npm install     # (or: npm ci, if package-lock.json is present and unmodified)
# If your VM has < 4 GB RAM, bump Node's heap limit before building:
#   export NODE_OPTIONS=--max-old-space-size=4096
npm run build
cd ~/moh-superset
```

**Verify (the most important verification in this entire guide):**
```bash
ls superset/static/assets/ | head -5
# Should list many built files including chunk-*.js and a manifest.json. If it
# prints nothing or "No such file or directory", the build failed silently —
# re-run npm run build and watch the output for the actual error.
```

### 3.6 Config file + secrets

```bash
cp superset_config.example.py superset_config.py    # template → live config
SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(42))")

cat >> ~/.bashrc <<EOF

# --- MoH Superset ---
export SUPERSET_CONFIG_PATH=\$HOME/moh-superset/superset_config.py
export FLASK_APP=superset
export SUPERSET_SECRET_KEY="${SECRET}"
export SUPERSET_DATABASE_URI="postgresql://superset:${DB_PASS}@localhost:5432/superset"

# Disable HTTPS redirect when running without a TLS terminator (local / VirtualBox / staging over HTTP).
# Set to "true" (or remove) when behind nginx+TLS in production.
export MOH_FORCE_HTTPS=false

# Optional — only if you'll use the AI Assistant at /ai-chat/
export MCP_INTERNAL_URL=http://localhost:5008/mcp
export MOH_PUBLIC_URL=http://localhost:8088/
export MOH_AI_PROVIDER=gemini       # or claude, openai
# Set the matching API key by hand:
# export GEMINI_API_KEY=AIza...
EOF
source ~/.bashrc
```

**Verify:**
```bash
echo $SUPERSET_CONFIG_PATH      # should print /home/.../moh-superset/superset_config.py
echo $FLASK_APP                  # should print "superset"
test -f "$SUPERSET_CONFIG_PATH" && echo OK || echo FAIL
python -c "exec(open('$SUPERSET_CONFIG_PATH').read()); print('config loads OK')"
```

### 3.7 Bootstrap the metadata DB + create admin

```bash
superset db upgrade           # creates all metadata tables — takes 30-60s
superset fab create-admin     # interactive: pick username, password, email
superset init                 # populates roles & permissions
```

**Verify:**
```bash
psql "$SUPERSET_DATABASE_URI" -c "\dt" | head -20
# Should list many tables: dashboards, slices, tables, ab_user, ...

psql "$SUPERSET_DATABASE_URI" -c "SELECT username FROM ab_user;"
# Should show the admin user you just created.
```

### 3.8 Run

Run the following in **separate terminals** (open 4 tabs). In each terminal, activate the venv and export env vars first:

```bash
source ~/moh-superset/.venv/bin/activate
source ~/.bashrc   # loads SUPERSET_CONFIG_PATH, MOH_FORCE_HTTPS=false, etc.
```

---

**Terminal 1 — Redis** (verify it is already running as a system service):

```bash
redis-cli ping
# Expected: PONG
# If not running:
sudo systemctl start redis-server
```

---

**Terminal 2 — Gunicorn (web server)**:

```bash
gunicorn \
  --bind 0.0.0.0:8088 \
  --workers 4 \
  --worker-class gthread \
  --threads 20 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  "superset.app:create_app()"
```

> Workers guideline: `2 × CPU cores`. For a 2-core VM use `4`.
> Do **not** use `gevent` — it requires extra setup and is unstable locally. Use `gthread`.

Wait until the logs show workers registering (MCP tools, blueprint lines). Then verify:

```bash
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8088/health
# Expected: HTTP 200

curl -sS http://127.0.0.1:8088/static/assets/manifest.json | head -c 80
# Expected: JSON starting with {"entrypoints"...
# If "404 Not Found": section 3.5 (frontend build) was skipped — go back and re-run.
```

---

**Terminal 3 — Celery worker** (required for SQL Lab async queries):

```bash
celery -A superset.tasks.celery_app:app worker \
  --loglevel=info \
  -O fair \
  -c 4
```

> Without this, SQL Lab queries appear to load forever — they are dispatched to the
> Celery queue but never executed.

---

**Terminal 4 — Celery beat** (required for scheduled reports & alerts, optional otherwise):

```bash
celery -A superset.tasks.celery_app:app beat \
  --loglevel=info
```

---

**Open the browser** to `http://localhost:8088` (or `http://your-vm-ip:8088`):
- Should show MoH logo + branded login → log in with the admin user → land on the MoH dashboard tiles.
- If it shows an **infinite spinner**: frontend assets are missing — re-run section 3.5.
- If the browser times out immediately: check that `MOH_FORCE_HTTPS=false` is exported (Gunicorn terminal). Without it, Superset redirects `http://` → `https://` and the browser cannot connect.

---

**Terminal 5 (optional) — MCP server** (required only for the AI Assistant at `/ai-chat/`):

```bash
superset mcp run --host 127.0.0.1 --port 5008
```

### 3.9 Run as system services (systemd) 

Use this instead of section 3.8 for a persistent setup that survives reboots.
All 4 services are managed by systemd — no terminal stays open.

**Step 1 — Get your username:**
```bash
whoami
# example: habtech
```

**Step 2 — Create the environment file:**
```bash
nano /home/habtech/superset.env
```
```
SUPERSET_CONFIG_PATH=/home/habtech/moh-superset/superset_config.py
SUPERSET_REDIS_HOST=localhost
SUPERSET_REDIS_PORT=6379
SUPERSET_JWT_SECRET=<your-jwt-secret>
MOH_PUBLIC_URL=http://localhost:8088/
MOH_FORCE_HTTPS=false

# Optional — AI Assistant iframe (uncomment if using an external AI service)
# MOH_AI_IFRAME_URL=http://tgfai.habtechsolution.com/embed
# MOH_CSP_DEV_ORIGIN=http://tgfai.habtechsolution.com
```
```bash
chmod 600 /home/habtech/superset.env
```

**Step 3 — Create the web server service:**
```bash
sudo nano /etc/systemd/system/superset.service
```
```ini
[Unit]
Description=MoH Superset Web
After=network.target redis-server.service

[Service]
User=habtech
WorkingDirectory=/home/habtech/moh-superset
EnvironmentFile=/home/habtech/superset.env
ExecStart=/home/habtech/moh-superset/.venv/bin/gunicorn \
    --bind 0.0.0.0:8088 \
    --workers 4 \
    --worker-class gthread \
    --threads 20 \
    --timeout 120 \
    "superset.app:create_app()"
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Step 4 — Create the Celery worker service:**
```bash
sudo nano /etc/systemd/system/superset-worker.service
```
```ini
[Unit]
Description=MoH Superset Celery Worker
After=network.target redis-server.service

[Service]
User=habtech
WorkingDirectory=/home/habtech/moh-superset
EnvironmentFile=/home/habtech/superset.env
ExecStart=/home/habtech/moh-superset/.venv/bin/celery \
    -A superset.tasks.celery_app:app worker \
    --loglevel=info -O fair -c 4
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Step 5 — Create the Celery beat service:**
```bash
sudo nano /etc/systemd/system/superset-beat.service
```
```ini
[Unit]
Description=MoH Superset Celery Beat
After=network.target redis-server.service

[Service]
User=habtech
WorkingDirectory=/home/habtech/moh-superset
EnvironmentFile=/home/habtech/superset.env
ExecStart=/home/habtech/moh-superset/.venv/bin/celery \
    -A superset.tasks.celery_app:app beat \
    --loglevel=info
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Step 6 — Enable and start all services:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable redis-server superset superset-worker superset-beat
sudo systemctl start redis-server superset superset-worker superset-beat
```

**Step 7 — Verify all are running:**
```bash
sudo systemctl status superset superset-worker superset-beat redis-server
# All should show: active (running)
```

**Step 8 — Check logs if something fails:**
```bash
sudo journalctl -u superset -n 50 --no-pager
sudo journalctl -u superset-worker -n 50 --no-pager
```

**Step 9 — Open the browser:**

Go to `http://localhost:8088` — should show the MoH login page.

> **Oracle VirtualBox note:** if accessing from the host machine, either set the VM
> network adapter to **Bridged**, or add a port-forwarding rule:
> host `8088` → guest `8088`. Then use `http://<vm-ip>:8088`.

**After any config change:**
```bash
sudo systemctl restart superset superset-worker superset-beat
```

---

### 3.10 Production hardening: systemd + nginx

For prod, replace the `superset run` dev server with gunicorn under
systemd, and put nginx + TLS in front. Skip this for dev/test.

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
    --bind 127.0.0.1:8088 --workers 4 --threads 20 --timeout 120 --worker-class gthread \
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
FLASK_APP=superset
MOH_FORCE_HTTPS=true

# ── Redis ──────────────────────────────────────────────────────────────────
# SUPERSET_REDIS_HOST: hostname or IP of the Redis server.
#   Default: localhost  (Redis running on the same machine)
#   Change to a remote IP if Redis is on a separate server, e.g. 10.0.0.5
SUPERSET_REDIS_HOST=localhost

# SUPERSET_REDIS_PORT: Redis port.
#   Default: 6379  (Redis default — only change if you run Redis on a custom port)
SUPERSET_REDIS_PORT=6379

# These two variables control ALL Redis usage in Superset:
#   DB 0 — Celery broker (task queue)
#   DB 1 — UI/metadata cache         (CACHE_CONFIG,         TTL 24h)
#   DB 2 — Chart query result cache  (DATA_CACHE_CONFIG,    TTL 1h)
#   DB 3 — Dashboard thumbnails      (THUMBNAIL_CACHE_CONFIG)
#   DB 4 — Async query job state     (GLOBAL_ASYNC_QUERIES)
#   DB 5 — SQL Lab results           (RESULTS_BACKEND)
#   DB 6 — Celery task results
# All DBs share the same Redis instance — no extra config needed.

# --- AI Assistant page (admin-only at /ai-chat/) ---
MOH_AI_PROVIDER=gemini              # or claude, openai
GEMINI_API_KEY=AIza...              # one or more keys, fallbacks rotate on 429
# GEMINI_API_KEY_2=...
# ANTHROPIC_API_KEY=sk-ant-...      # if MOH_AI_PROVIDER=claude
# OPENAI_API_KEY=sk-...             # if MOH_AI_PROVIDER=openai
MCP_INTERNAL_URL=http://localhost:5008/mcp     # native MCP runs on localhost
MOH_PUBLIC_URL=https://analytics.moh.gov.et/   # match your nginx hostname
```

**Verify Redis is reachable after setting the variables:**
```bash
source ~/superset.env   # or: set -a; source ~/superset.env; set +a
redis-cli -h $SUPERSET_REDIS_HOST -p $SUPERSET_REDIS_PORT ping
# Expected: PONG
```

**Apply after any change:**
```bash
sudo systemctl restart superset superset-worker
```

For the AI Assistant, also add a `superset-mcp.service` systemd unit that
runs `superset mcp run --host 127.0.0.1 --port 5008` (same `EnvironmentFile`
as the web service). Don't proxy `/mcp` through nginx unless you've enabled
JWT auth on the MCP endpoint — by default it's only safe over localhost.

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

## 4. Mobile Responsiveness

The MoH deployment includes **global responsive CSS** that makes dashboards work on phones, tablets, and desktops. This is implemented via `superset/templates/head_custom_extra.html`, which is injected into every Superset page.

### 4.1 Responsive Breakpoints

| Breakpoint | Screen Size | Behavior |
|---|---|---|
| **≥ 901px** | Desktop | Dashboard grid uses 12-column layout; filter sidebar (260px) visible; full-width modals |
| **768–900px** | Tablet | Dashboard grid uses 12-column layout; filter sidebar visible but may need scrolling; toolbar wraps if needed |
| **577–767px** | Large phone | Dashboard grid collapses to **1 column** (full width); filter sidebar may overflow; text readable |
| **≤ 576px** | Small phone | Extreme compression: minimal padding (4px), 44x44px touch targets, full-width forms, tables scroll horizontally |

### 4.2 What's Responsive

Handled automatically by `head_custom_extra.html`:
- ✅ **Dashboard grid** → collapses to 1 column on mobile
- ✅ **Charts** → scale to viewport (min-height 280px, max-height 60vh)
- ✅ **Touch targets** → 44x44px minimum on mobiles (buttons, links, inputs)
- ✅ **Tables** → scroll horizontally instead of breaking layout
- ✅ **Modals** → full-screen on phones, centered on desktop
- ✅ **Navigation** → tighter padding on small screens
- ✅ **Forms** → full-width inputs on mobile

### 4.3 Testing Mobile Responsiveness

**In Chrome DevTools:**
```
1. Press F12 to open DevTools
2. Click Device Toolbar icon (top-left, looks like a phone/tablet)
   or press Ctrl+Shift+M
3. Select a device:
   - iPhone SE (375px) → small phone
   - iPad (768px) → tablet
   - Custom 414x896 → typical Android phone
4. Reload page (F5) and scroll through dashboard
```

**On a real device:**
```bash
# Find your machine IP
ip addr show

# From phone on the same network, visit:
http://<YOUR-IP>:8088
```

### 4.4 Customizing Responsive Breakpoints

Edit `superset/templates/head_custom_extra.html` to change breakpoints or chart heights:

```css
/* Current breakpoints: adjust these pixel values to match your needs */
@media (max-width: 767px) { ... }    /* Phones */
@media (max-width: 640px) { ... }    /* Smaller phones */
@media (max-width: 576px) { ... }    /* Tiny phones */
@media (max-width: 380px) { ... }    /* Extra small phones */

/* Current chart sizing: adjust if charts are too tall/short on mobile */
@media (max-width: 767px) {
  .dashboard-component-chart-holder {
    min-height: 280px !important;    /* Adjust this */
    max-height: 60vh !important;     /* Adjust this */
  }
}
```

### 4.5 Debugging Unresponsive Dashboards

**If your dashboard isn't responsive:**

1. **Check the template is loaded:**
   ```bash
   grep -l "head_custom_extra" superset/templates/base.html superset/templates/superset/spa.html
   # Should print one or both filenames
   ```

2. **Verify styles are in the browser:**
   - Open DevTools (F12)
   - Go to Elements tab
   - Search for `@media (max-width: 767px)`
   - If not found, the template didn't load — restart Superset

3. **Check for conflicting inline styles:**
   - In DevTools Inspector, click a chart
   - Look for `style="width: NNNpx"` (inline styles)
   - If present, CSS `!important` flags should override, but if not → file a bug report

4. **Clear browser cache:**
   - Hard-refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
   - Or open DevTools → Disable cache (checkbox in Settings)

5. **Check if this is a known Superset issue:**
   - Some Superset charts (ECharts, Vega) measure themselves at render time
   - After viewport resize on desktop, they may not instantly re-fit
   - This is **not a problem on real phones** (orientation change triggers resize)
   - This is a limitation, not a bug

### 4.6 Touch-Friendly Spacing

MOH defaults are optimized for healthcare workers using phones in clinical settings:
- Buttons: 44x44px minimum (exceeds Apple HIG standard of 44x44px)
- Touch targets: 3px padding from edges (easier to tap)
- Spacing: wider gaps between clickable elements on mobile

To increase touch targets further, edit `head_custom_extra.html`:
```css
@media (max-width: 767px) {
  .ant-btn {
    min-height: 48px !important;  /* Increase from 44px */
    min-width: 48px !important;
  }
}
```

### 4.7 Performance on Mobile

Responsive CSS has minimal performance impact:
- Media queries are evaluated only on page load and orientation change
- Grid reflow is hardware-accelerated in modern browsers
- No JavaScript required — pure CSS

However, **chart SVG rendering** can be slow on low-end phones:
- If dashboards are slow, reduce the number of charts per view
- Use `THUMBNAIL_CACHE_CONFIG` (24h TTL) to cache expensive thumbnails
- Consider disabling auto-refresh on mobile by default

---

## 5. Docker development (Windows) — quick reference

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

### 5.4 Performance tuning

All performance settings live in `superset/moh_branding.py` and are applied to both runtimes automatically.

| Setting | Value | Purpose |
|---|---|---|
| `CACHE_CONFIG` TTL | 24 hours | UI/metadata cache (Redis DB 1) |
| `DATA_CACHE_CONFIG` TTL | 1 hour | Chart query result cache (Redis DB 2) |
| `THUMBNAIL_CACHE_CONFIG` | 24 hours | Dashboard thumbnail cache (Redis DB 3) |
| `GLOBAL_ASYNC_QUERIES` | enabled | Charts load in parallel, not sequentially |
| `GLOBAL_ASYNC_QUERIES_REDIS_CONFIG` | Redis DB 4 | Async query job state |
| `RESULTS_BACKEND` | Redis DB 5 | SQL Lab results (in-memory vs filesystem) |

To pre-warm the cache after a data update:
```bash
superset cache-warmup --strategy top_n_dashboards --top-n 10
```

To increase gunicorn workers (edit the systemd service file on the server):
```ini
--workers 8 --worker-class gthread --threads 20
```

### 5.5 Customizing the landing page

- **Layout / styling**: [superset/templates/superset/landing.html](superset/templates/superset/landing.html) — pure HTML/CSS, hot-reloads in dev mode
- **What's listed / featured logic**: [superset/landing_view.py](superset/landing_view.py) — the `MoHLandingView.index()` method
- **Add data to the template**: pass extra kwargs to `self.render_template(...)` from the view

---

## 6. Environment Variables

All variables read by this project's own code. CI/CD and Docker-internal variables are excluded — those only matter inside containers.

### 6.1 Required for native Ubuntu run

These must be set (or exported) before starting Gunicorn, Celery, or `superset run`.

| Variable | Default | Purpose |
|---|---|---|
| `SUPERSET_CONFIG_PATH` | — | Absolute path to `superset_config.py`. **Must be set.** |
| `SUPERSET_SECRET_KEY` | placeholder | Session/CSRF encryption key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(42))"`. **Must be changed in production.** |
| `SUPERSET_DATABASE_URI` | `postgresql://superset:root@localhost:5432/superset` | Postgres metadata DB connection string |
| `SUPERSET_REDIS_HOST` | `localhost` | Redis hostname used by cache and Celery broker |
| `SUPERSET_REDIS_PORT` | `6379` | Redis port |
| `MOH_FORCE_HTTPS` | `true` | Set `false` for local/HTTP. When `true`, Superset redirects `http://` → `https://` and sets `Secure` on cookies. **Always `false` unless behind nginx+TLS.** |

### 6.2 MoH-specific (branding, AI, MCP)

| Variable | Default | Purpose |
|---|---|---|
| `MOH_PUBLIC_URL` | `http://localhost:8090/` | Public-facing base URL — used to build explore/dashboard links in AI chat replies |
| `MOH_AI_PROVIDER` | — | AI backend for `/ai-chat/`: `gemini`, `claude`, or `openai` |
| `MCP_INTERNAL_URL` | `http://localhost:5008/mcp` | Internal MCP server URL — AI chat agent calls this to query Superset |
| `MOH_CSP_DEV_ORIGIN` | — | Dev server origin added to CSP `frame-ancestors` (e.g. `http://localhost:9000`) |
| `MOH_AI_IFRAME_URL` | — | External AI service URL to embed inside `/ai-chat/` instead of the built-in chat |

### 6.3 AI provider API keys (only if using `/ai-chat/`)

Set only the key matching `MOH_AI_PROVIDER`.

| Variable | Provider |
|---|---|
| `GEMINI_API_KEY` | Google Gemini (`MOH_AI_PROVIDER=gemini`) |
| `ANTHROPIC_API_KEY` | Claude (`MOH_AI_PROVIDER=claude`) |
| `OPENAI_API_KEY` | OpenAI (`MOH_AI_PROVIDER=openai`) |

### 6.4 MCP server

| Variable | Default | Purpose |
|---|---|---|
| `FASTMCP_HOST` | `127.0.0.1` | MCP server bind host |
| `FASTMCP_PORT` | `5008` | MCP server bind port |
| `FASTMCP_TRANSPORT` | `stdio` | Transport type: `stdio` (CLI mode) or `http` (server mode) |

### 6.5 Logging

| Variable | Default | Purpose |
|---|---|---|
| `SUPERSET_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `FLASK_DEBUG` | `false` | Enable Flask auto-reload and debug error pages (dev only) |

### 6.6 Docker dev only

These are only needed when running via `docker compose` and have no effect on native Ubuntu.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_HOST` / `DATABASE_USER` / `DATABASE_PASSWORD` / `DATABASE_DB` / `DATABASE_PORT` | `db` / `superset` / `superset` / `superset` / `5432` | Postgres connection for Docker Compose |
| `REDIS_HOST` / `REDIS_PORT` | `redis` / `6379` | Redis for Docker Compose |
| `SUPERSET_PORT` | `8088` | Exposed web port on the host |
| `DEV_MODE` | `true` | Enables dev features (hot reload, etc.) |
| `SUPERSET_LOAD_EXAMPLES` | `yes` | Load sample datasets on first `superset init` |
| `BUILD_SUPERSET_FRONTEND_IN_DOCKER` | `true` | Build the React SPA inside the container |
| `MAPBOX_API_KEY` | — | Mapbox token for map visualisations |

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard **not responsive on mobile** — charts don't stack vertically, sidebar too wide, text overflows | CSS in `head_custom_extra.html` not being applied, or browser cache | Hard-refresh (`Ctrl+Shift+R`), verify `head_custom_extra.html` exists in the template folder, check Chrome DevTools (F12 → Styles) that media queries are loaded |
| Mobile dashboard loads but **charts still show at fixed width** | Hardcoded React component widths override CSS — or the `!important` flags in media queries are not working | File an issue with the exact viewport width; check DevTools Inspector for inline `style="width: XXXpx"` overrides. May require React component changes in `superset-frontend/` |
| **Touch targets too small** on mobile buttons | Default button height is 36px, should be 44px per Apple HIG | Already fixed in `head_custom_extra.html` media query `@media (max-width: 640px)` — clear browser cache and restart. If still too small, check that the override file is loading (Chrome DevTools → Sources → search "head_custom_extra") |
| **Charts don't re-fit after viewport resize** | Some Superset charts (ECharts, Vega) measure SVG size at render time, not on resize | This is expected on desktop live-resizing (not a phone issue). Charts re-fit correctly on initial load and on device orientation change. Limitation documented in `head_custom_extra.html` comment |
| SQL Lab query **loads forever**, never returns results | Celery worker not running — queries queue in Redis but nothing executes them | Start Terminal 3 (Celery worker). Verify with `celery -A superset.tasks.celery_app:app inspect active` |
| Browser stuck on infinite loading spinner, blank page; `curl /health` returns 200 | Frontend assets were never built — `superset/static/assets/` is empty | Run section 3.5: `cd superset-frontend && npm install && npm run build`. Verify with `ls superset/static/assets/ \| head -5`. Restart Gunicorn after the build completes |
| 404 on `/static/assets/manifest.json` | Same as above — no built frontend bundle | See above |
| `superset run` succeeds but no `/static/assets/` directory exists | `npm run build` was never run, or it errored silently | Re-run with `cd superset-frontend && npm run build 2>&1 \| tee build.log` and read `build.log` for the actual failure |
| Logo still shows Superset default | Browser cache, or `THEME_DEFAULT` not re-seeded | Hard-refresh; restart `superset` container/service |
| `Can't load plugin: sqlalchemy.dialects:clickhousedb.connect` | ClickHouse drivers not installed | `uv pip install -r requirements/moh.txt` (or `docker exec ... uv pip install ...` for runtime fix) |
| `AttributeError: 'NoneType' object has no attribute 'database_after_insert'` | Importing a view too early during FAB setup | Don't import from `superset.views.*` inside `configure_fab()` — use top-level modules like `superset.landing_view` |
| `ClickHouse Code: 215. NOT_AN_AGGREGATE` errors on charts | Time column alias collision with `dateTrunc` wrapper | Add a pre-truncated calculated column to the dataset; use it as the X-axis with `No time grain` |
| Landing page works but menu links broken | Routes haven't changed; the React SPA still owns `/dashboard/list/` etc. | Click any link in the landing nav — they go to the standard Superset SPA which has its own React menu |
| `AttributeError: module 'numpy' has no attribute 'product'` during boot | Superset 6.x source still uses `np.product` (removed in numpy 2.0) | `pip install "numpy<2.0"` — also pinned in `requirements/moh.txt` |
| `Failed to import config` + `PermissionError: '/var/lib/superset'` | Old `superset_config.py` from before the resilient-defaults fix | `cp superset_config.example.py superset_config.py` (the new template defaults to `~/.superset/sqllab` and creates it automatically) |
| `psycopg2.OperationalError: password authentication failed for user "superset"` | Either `SUPERSET_DATABASE_URI` not set (config falls back to literal `CHANGE_ME`), or Postgres is on `peer`/`ident` auth | Set the env var; in `pg_hba.conf` change `peer`/`ident` → `md5` and `sudo service postgresql restart` |
| Boot logs show MCP tools registering but no `Registering blueprint: moh_ai_chat` | Custom config failed to import silently — Superset logs `Failed to import config ...` and falls back to defaults (no `BLUEPRINTS`) | Run `python -c "import os; os.environ['SUPERSET_CONFIG_PATH']='$PWD/superset_config.py'; from superset.app import create_app; create_app()"` to surface the real exception |
| `npm ci` fails with `EACCES rmdir` (WSL on `/mnt/c`) | Linux file permissions don't apply on NTFS via 9P | Run npm from Windows PowerShell, or clone the repo to `~/moh-superset` (WSL filesystem) and build there |
| `pip install -e .` fails with `PermissionError` on a build artifact | Files left as `root` from prior Docker bind-mount run | `sudo chown -R $USER:$USER .` from the repo root, retry |
| AI chat: switching `MOH_AI_PROVIDER` doesn't take effect | `docker compose restart` doesn't re-read `env_file:`; only `up -d --force-recreate` does | `docker compose up -d --force-recreate --no-deps superset` |
