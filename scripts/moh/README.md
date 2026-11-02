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

# MoH production deploy: `deploy-frontend.sh`

Pulls `origin/master`, builds the frontend, restarts `moh-superset.service`
and checks the result on the production host (`/var/etls/moh-superset`).
Run it on the server as `sysadmin`, never with `sudo`. It asks for the sudo
password once, for `systemctl` and `journalctl`.

```bash
cd /var/etls/moh-superset
scripts/moh/deploy-frontend.sh --dry-run        # preflight + incoming commits only
scripts/moh/deploy-frontend.sh                  # deploy (asks to confirm)
scripts/moh/deploy-frontend.sh --with-celery    # also restart celery (Python changes)
scripts/moh/deploy-frontend.sh --rollback       # undo the last successful deploy
scripts/moh/deploy-frontend.sh --prune-assets --dry-run   # list old bundle files
```

## Why not `git pull && npm run build` in place

| Problem | Effect | What the script does |
|---|---|---|
| webpack `output.clean = true` empties `superset/static/assets` when the build starts | gunicorn workers (recycled every ~1000 requests) load an empty `manifest.json` and serve **blank pages**; a failed build leaves the site with no assets | builds in a separate worktree `/var/etls/moh-superset-build`, then copies files in without deleting old ones, `manifest.json` last with an atomic rename |
| `node_modules` older than `package-lock.json` | "Module not found" build errors | its own `node_modules`, `npm ci` whenever the lockfile or Node version changes |
| system Node v23, repo pins v22 (`.nvmrc`) | build differences | refuses unless a v22 Node is found (`NODE_HOME` or `/var/etls/tools/node-v22.*`) or `--allow-node-mismatch` |
| build uses an 8 GB heap; swap often full | OOM risk for Superset/ClickHouse | refuses if `MemAvailable` < 10 GB; runs the build with `nice`/`ionice`; warns when an ETL is running |
| builds run as root | root-owned files | refuses to run as root |
| migrations / requirements changes | app fails after restart | refuses; do pip + `superset db upgrade` by hand (after a DB backup), then `--allow-backend-changes` |

## Checks after the restart (and again 45 s later)

* unit `active`, `NRestarts` unchanged, `/health` returns `OK`
* no `Worker failed to boot` / `ImportError` / `CRITICAL` lines in the journal since the restart
* `/login/` serves the hashed entry bundles from the **new** `manifest.json`, and each returns 200
* `PUBLIC_URL/health` if `PUBLIC_URL` is set; celery units active with `--with-celery`

If any of these fail, the script rolls back automatically: `git reset --keep` to
the previous commit, restores the previous `manifest.json` and `service-worker.js`,
restarts, and checks again.

State, logs and release records are kept in `/var/etls/moh-superset-deploy`
(`logs/`, `releases/<timestamp>/` with `build.log`, `npm-ci.log`,
`assets-before.tar.gz`). All paths can be overridden through environment variables (see the
top of the script).

One-time setup for the pinned Node version (no sudo needed):

```bash
mkdir -p /var/etls/tools && cd /var/etls/tools
curl -fsSLO https://nodejs.org/dist/v22.22.0/node-v22.22.0-linux-x64.tar.xz
tar xf node-v22.22.0-linux-x64.tar.xz
```
