#!/usr/bin/env bash
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Safe production deploy for MoH Superset: pull, frontend build, backend update, restart, verify.
#
# Run ON the server, as sysadmin (not root):
#   /var/etls/moh-superset/scripts/moh/deploy.sh --dry-run    # preflight only, changes nothing
#   /var/etls/moh-superset/scripts/moh/deploy.sh              # full deploy of origin/master
#   /var/etls/moh-superset/scripts/moh/deploy.sh --rollback   # undo the last deploy
#
# Steps of a full deploy:
#   1. Preflight checks: service health, a clean git tree, a fast-forward-only update, the Node
#      version, free memory and disk, the metadata DB is reachable; shows the pip changes it would make.
#   2. Checks out the target commit in a SEPARATE worktree (BUILD_DIR) and builds the frontend
#      there. webpack's `output.clean` empties the assets dir it builds into, so building
#      in the live tree makes recycled gunicorn workers serve blank pages.
#   3. Records a release: previous commit, manifest, assets tarball, `pip freeze`, and a
#      pg_dump of the metadata DB.
#   4. Backend: `uv pip install -r requirements/moh.txt` (no-op when nothing changed),
#      `superset db upgrade` (no-op at head), and `superset init` ONLY when the update
#      touches permissions/views/APIs/migrations. Both CLI commands run from the build
#      worktree (new code) with the service's exact environment (systemd-run), so the
#      live tree stays on old code until just before the restart.
#   5. Fast-forwards the live checkout and copies new assets in without deleting old ones,
#      manifest.json last with an atomic rename.
#   6. Restarts moh-superset.service, plus the celery units when backend code changed.
#   7. Checks the service: unit active, no restart loop, /health OK, no worker boot errors,
#      and the login page serves the new bundles, each returning 200. Checks again after
#      STABILITY_WAIT seconds.
#   8. On failure it rolls back automatically (code, pip packages, manifest, restart) UNLESS
#      a DB migration was applied. Then it stops and prints the --rollback --restore-db
#      command, because restoring the DB discards metadata edits made since the dump.
#
# Exit codes: 0 ok, 1 failed, 2 preflight refused (nothing changed).

set -Eeuo pipefail

# --- Re-exec from a temp copy: `git merge` below may rewrite this very file. --------
if [[ -z "${MOH_DEPLOY_REEXEC:-}" ]]; then
  tmp_self="$(mktemp /tmp/moh-deploy.XXXXXX.sh)"
  cp -- "$0" "$tmp_self"
  chmod 700 "$tmp_self"
  export MOH_DEPLOY_REEXEC="$tmp_self" MOH_DEPLOY_ORIG="$0"
  exec bash "$tmp_self" "$@"
fi
trap 'rm -f -- "${MOH_DEPLOY_REEXEC:-}"' EXIT

# --- Settings (override through the environment) ---------------------------------------
LIVE_DIR="${LIVE_DIR:-/var/etls/moh-superset}"
BUILD_DIR="${BUILD_DIR:-/var/etls/moh-superset-build}"
STATE_DIR="${STATE_DIR:-/var/etls/moh-superset-deploy}"
SERVICE="${SERVICE:-moh-superset.service}"
CELERY_UNITS="${CELERY_UNITS:-superset-celery-worker.service superset-celery-worker-background.service superset-celery-beat.service}"
BRANCH="${BRANCH:-master}"
REMOTE="${REMOTE:-origin}"
LOCAL_URL="${LOCAL_URL:-http://127.0.0.1:9099}"
PUBLIC_URL="${PUBLIC_URL:-}"            # e.g. https://mohss.habtechsolution.com; checked if set
NODE_HOME="${NODE_HOME:-}"              # dir containing bin/node of the .nvmrc version
REQ_FILE="${REQ_FILE:-requirements/moh.txt}"   # full pinned set that prod runs (NOT base.txt)
DB_CLUSTER="${DB_CLUSTER:-16/main}"     # pg_lsclusters name of the metadata DB cluster
DB_NAME="${DB_NAME:-moh_superset}"
MIN_MEM_GB="${MIN_MEM_GB:-10}"          # build uses --max_old_space_size=8192
MIN_DISK_GB="${MIN_DISK_GB:-5}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-240}" # TimeoutStartSec=120 + 8 workers to boot
STABILITY_WAIT="${STABILITY_WAIT:-45}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"     # each keeps an assets tarball and a DB dump
export UV_CACHE_DIR="${UV_CACHE_DIR:-$STATE_DIR/uv-cache}"   # /home is small

# Changes under these paths make `superset init` run (permissions/roles sync).
INIT_PATHS_RE='^superset/(security/|views/|initialization/|migrations/versions/|constants\.py$|config\.py$|.*/api\.py$)'

# --- Flags ------------------------------------------------------------------------
DRY_RUN=0; ASSUME_YES=0; DO_FRONTEND=1; DO_BACKEND=1; CELERY=auto; FORCE_INIT=0
ALLOW_NODE_MISMATCH=0; FORCE_MEM=0; AUTO_ROLLBACK=1; MODE=deploy; RESTORE_DB=0

