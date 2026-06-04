<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
-->

# MoH Superset — Production Setup (Ubuntu)

## 1. Prerequisites

Install system dependencies:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv redis-server postgresql postgresql-contrib
```

Start and enable Redis and Postgres:

```bash
sudo systemctl enable --now redis-server
sudo systemctl enable --now postgresql
```

Create the Postgres database and user:

```bash
sudo -u postgres psql <<SQL
CREATE USER superset WITH PASSWORD 'STRONG_PW';
CREATE DATABASE superset OWNER superset;
SQL
```

---

## 2. Project Setup (one time)

```bash
cd ~/moh-superset

# Create and activate virtualenv
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[postgres]"

# Copy config
cp superset_config.example.py superset_config.py
```

Set required environment variables (add to `~/.bashrc` or a `.env` file you source):

```bash
export SUPERSET_CONFIG_PATH=~/moh-superset/superset_config.py
export SUPERSET_DATABASE_URI=postgresql://superset:STRONG_PW@localhost:5432/superset
export SUPERSET_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(42))")
export SUPERSET_REDIS_HOST=localhost
export SUPERSET_REDIS_PORT=6379

# Disable HTTPS redirect when not behind a TLS terminator (local / HTTP setup)
export MOH_FORCE_HTTPS=false
```

Run one-time database setup:

```bash
source .venv/bin/activate
source ~/moh-superset/.env   # or re-export the vars above

superset db upgrade
superset init
```

---

## 3. Running (4 terminals)

Open 4 separate terminal tabs/windows. In **each** terminal, first activate the venv and export vars:

```bash
source ~/moh-superset/.venv/bin/activate
export SUPERSET_CONFIG_PATH=~/moh-superset/superset_config.py
export SUPERSET_DATABASE_URI=postgresql://superset:STRONG_PW@localhost:5432/superset
export SUPERSET_SECRET_KEY=<your-generated-key>
export MOH_FORCE_HTTPS=false
```

---

### Terminal 1 — Redis

Redis is usually already running as a system service. Verify:

```bash
redis-cli ping
# Should print: PONG
```

If not running:

```bash
sudo systemctl start redis-server
```

---

### Terminal 2 — Gunicorn (web server)

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

Open `http://localhost:8088` in your browser.

> **Workers guideline:** set `--workers` to `2 × CPU cores`. For a 2-core VM use `4`.

---

### Terminal 3 — Celery Worker (async queries, thumbnails, alerts)

```bash
celery -A superset.tasks.celery_app:app worker \
  --loglevel=info \
  -O fair \
  -c 4
```

This is required for SQL Lab async queries to return results. Without it, queries will appear to load forever.

---

### Terminal 4 — Celery Beat (scheduled reports & alerts)

```bash
celery -A superset.tasks.celery_app:app beat \
  --loglevel=info
```

Only needed if you use scheduled reports or email alerts. Can be skipped for basic usage.

---

## 4. Verifying everything is up

| Check | Command |
|---|---|
| Redis | `redis-cli ping` → `PONG` |
| Postgres | `psql $SUPERSET_DATABASE_URI -c "SELECT 1"` |
| Gunicorn | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8088` → `200` or `302` |
| Celery | `celery -A superset.tasks.celery_app:app inspect active` |

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Browser times out on `http://localhost:8088` | `MOH_FORCE_HTTPS=true` redirects HTTP→HTTPS | Set `export MOH_FORCE_HTTPS=false` |
| SQL Lab query loads forever | Celery worker not running | Start Terminal 3 |
| `PONG` missing from `redis-cli ping` | Redis not running | `sudo systemctl start redis-server` |
| `Connection refused` on port 8088 | Gunicorn not started | Start Terminal 2 |
| `ModuleNotFoundError` | Virtualenv not activated | `source .venv/bin/activate` |

---

## 6. Production behind Nginx + TLS

When deploying behind Nginx with a valid TLS certificate, set `MOH_FORCE_HTTPS=true` (the default) and add `ENABLE_PROXY_FIX = True` to `superset_config.py` so Superset trusts the `X-Forwarded-*` headers from Nginx.

For the full upstream Superset installation docs:
**[📚 Installation Guide →](https://superset.apache.org/docs/installation/installation-methods)**
