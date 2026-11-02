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

# MoH production deploy: `deploy.sh`

Deploys `origin/master` to the production host (`/var/etls/moh-superset`): pull,
frontend build, backend update (packages, DB migrations, permissions), restart, and checks.
Run it on the server as `sysadmin`, never with `sudo`. It asks for the sudo password
once (for `systemctl`, `journalctl`, `pg_dump` and the Superset CLI).

```bash
cd /var/etls/moh-superset
scripts/moh/deploy.sh --dry-run          # preflight, incoming commits, planned steps
scripts/moh/deploy.sh                    # full deploy (asks to confirm)
scripts/moh/deploy.sh --frontend-only    # build + assets only, no backend steps
scripts/moh/deploy.sh --backend-only     # no frontend build
scripts/moh/deploy.sh --rollback         # undo the last deploy (code, packages, assets)
scripts/moh/deploy.sh --rollback --restore-db   # ... and the metadata DB from its dump
scripts/moh/deploy.sh --prune-assets --dry-run  # list old bundle files
```

## What a full deploy runs

| Step | When it runs |
|---|---|
| frontend build in `/var/etls/moh-superset-build` | always (skip with `--backend-only`) |
| `pg_dump` of `moh_superset` (cluster `16/main`) | always for backend deploys, before any change |
| `uv pip install -r requirements/moh.txt` | always; a no-op when the venv already matches (preflight shows the changes) |
| `superset db upgrade` | always; a no-op at head |
| `superset init` | only if the update touches `superset/security/`, `views/`, `initialization/`, `migrations/versions/`, `constants.py`, `config.py` or any `api.py` (or `--superset-init`) |
| restart celery worker/background/beat | only if Python code or dependencies changed (`--with-celery` / `--no-celery`) |

`requirements/moh.txt` is the full pinned set that production runs. Do **not** install
`requirements/base.txt`: it would downgrade dozens of packages, including security fixes.

The Superset CLI runs through `systemd-run` with the service's own `EnvironmentFile` and
`Environment=`, so the secrets never pass through the shell. `db upgrade` and `init`
run from the build worktree, so the live tree stays on the old code until just before the restart.

## Why not `git pull && npm run build` in place

| Problem | Effect | What the script does |
|---|---|---|
| webpack `output.clean = true` empties `superset/static/assets` when the build starts | gunicorn workers (recycled every ~1000 requests) load an empty `manifest.json` and serve **blank pages**; a failed build leaves the site with no assets | builds in a separate worktree, copies files in without deleting old ones, `manifest.json` last with an atomic rename |
| `node_modules` older than `package-lock.json` | "Module not found" build errors | its own `node_modules`, `npm ci` whenever the lockfile or Node version changes |
| system Node v23, repo pins v22 (`.nvmrc`) | build differences | uses `/var/etls/tools/node-v22.*` (or `NODE_HOME`); refuses otherwise |
| build uses an 8 GB heap; swap often full | OOM risk for Superset/ClickHouse | refuses if `MemAvailable` < 10 GB; runs the build with `nice`/`ionice`; warns when an ETL is running |
| builds run as root | root-owned files | refuses to run as root |

## Checks after the restart (and again 45 s later)

* unit `active`, `NRestarts` unchanged, `/health` returns `OK`
* no `Worker failed to boot` / `ImportError` / `ModuleNotFoundError` lines in the journal since the restart
  (`WORKER TIMEOUT` and Tracebacks are reported as warnings)
* `/login/` serves the hashed entry bundles from the **new** `manifest.json`, and each returns 200
* `PUBLIC_URL/health` if `PUBLIC_URL` is set; celery units active when they were restarted

## Rollback

If any check fails, the script rolls back automatically: `git reset --keep` to the previous
commit, reinstalls the previous Python packages (`pip-freeze-before.txt`) if they changed,
restores `manifest.json` and `service-worker.js`, restarts, and checks again.

If a **DB migration was applied**, it does not roll back automatically: old code on a
migrated schema is unsafe, and restoring the dump discards dashboard/chart/user edits
made since. It prints `deploy.sh --rollback --restore-db`, which stops the services, runs
`pg_restore --clean --single-transaction`, rolls back code, packages and assets, and starts them again.

Release records in `/var/etls/moh-superset-deploy/releases/<timestamp>/` (last 5 kept): `build.log`,
`npm-ci.log`, `db-upgrade.log`, `assets-before.tar.gz`, `pip-freeze-before.txt`,
`moh_superset.dump`, `status`. All paths can be overridden through environment variables (see the top
of the script).

One-time setup for the pinned Node version (no sudo needed):

```bash
mkdir -p /var/etls/tools && cd /var/etls/tools
curl -fsSLO https://nodejs.org/dist/v22.22.0/node-v22.22.0-linux-x64.tar.xz
tar xf node-v22.22.0-linux-x64.tar.xz
```