usage() {
  sed -n '20,23p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'
Options:
  --dry-run               preflight + show incoming commits and planned steps; change nothing
  --yes                   don't ask for confirmation
  --branch NAME           branch to deploy (default master)
  --frontend-only         skip pip / DB backup / db upgrade / superset init
  --backend-only          skip the frontend build (alias: --no-build)
  --with-celery           always restart the celery units
  --no-celery             never restart the celery units (default: only if backend changed)
  --superset-init         run `superset init` even if no relevant files changed
  --allow-node-mismatch   build with a Node that does not match .nvmrc
  --force-low-memory      build even if MemAvailable < MIN_MEM_GB
  --no-auto-rollback      leave the failed state in place for debugging
  --rollback              restore the previous release (code, packages, assets) and restart
  --rollback --restore-db also restore the metadata DB from that release's dump
                          (discards dashboard/chart/user edits made since the deploy)
  --prune-assets          delete asset files not used by the last 2 deploys
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --branch) BRANCH="$2"; shift ;;
    --frontend-only) DO_BACKEND=0 ;;
    --backend-only|--no-build) DO_FRONTEND=0 ;;
    --with-celery) CELERY=yes ;;
    --no-celery) CELERY=no ;;
    --superset-init) FORCE_INIT=1 ;;
    --allow-node-mismatch) ALLOW_NODE_MISMATCH=1 ;;
    --force-low-memory) FORCE_MEM=1 ;;
    --no-auto-rollback) AUTO_ROLLBACK=0 ;;
    --rollback) MODE=rollback ;;
    --restore-db) RESTORE_DB=1 ;;
    --prune-assets) MODE=prune ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done
(( DO_FRONTEND || DO_BACKEND )) || { echo "--frontend-only and --backend-only together leave nothing to do" >&2; exit 2; }

# --- Logging ----------------------------------------------------------------------
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$STATE_DIR"/{logs,releases}
LOG="$STATE_DIR/logs/deploy-$TS.log"
exec > >(tee -a "$LOG") 2>&1

c_red=$'\e[31m'; c_grn=$'\e[32m'; c_ylw=$'\e[33m'; c_bld=$'\e[1m'; c_off=$'\e[0m'
step() { echo; echo "${c_bld}==> $*${c_off}"; }
ok()   { echo "  ${c_grn}ok${c_off}   $*"; }
warn() { echo "  ${c_ylw}warn${c_off} $*"; }
info() { echo "       $*"; }
die()  { echo "  ${c_red}FAIL${c_off} $1"; echo "Log: $LOG"; exit "${2:-1}"; }
refuse() { die "$1" 2; }
confirm() {
  (( ASSUME_YES )) && return 0
  local a; read -r -p "  $* [y/N] " a </dev/tty; [[ "$a" =~ ^[Yy]$ ]]
}

echo "moh-superset deploy ($MODE) started $(date -Is) by $(id -un) on $(hostname)"
echo "Log: $LOG"

[[ "$(id -u)" -ne 0 ]] || refuse "do not run as root (it leaves root-owned files); run as sysadmin"

# One run at a time.
exec 9>"$STATE_DIR/deploy.lock"
flock -n 9 || refuse "another deploy is running (lock $STATE_DIR/deploy.lock)"

# --- Helpers ----------------------------------------------------------------------
git_live() { git -C "$LIVE_DIR" "$@"; }
unit_prop() { systemctl show -p "$2" --value "$1"; }
http_code() { curl -s -o /dev/null -m 20 -w '%{http_code}' "$1" || echo 000; }
uv_bin() { echo "$LIVE_DIR/.venv/bin/uv"; }
VENV_PY="$LIVE_DIR/.venv/bin/python"

# Run the Superset CLI with exactly the service's environment (EnvironmentFile +
# Environment=) via a transient systemd unit, so secrets never pass through this shell.
# $1 = directory whose `superset` package is imported (live or build worktree).
superset_cli() {
  local wd="$1"; shift
  local envf; envf="$(unit_prop "$SERVICE" EnvironmentFiles | awk '{print $1}')"
  local -a args=(--quiet --wait --pipe --collect --uid="$(id -un)" --gid="$(id -gn)"
                 -p "WorkingDirectory=$wd")
  [[ -n "$envf" ]] && args+=(-p "EnvironmentFile=$envf")
  local kv
  for kv in $(unit_prop "$SERVICE" Environment); do args+=(--setenv="$kv"); done
  sudo -n systemd-run "${args[@]}" "$VENV_PY" -c \
    'import sys; from superset.cli.main import superset; sys.argv[0] = "superset"; superset()' "$@"
}

db_revision() { # prints the alembic revision of the metadata DB ("" on failure)
  superset_cli "$1" db current 2>&1 | grep -oE '^[0-9a-f]{8,}' | tail -1 || true
}

pg() { # run a postgres client tool as the postgres OS user against the metadata cluster
  local tool="$1"; shift
  # sudo resets the environment: pass PGOPTIONS through explicitly
  (cd / && sudo -n -u postgres env "PGOPTIONS=${PGOPTIONS:-}" "$tool" --cluster "$DB_CLUSTER" "$@")
}

restart_units() { # $1 = 1 to include celery
  local units="$SERVICE"
  [[ "${1:-0}" == 1 ]] && units="$units $CELERY_UNITS"
  # shellcheck disable=SC2086
  sudo systemctl restart $units
}

wait_healthy() {
  local deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
  while (( $(date +%s) < deadline )); do
    if [[ "$(unit_prop "$SERVICE" ActiveState)" == active ]] \
       && [[ "$(curl -s -m 10 "$LOCAL_URL/health" || true)" == OK ]]; then
      return 0
    fi
    sleep 5
  done
  return 1
}

# Entry JS/CSS from manifest.json "entrypoints" (what the HTML should reference).
manifest_entries() {
  python3 - "$1" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
out = set()
for ent in m.get("entrypoints", {}).values():
    for kind in ("js", "css"):
        out.update(ent.get(kind, []))
print("\n".join(sorted(out)))
PY
}

# JS/CSS files referenced by src=/href= attributes (query strings dropped, host stripped).
page_bundles() {
  grep -oE '(src|href)="[^"]*/static/assets/[^"?]+\.(js|css)(\?[^"]*)?"' \
    | sed -E 's/^(src|href)="//; s/[?"].*$//; s#^https?://[^/]+##' | sort -u
}

# Check after restart: the app serves the bundle from the manifest now in place.
verify_service() {
  local since="$1" restarts_before="$2" expect_manifest="$3" celery="$4"
  local failed=0

  if wait_healthy; then ok "$SERVICE active and /health = OK"
  else warn "$SERVICE not healthy within ${HEALTH_TIMEOUT}s"; failed=1; fi

  local nr; nr="$(unit_prop "$SERVICE" NRestarts)"
  if [[ "$nr" == "$restarts_before" ]]; then ok "no systemd auto-restarts (NRestarts=$nr)"
  else warn "NRestarts went $restarts_before -> $nr (crash loop?)"; failed=1; fi

  # sysadmin is not in systemd-journal/adm: read through sudo (cached by `sudo -v`).
  local jr; jr="$(sudo -n journalctl -u "$SERVICE" --since "$since" --no-pager -o cat 2>/dev/null || true)"
  local fatal='Worker failed to boot|Exception in worker process|App failed to load|ModuleNotFoundError|ImportError'
  if [[ -z "$jr" ]]; then
    warn "could not read the journal (sudo timestamp expired?); journal check skipped"
  elif grep -qE "$fatal" <<<"$jr"; then
    warn "worker errors in journal since restart:"
    grep -nE "$fatal" <<<"$jr" | head -20 | sed 's/^/       /'
    failed=1
  else ok "no worker boot errors in journal"; fi
  # WORKER TIMEOUT also happens on slow ClickHouse queries, so it only warns.
  local wt; wt="$(grep -c 'WORKER TIMEOUT' <<<"$jr" || true)"
  (( wt == 0 )) || warn "$wt WORKER TIMEOUT line(s) since restart (slow queries or stuck boot?)"
  local tb; tb="$(grep -c 'Traceback' <<<"$jr" || true)"
  (( tb == 0 )) || warn "$tb Traceback(s) in journal since restart (sudo journalctl -u $SERVICE --since '$since' | grep -A20 Traceback)"

  local html; html="$(curl -s -m 30 "$LOCAL_URL/login/" || true)"
  local served; served="$(page_bundles <<<"$html" || true)"
  if [[ -z "$served" ]]; then
    warn "login page references no /static/assets bundles (blank page)"; failed=1
  else
    local f missing=0
    while read -r f; do
      [[ "$(http_code "$LOCAL_URL$f")" == 200 ]] || { warn "asset $f returned $(http_code "$LOCAL_URL$f")"; missing=1; }
    done <<<"$served"
    (( missing )) && failed=1 || ok "$(wc -l <<<"$served") bundles on /login/ all return 200"
    local want; want="$(manifest_entries "$expect_manifest")"
    local stale=0
    while read -r f; do
      # only hashed webpack entry files come from manifest.json
      [[ "$f" =~ \.entry\.(js|css)$ ]] || continue
      grep -qxF "$f" <<<"$want" || { warn "login page serves $f which is NOT in the deployed manifest"; stale=1; }
    done <<<"$served"
    (( stale )) && failed=1 || ok "login page serves the deployed bundle"
  fi

  if [[ -n "$PUBLIC_URL" ]]; then
    local pc; pc="$(http_code "$PUBLIC_URL/health")"
    [[ "$pc" == 200 ]] && ok "public $PUBLIC_URL/health = 200" || { warn "public health = $pc"; failed=1; }
  fi

  if [[ "$celery" == 1 ]]; then
    local u; for u in $CELERY_UNITS; do
      [[ "$(unit_prop "$u" ActiveState)" == active ]] && ok "$u active" || { warn "$u not active"; failed=1; }
    done
  fi
  return "$failed"
}

install_manifest() { # atomic replace of manifest.json (+ service-worker.js) from dir $1
  local src="$1" dst="$LIVE_DIR/superset/static"
  if [[ -f "$src/service-worker.js" ]]; then
    cp -p "$src/service-worker.js" "$dst/.service-worker.js.new"
    mv -f "$dst/.service-worker.js.new" "$dst/service-worker.js"
  fi
  cp -p "$src/manifest.json" "$dst/assets/.manifest.json.new"
  mv -f "$dst/assets/.manifest.json.new" "$dst/assets/manifest.json"
}

set_status() { echo "$1 $(date -Is)" >"$2/status"; }

release_flag() { cat "$1/$2" 2>/dev/null || echo 0; }

print_db_restore_help() { # $1 = release dir
  info "A DB migration was applied, so code-only rollback is unsafe. To restore everything:"
  info "  $LIVE_DIR/scripts/moh/deploy.sh --rollback --restore-db"
  info "(restores $1/$DB_NAME.dump: dashboard/chart/user edits made after the deploy are lost)"
}

# Roll back code, Python packages, manifest; optionally the DB. $1 = release dir.
do_rollback() {
  local rel="$1" restore_db="${2:-0}"
  [[ -f "$rel/prev_commit" ]] || die "release $rel has no prev_commit"
  local prev; prev="$(cat "$rel/prev_commit")"
  local celery; celery="$(release_flag "$rel" celery)"
  step "Rolling back to $prev (release $(basename "$rel"))"
  sudo -v

  if (( restore_db )); then
    [[ -s "$rel/$DB_NAME.dump" ]] || die "no DB dump in $rel"
    info "stopping $SERVICE and celery units for the DB restore"
    # shellcheck disable=SC2086
    sudo systemctl stop "$SERVICE" $CELERY_UNITS
    celery=1
    PGOPTIONS='-c lock_timeout=60s' pg pg_restore --clean --if-exists --single-transaction \
      --dbname "$DB_NAME" <"$rel/$DB_NAME.dump" \
      || die "pg_restore failed (DB unchanged: single transaction). Services are STOPPED; start them with: sudo systemctl start $SERVICE $CELERY_UNITS"
    ok "metadata DB restored from $(basename "$rel")/$DB_NAME.dump"
  fi

  if [[ "$(git_live rev-parse HEAD)" != "$prev" ]]; then
    git_live reset --keep "$prev" || die "git reset --keep failed; fix by hand: git -C $LIVE_DIR reset --keep $prev"
  fi
  ok "code at $(git_live log --oneline -1)"

  if [[ "$(release_flag "$rel" pip_changed)" == 1 ]]; then
    "$(uv_bin)" pip install --python "$VENV_PY" -r "$rel/pip-freeze-before.txt" \
      || die "restoring Python packages failed; retry: $(uv_bin) pip install --python $VENV_PY -r $rel/pip-freeze-before.txt"
    ok "Python packages restored from pip-freeze-before.txt"
  fi

  install_manifest "$rel/prev_static"
  ok "previous manifest.json / service-worker.js restored"

  local since; since="$(date '+%Y-%m-%d %H:%M:%S')"
  local nr; nr="$(unit_prop "$SERVICE" NRestarts)"
  if (( restore_db )); then
    # shellcheck disable=SC2086
    sudo systemctl start "$SERVICE" $CELERY_UNITS
  else
    restart_units "$celery"
  fi
  if verify_service "$since" "$nr" "$rel/prev_static/manifest.json" "$celery"; then
    ok "rollback verified"
    set_status "rolled_back$( (( restore_db )) && echo _with_db)" "$rel"
  else
    set_status rollback_unhealthy "$rel"
    die "service unhealthy after rollback. Assets tarball: $rel/assets-before.tar.gz; DB dump: $rel/$DB_NAME.dump"
  fi
}

# Release dirs whose deploy completed (status "deployed"), oldest first.
deployed_releases() {
  local d
  for d in "$STATE_DIR"/releases/*/; do
    [[ -f "$d/status" ]] && grep -q '^deployed' "$d/status" && echo "${d%/}"
  done
  return 0
}

# --- Mode: rollback -----------------------------------------------------------------
if [[ "$MODE" == rollback ]]; then
  last="$(deployed_releases | tail -1)"
  [[ -n "$last" ]] || refuse "no completed deploy to roll back in $STATE_DIR/releases"
  [[ "$(git_live rev-parse HEAD)" == "$(cat "$last/new_commit")" ]] \
    || refuse "live HEAD is not the commit that release deployed; someone changed it since. Roll back by hand."
  echo "Last deploy: $(basename "$last")  ($(cat "$last/prev_commit") -> $(cat "$last/new_commit"))"
  if [[ "$(release_flag "$last" db_migrated)" == 1 && "$RESTORE_DB" == 0 ]]; then
    print_db_restore_help "$last"
    refuse "refusing a code-only rollback over a migrated DB"
  fi
  (( RESTORE_DB )) && warn "this restores the metadata DB to its state at $(basename "$last"); later edits are lost"
  confirm "Roll back to $(cat "$last/prev_commit")$( (( RESTORE_DB )) && echo " and restore the DB")?" || refuse "aborted"
  do_rollback "$last" "$RESTORE_DB"
  exit 0
fi

# --- Mode: prune assets ---------------------------------------------------------------
if [[ "$MODE" == prune ]]; then
  mapfile -t rels < <(deployed_releases | tail -2)
  (( ${#rels[@]} == 2 )) || refuse "need 2 completed deploys recorded to prune safely"
  for r in "${rels[@]}"; do
    [[ -s "$r/new_assets.txt" ]] || refuse "$(basename "$r") has no asset list (backend-only deploy?); not pruning"
  done
  keep="$(mktemp)"
  { cat "${rels[0]}/new_assets.txt" "${rels[1]}/new_assets.txt"; echo manifest.json; echo .gitkeep; } | sort -u >"$keep"
  cand="$(cd "$LIVE_DIR/superset/static/assets" && find . -type f -printf '%P\n' | sort | comm -23 - "$keep")"
  rm -f "$keep"
  n="$(grep -c . <<<"$cand" || true)"
  echo "Files to delete: $n"; head -20 <<<"$cand"
  (( n > 0 )) || { ok "nothing to prune"; exit 0; }
  (( DRY_RUN )) && exit 0
  confirm "Delete these $n files from $LIVE_DIR/superset/static/assets?" || refuse "aborted"
  (cd "$LIVE_DIR/superset/static/assets" && xargs -d '\n' rm -f -- <<<"$cand")
  ok "pruned $n files"; exit 0
fi

# ============================ DEPLOY ===============================================
step "Preflight"
[[ -d "$LIVE_DIR/.git" ]] || refuse "$LIVE_DIR is not a git checkout"

[[ "$(unit_prop "$SERVICE" ActiveState)" == active ]] && ok "$SERVICE is active" \
  || warn "$SERVICE is NOT active before deploy ($(unit_prop "$SERVICE" ActiveState))"
pre_health="$(curl -s -m 10 "$LOCAL_URL/health" || true)"
[[ "$pre_health" == OK ]] && ok "/health = OK before deploy" || warn "/health before deploy: '${pre_health:-no answer}'"

cur_branch="$(git_live rev-parse --abbrev-ref HEAD)"
[[ "$cur_branch" == "$BRANCH" ]] || refuse "live checkout is on '$cur_branch', expected '$BRANCH'"
dirty="$(git_live status --porcelain --untracked-files=no)"
[[ -z "$dirty" ]] || refuse "live checkout has uncommitted changes to tracked files:
$dirty
Commit/stash them deliberately before deploying."
ok "live checkout on $BRANCH, no tracked changes"

git_live fetch --quiet "$REMOTE" "$BRANCH" || refuse "git fetch failed (deploy key / network?)"
PREV="$(git_live rev-parse HEAD)"
TARGET="$(git_live rev-parse "$REMOTE/$BRANCH")"
git_live merge-base --is-ancestor "$PREV" "$TARGET" \
  || refuse "live HEAD $PREV is not an ancestor of $REMOTE/$BRANCH (diverged/force-pushed); resolve by hand"

if [[ "$PREV" == "$TARGET" ]]; then
  ok "already at $REMOTE/$BRANCH ($(git_live log --oneline -1))"
else
  echo "  Incoming commits ($PREV..$TARGET):"
  git_live log --oneline --no-merges "$PREV..$TARGET" | head -40 | sed 's/^/       /'
fi

changed="$(git_live diff --name-only "$PREV" "$TARGET")"
fe_changed="$(grep -c '^superset-frontend/' <<<"$changed" || true)"
py_changed="$(grep -E '^(superset|superset-core)/.*\.py$' <<<"$changed" | grep -vc '^superset/static/' || true)"
migrations="$(grep -E '^superset/migrations/versions/' <<<"$changed" || true)"
dep_changed="$(grep -cE '^(requirements/|pyproject\.toml$|setup\.py$|superset-core/pyproject\.toml$)' <<<"$changed" || true)"
echo "  Changed files: $(grep -c . <<<"$changed" || true) total, $fe_changed frontend, $py_changed python, $dep_changed dependency"

RUN_INIT=0
if (( DO_BACKEND )); then
  if (( FORCE_INIT )) || grep -qE "$INIT_PATHS_RE" <<<"$changed"; then RUN_INIT=1; fi
  [[ -n "$migrations" ]] && { info "new/changed migrations:"; sed 's/^/         /' <<<"$migrations"; }
fi
case "$CELERY" in
  yes) RESTART_CELERY=1 ;;
  no)  RESTART_CELERY=0 ;;
  *)   RESTART_CELERY=$(( DO_BACKEND && (py_changed > 0 || dep_changed > 0) )) ;;
esac
(( ! DO_BACKEND && py_changed > 0 )) && warn "Python code changed but --frontend-only was given: pip/db upgrade/init are skipped"

if (( DO_FRONTEND )); then
  want_node="$(git_live show "$TARGET:superset-frontend/.nvmrc" 2>/dev/null | tr -d ' v\n' || true)"
  want_major="${want_node%%.*}"
  if [[ -z "$NODE_HOME" ]]; then
    for d in /var/etls/tools/node-v"${want_major}".*-linux-x64 "$HOME"/.nvm/versions/node/v"${want_major}".*; do
      [[ -x "$d/bin/node" ]] && NODE_HOME="$d"
    done
  fi
  [[ -n "$NODE_HOME" ]] && export PATH="$NODE_HOME/bin:$PATH"
  have_node="$(node -v 2>/dev/null | tr -d v || echo none)"
  if [[ "${have_node%%.*}" == "$want_major" ]]; then
    ok "node $have_node matches .nvmrc v$want_node ($(command -v node))"
  else
    warn "node $have_node does not match .nvmrc v$want_node"
    info "Install a matching Node without sudo:"
    info "mkdir -p /var/etls/tools && cd /var/etls/tools && curl -fsSLO https://nodejs.org/dist/v$want_node/node-v$want_node-linux-x64.tar.xz && tar xf node-v$want_node-linux-x64.tar.xz"
    (( ALLOW_NODE_MISMATCH )) || refuse "re-run after installing it, or pass --allow-node-mismatch"
  fi

  mem_gb="$(awk '/MemAvailable/ {printf "%d", $2/1024/1024}' /proc/meminfo)"
  if (( mem_gb >= MIN_MEM_GB )); then ok "MemAvailable ${mem_gb} GB"
  else
    warn "MemAvailable ${mem_gb} GB < ${MIN_MEM_GB} GB (webpack uses about 8 GB heap); a build could push Superset/ClickHouse into OOM"
    (( FORCE_MEM )) || refuse "try outside ETL hours, or pass --force-low-memory"
  fi
fi

disk_gb="$(df -BG --output=avail "$(dirname "$BUILD_DIR")" | tail -1 | tr -dc 0-9)"
(( disk_gb >= MIN_DISK_GB )) && ok "free disk ${disk_gb} GB" || refuse "only ${disk_gb} GB free on $(dirname "$BUILD_DIR")"

if (( DO_BACKEND )); then
  [[ -x "$(uv_bin)" ]] || refuse "$(uv_bin) not found (needed for the pip step)"
  req_tmp="$(mktemp)"
  git_live show "$TARGET:$REQ_FILE" >"$req_tmp" 2>/dev/null || refuse "$REQ_FILE not found at $TARGET"
  pip_plan="$("$(uv_bin)" pip install --dry-run --python "$VENV_PY" -r "$req_tmp" 2>&1)" \
    || { rm -f "$req_tmp"; info "$pip_plan"; refuse "pip dry-run failed for $REQ_FILE"; }
  rm -f "$req_tmp"
  pip_changes="$(grep -E '^ [-+] ' <<<"$pip_plan" || true)"
  if [[ -z "$pip_changes" ]]; then ok "Python packages already match $REQ_FILE"
  else
    warn "pip step will change these packages (from $REQ_FILE):"
    head -40 <<<"$pip_changes" | sed 's/^/       /'
  fi
  info "backend steps: pg_dump $DB_NAME, pip install, superset db upgrade$( (( RUN_INIT )) && echo ', superset init (relevant files changed)')"
fi
info "restart: $SERVICE$( (( RESTART_CELERY )) && echo " + celery ($CELERY_UNITS)")"

if pgrep -f 'data_refreshing_scripts/.*\.sh' >/dev/null; then
  warn "an ETL refresh is running now:"
  pgrep -af 'data_refreshing_scripts/.*\.sh' | head -3 | cut -c1-150 | sed 's/^/       /'
  info "Building alongside it competes for CPU/RAM; consider waiting."
fi

if (( DRY_RUN )); then
  step "Dry run: nothing changed"; echo "Log: $LOG"; exit 0
fi
if [[ "$PREV" == "$TARGET" ]]; then
  confirm "No new commits. Redeploy $(git_live log --oneline -1) anyway?" || refuse "nothing to do"
else
  confirm "Deploy $(git_live log --oneline -1 "$TARGET") to production?" || refuse "aborted"
fi

# Ask for the sudo password now, not in the middle of the deploy.
sudo -v || refuse "sudo is needed for systemctl, journalctl, pg_dump and the Superset CLI"

if (( DO_BACKEND )); then
  db_size="$(pg psql -Atc "select pg_size_pretty(pg_database_size('$DB_NAME'))" 2>/dev/null)" \
    || refuse "cannot reach database $DB_NAME on cluster $DB_CLUSTER (set DB_CLUSTER/DB_NAME)"
  ok "metadata DB $DB_NAME on $DB_CLUSTER: $db_size"
  REV_BEFORE="$(db_revision "$LIVE_DIR")"
  [[ -n "$REV_BEFORE" ]] || refuse "could not read the alembic revision with the Superset CLI (check: sudo journalctl, env file)"
  ok "DB revision before: $REV_BEFORE"
fi

REL="$STATE_DIR/releases/$TS"
mkdir -p "$REL/prev_static"
echo "$PREV" >"$REL/prev_commit"; echo "$TARGET" >"$REL/new_commit"
echo "$RESTART_CELERY" >"$REL/celery"; echo 0 >"$REL/db_migrated"; echo 0 >"$REL/pip_changed"
set_status started "$REL"

# --- Check out target + build in a separate worktree -------------------------------
step "Preparing $TARGET in $BUILD_DIR (live site not touched)"
if [[ ! -e "$BUILD_DIR/.git" ]]; then
  git_live worktree add --detach "$BUILD_DIR" "$TARGET"
else
  git -C "$BUILD_DIR" checkout --quiet --detach --force "$TARGET"
fi
ok "build worktree at $(git -C "$BUILD_DIR" log --oneline -1)"

if (( DO_FRONTEND )); then
  FE="$BUILD_DIR/superset-frontend"
  lock_hash="$(sha256sum "$FE/package-lock.json" | cut -c1-16)-node$(node -v)"
  if [[ ! -d "$FE/node_modules" || "$(cat "$FE/node_modules/.moh-stamp" 2>/dev/null)" != "$lock_hash" ]]; then
    echo "  npm ci (lockfile or node changed) ... log: $REL/npm-ci.log"
    ( cd "$FE" && nice -n 10 ionice -c3 npm ci --no-audit --no-fund ) >"$REL/npm-ci.log" 2>&1 \
      || { tail -30 "$REL/npm-ci.log"; set_status failed_build "$REL"; die "npm ci failed (live site untouched)"; }
    echo "$lock_hash" >"$FE/node_modules/.moh-stamp"
    ok "npm ci done"
  else
    ok "node_modules up to date for this lockfile"
  fi

  echo "  npm run build ... log: $REL/build.log (takes several minutes)"
  t0=$(date +%s)
  ( cd "$FE" && nice -n 10 ionice -c3 npm run build ) >"$REL/build.log" 2>&1 \
    || { grep -nE 'ERROR|Error:|FATAL|heap' "$REL/build.log" | tail -20; set_status failed_build "$REL"; die "build failed (live site untouched)"; }
  ok "build finished in $(( $(date +%s) - t0 ))s ($(grep -oE 'compiled.*' "$REL/build.log" | tail -1 | sed 's/\x1b\[[0-9;]*m//g'))"

  OUT="$BUILD_DIR/superset/static"
  [[ -s "$OUT/assets/manifest.json" ]] || { set_status failed_build "$REL"; die "build produced no manifest.json"; }
  missing=0
  while read -r f; do
    [[ -z "$f" ]] && continue
    [[ -s "$OUT/assets/${f##*/static/assets/}" ]] || { warn "manifest entry missing on disk: $f"; missing=1; }
  done < <(manifest_entries "$OUT/assets/manifest.json")
  (( missing == 0 )) || { set_status failed_build "$REL"; die "build output is incomplete (live site untouched)"; }
  (cd "$OUT/assets" && find . -type f -printf '%P\n' | sort) >"$REL/new_assets.txt"
  ok "build output checked: $(wc -l <"$REL/new_assets.txt") files, all manifest entries present"
fi

# --- Back up the current state ----------------------------------------------------
step "Recording release $TS (rollback point)"
cp -p "$LIVE_DIR/superset/static/assets/manifest.json" "$REL/prev_static/" 2>/dev/null || warn "no live manifest.json to back up"
cp -p "$LIVE_DIR/superset/static/service-worker.js" "$REL/prev_static/" 2>/dev/null || true
tar -C "$LIVE_DIR/superset/static" -czf "$REL/assets-before.tar.gz" assets service-worker.js 2>/dev/null \
  && ok "assets backup $(du -h "$REL/assets-before.tar.gz" | cut -f1)" || warn "assets tarball failed (manifest backup still exists)"
if (( DO_BACKEND )); then
  "$(uv_bin)" pip freeze --python "$VENV_PY" >"$REL/pip-freeze-before.txt"
  ok "pip freeze saved ($(wc -l <"$REL/pip-freeze-before.txt") packages)"
  echo "  pg_dump $DB_NAME ..."
  pg pg_dump -Fc "$DB_NAME" >"$REL/$DB_NAME.dump" \
    || { set_status failed_backup "$REL"; die "pg_dump failed (nothing changed yet)"; }
  pg_restore -l "$REL/$DB_NAME.dump" >/dev/null 2>&1 \
    || { set_status failed_backup "$REL"; die "DB dump is not readable by pg_restore (nothing changed yet)"; }
  ok "DB dump $(du -h "$REL/$DB_NAME.dump" | cut -f1): $REL/$DB_NAME.dump"
fi

ROLLBACK_ARMED=1
on_fail() {
  local rc=$?
  (( ${ROLLBACK_ARMED:-0} )) || return 0
  ROLLBACK_ARMED=0
  trap - ERR
  echo; warn "deploy failed (rc=$rc)"
  set_status failed "$REL"
  if [[ "$(release_flag "$REL" db_migrated)" == 1 && -n "${REV_BEFORE:-}" ]] \
     && [[ "$(db_revision "$BUILD_DIR")" == "$REV_BEFORE" ]]; then
    echo 0 >"$REL/db_migrated"; info "DB revision unchanged ($REV_BEFORE): no migration was applied"
  fi
  if [[ "$(release_flag "$REL" db_migrated)" == 1 ]]; then
    print_db_restore_help "$REL"
    die "NOT rolling back automatically because the DB was migrated"
  elif (( AUTO_ROLLBACK )); then
    warn "rolling back automatically"
    do_rollback "$REL" 0
    die "deploy failed; rolled back to $(cat "$REL/prev_commit")"
  else
    die "deploy failed and --no-auto-rollback is set. Undo with: $LIVE_DIR/scripts/moh/deploy.sh --rollback (release status is 'failed'; use git reset --keep $(cat "$REL/prev_commit") + manifest from $REL/prev_static by hand)"
  fi
}
trap 'on_fail' ERR

# --- Backend: packages, migrations, permissions (from the build worktree) ----------
if (( DO_BACKEND )); then
  step "Backend"
  if [[ -n "$pip_changes" ]]; then
    "$(uv_bin)" pip install --python "$VENV_PY" -r "$BUILD_DIR/$REQ_FILE"
    "$(uv_bin)" pip freeze --python "$VENV_PY" >"$REL/pip-freeze-after.txt"
    cmp -s "$REL/pip-freeze-before.txt" "$REL/pip-freeze-after.txt" || echo 1 >"$REL/pip_changed"
    ok "Python packages updated from $REQ_FILE"
  else
    ok "Python packages unchanged"
  fi

  # Mark before running: a partially applied upgrade also needs the DB-aware rollback.
  echo 1 >"$REL/db_migrated"
  superset_cli "$BUILD_DIR" db upgrade >"$REL/db-upgrade.log" 2>&1 \
    || { tail -25 "$REL/db-upgrade.log" | sed 's/^/       /'; false; }
  grep -E 'Running upgrade' "$REL/db-upgrade.log" | tail -15 | sed 's/^/       /' || true
  REV_AFTER="$(db_revision "$BUILD_DIR")"
  [[ -n "$REV_AFTER" ]] || false
  if [[ "$REV_AFTER" == "$REV_BEFORE" ]]; then
    echo 0 >"$REL/db_migrated"; ok "superset db upgrade: no pending migrations ($REV_AFTER)"
  else
    ok "superset db upgrade: $REV_BEFORE -> $REV_AFTER"
  fi

  if (( RUN_INIT )); then
    superset_cli "$BUILD_DIR" init >"$REL/superset-init.log" 2>&1 \
      || { tail -25 "$REL/superset-init.log" | sed 's/^/       /'; false; }
    ok "superset init done"
  else
    ok "superset init skipped (no permission/view/API/migration changes)"
  fi
fi

# --- Update live code and install assets -----------------------------------------
step "Updating live checkout"
if [[ "$PREV" != "$TARGET" ]]; then
  git_live merge --ff-only --quiet "$TARGET"
fi
ok "live code at $(git_live log --oneline -1)"

if (( DO_FRONTEND )); then
  step "Installing assets (additive, manifest last)"
  rsync -a --exclude manifest.json "$OUT/assets/" "$LIVE_DIR/superset/static/assets/"
  mkdir -p "$REL/new_static"
  cp -p "$OUT/assets/manifest.json" "$REL/new_static/"
  # webpack writes service-worker.js one level above assets/
  [[ -f "$OUT/service-worker.js" ]] && cp -p "$OUT/service-worker.js" "$REL/new_static/"
  install_manifest "$REL/new_static"
  ok "assets installed; old files left in place for running workers/clients"
  EXPECT_MANIFEST="$REL/new_static/manifest.json"
else
  EXPECT_MANIFEST="$LIVE_DIR/superset/static/assets/manifest.json"
fi

# --- Restart and verify -----------------------------------------------------------
step "Restarting $SERVICE$( (( RESTART_CELERY )) && echo " + celery units")"
since="$(date '+%Y-%m-%d %H:%M:%S')"
nr_before="$(unit_prop "$SERVICE" NRestarts)"
sudo -v
restart_units "$RESTART_CELERY"
ok "restart issued at $since"

step "Verifying"
verify_service "$since" "$nr_before" "$EXPECT_MANIFEST" "$RESTART_CELERY" || false
echo "  waiting ${STABILITY_WAIT}s, then checking again ..."
sleep "$STABILITY_WAIT"
verify_service "$since" "$nr_before" "$EXPECT_MANIFEST" "$RESTART_CELERY" || false

ROLLBACK_ARMED=0
trap - ERR
set_status deployed "$REL"

# Keep the last KEEP_RELEASES release records (each holds an assets tarball and a DB dump).
ls -1d "$STATE_DIR"/releases/*/ | head -n -"$KEEP_RELEASES" | xargs -r rm -rf --

step "${c_grn}Deploy OK${c_off}: $(git_live log --oneline -1)"
echo "  Release record: $REL"
echo "  Undo:           $LIVE_DIR/scripts/moh/deploy.sh --rollback$( [[ "$(release_flag "$REL" db_migrated)" == 1 ]] && echo ' --restore-db')"
echo "  Browser check:  hard-refresh (Ctrl+Shift+R) a dashboard; the PWA service worker may serve the old shell once."
echo "  Log: $LOG"
