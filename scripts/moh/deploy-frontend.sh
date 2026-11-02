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
# Safe pull + frontend build + restart for the MoH Superset production instance.
#
# Run ON the server, as sysadmin (not root):
#   /var/etls/moh-superset/scripts/moh/deploy-frontend.sh --dry-run    # preflight only
#   /var/etls/moh-superset/scripts/moh/deploy-frontend.sh              # deploy origin/master
#   /var/etls/moh-superset/scripts/moh/deploy-frontend.sh --rollback   # undo the last deploy
#
# Why this exists (problems seen when running `npm run build` in place):
#   * webpack runs with `output.clean = true`, so the build first DELETES
#     superset/static/assets. Gunicorn workers read manifest.json once at boot and
#     ignore a missing file; with --max-requests 1000 workers restart all the time,
#     so any worker that restarts during the build serves blank pages. A failed build
#     leaves the site with no assets.
#   * node_modules was older than package-lock.json, and the system Node (v23) is
#     not the version in .nvmrc (v22).
#   * The build needs about 8 GB of heap on a host whose swap is often full.
#
# What this script does instead:
#   1. Preflight checks: service health, a clean git tree, a fast-forward-only update, no
#      migrations or dependency changes, the Node version, free memory and disk.
#   2. Builds in a SEPARATE git worktree (BUILD_DIR) at the target commit, with its
#      own node_modules (`npm ci` only when the lockfile changes). The live site is not
#      touched while it builds.
#   3. Checks the build output (every file manifest.json points to must exist).
#   4. Saves a release record (previous commit, manifest, service worker, assets tarball).
#   5. Fast-forwards the live checkout to the commit that was built.
#   6. Copies the new assets in WITHOUT deleting old ones, and puts manifest.json in
#      place last with an atomic rename. Running workers keep using the old files,
#      and restarted workers get the new ones.
#   7. Restarts moh-superset.service (and the celery units with --with-celery).
#   8. Checks the service: unit active, no restart loop, /health OK, the login page
#      serves the NEW entry bundles, each bundle returns 200, and no worker boot errors
#      in the journal. Checks again after STABILITY_WAIT seconds.
#   9. If any check after the restart fails, it rolls back automatically (previous
#      commit, manifest, restart) and exits non-zero.
#
# Exit codes: 0 ok, 1 failed (rolled back if it got past the restart), 2 preflight refused.

set -Eeuo pipefail

# --- Re-exec from a temp copy: `git merge` below may rewrite this very file. --------
if [[ -z "${MOH_DEPLOY_REEXEC:-}" ]]; then
  tmp_self="$(mktemp /tmp/moh-deploy-frontend.XXXXXX.sh)"
  cp -- "$0" "$tmp_self"
  chmod 700 "$tmp_self"
  export MOH_DEPLOY_REEXEC="$tmp_self"
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
PUBLIC_URL="${PUBLIC_URL:-}"            # e.g. https://dashboards.example; checked if set
NODE_HOME="${NODE_HOME:-}"              # dir containing bin/node of the .nvmrc version
MIN_MEM_GB="${MIN_MEM_GB:-10}"          # build uses --max_old_space_size=8192
MIN_DISK_GB="${MIN_DISK_GB:-5}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-240}" # TimeoutStartSec=120 + 8 workers to boot
STABILITY_WAIT="${STABILITY_WAIT:-45}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"

# --- Flags ------------------------------------------------------------------------
DRY_RUN=0; ASSUME_YES=0; WITH_CELERY=0; NO_BUILD=0; ALLOW_NODE_MISMATCH=0
ALLOW_BACKEND=0; FORCE_MEM=0; AUTO_ROLLBACK=1; MODE=deploy

usage() {
  sed -n '18,23p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'
Options:
  --dry-run               preflight + show incoming commits, change nothing
  --yes                   don't ask for confirmation
  --branch NAME           branch to deploy (default master)
  --with-celery           also restart the celery worker/beat units
  --no-build              skip the frontend build (Python-only change)
  --allow-backend-changes proceed even if migrations/requirements changed
                          (you must run pip/`superset db upgrade` yourself)
  --allow-node-mismatch   build with a Node that does not match .nvmrc
  --force-low-memory      build even if MemAvailable < MIN_MEM_GB
  --no-auto-rollback      leave the failed state in place for debugging
  --rollback              restore the previous release and restart
  --prune-assets          delete asset files not used by the last 2 releases
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --branch) BRANCH="$2"; shift ;;
    --with-celery) WITH_CELERY=1 ;;
    --no-build) NO_BUILD=1 ;;
    --allow-backend-changes) ALLOW_BACKEND=1 ;;
    --allow-node-mismatch) ALLOW_NODE_MISMATCH=1 ;;
    --force-low-memory) FORCE_MEM=1 ;;
    --no-auto-rollback) AUTO_ROLLBACK=0 ;;
    --rollback) MODE=rollback ;;
    --prune-assets) MODE=prune ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

# --- Logging ----------------------------------------------------------------------
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$STATE_DIR"/{logs,releases}
LOG="$STATE_DIR/logs/deploy-$TS.log"
exec > >(tee -a "$LOG") 2>&1

c_red=$'\e[31m'; c_grn=$'\e[32m'; c_ylw=$'\e[33m'; c_bld=$'\e[1m'; c_off=$'\e[0m'
step() { echo; echo "${c_bld}==> $*${c_off}"; }
ok()   { echo "  ${c_grn}ok${c_off}   $*"; }
warn() { echo "  ${c_ylw}warn${c_off} $*"; }
die()  { echo "  ${c_red}FAIL${c_off} $*"; echo "Log: $LOG"; exit "${2:-1}"; }
refuse() { die "$*" 2; }
confirm() {
  (( ASSUME_YES )) && return 0
  read -r -p "  $* [y/N] " a </dev/tty; [[ "$a" =~ ^[Yy]$ ]]
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

sudo_systemctl() {
  # sysadmin has no passwordless sudo: this prompts on the terminal if needed.
  sudo systemctl "$@"
}

http_code() { curl -s -o /dev/null -m 20 -w '%{http_code}' "$1" || echo 000; }

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

# Check after restart: the app serves the bundle from the manifest now in place.
verify_service() {
  local since="$1" restarts_before="$2" expect_manifest="$3"
  local failed=0

  if wait_healthy; then ok "$SERVICE active and /health = OK"
  else warn "$SERVICE not healthy within ${HEALTH_TIMEOUT}s"; failed=1; fi

  local nr; nr="$(unit_prop "$SERVICE" NRestarts)"
  if [[ "$nr" == "$restarts_before" ]]; then ok "no systemd auto-restarts (NRestarts=$nr)"
  else warn "NRestarts went $restarts_before -> $nr (crash loop?)"; failed=1; fi

  # sysadmin is not in systemd-journal/adm: read through sudo (cached by `sudo -v`).
  local jr; jr="$(sudo -n journalctl -u "$SERVICE" --since "$since" --no-pager -o cat 2>/dev/null || true)"
  [[ -n "$jr" ]] || warn "could not read the journal (sudo timestamp expired?); journal check skipped"
  if grep -qE 'Worker failed to boot|Exception in worker process|ModuleNotFoundError|ImportError|CRITICAL|Shutting down: Master' <<<"$jr"; then
    warn "fatal-looking lines in journal since restart:"
    grep -nE 'Worker failed to boot|Exception in worker process|ModuleNotFoundError|ImportError|CRITICAL|Shutting down: Master' <<<"$jr" | head -20 | sed 's/^/       /'
    failed=1
  else ok "no worker boot errors in journal"; fi
  local tb; tb="$(grep -c 'Traceback' <<<"$jr" || true)"
  (( tb == 0 )) || warn "$tb Traceback(s) in journal since restart (check: journalctl -u $SERVICE --since '$since')"

  local html; html="$(curl -s -m 30 "$LOCAL_URL/login/" || true)"
  local served; served="$(grep -oE '/static/assets/[^"'"'"' ]+\.(js|css)' <<<"$html" | sort -u || true)"
  if [[ -z "$served" ]]; then
    warn "login page references no /static/assets bundles (blank page)"; failed=1
  else
    local f missing=0
    while read -r f; do
      [[ "$(http_code "$LOCAL_URL$f")" == 200 ]] || { warn "asset $f not 200"; missing=1; }
    done <<<"$served"
    (( missing )) && failed=1 || ok "$(wc -l <<<"$served") bundles on /login/ all return 200"
    local want; want="$(manifest_entries "$expect_manifest")"
    local stale=0
    while read -r f; do
      # only hashed webpack entry files come from manifest.json (pwa-manifest.js etc. do not)
      [[ "$f" =~ \.entry\.(js|css)$ ]] || continue
      grep -qxF "$f" <<<"$want" || { warn "login page serves $f which is NOT in the deployed manifest"; stale=1; }
    done <<<"$served"
    (( stale )) && failed=1 || ok "login page serves the deployed bundle"
  fi

  if [[ -n "$PUBLIC_URL" ]]; then
    local pc; pc="$(http_code "$PUBLIC_URL/health")"
    [[ "$pc" == 200 ]] && ok "public $PUBLIC_URL/health = 200" || { warn "public health = $pc"; failed=1; }
  fi

  if (( WITH_CELERY )); then
    local u; for u in $CELERY_UNITS; do
      [[ "$(unit_prop "$u" ActiveState)" == active ]] && ok "$u active" || { warn "$u not active"; failed=1; }
    done
  fi
  return "$failed"
}

install_manifest() { # atomic replace of manifest.json + service-worker.js from $1 (dir with both)
  local src="$1" dst="$LIVE_DIR/superset/static"
  if [[ -f "$src/service-worker.js" ]]; then
    cp -p "$src/service-worker.js" "$dst/.service-worker.js.new"
    mv -f "$dst/.service-worker.js.new" "$dst/service-worker.js"
  fi
  cp -p "$src/manifest.json" "$dst/assets/.manifest.json.new"
  mv -f "$dst/assets/.manifest.json.new" "$dst/assets/manifest.json"
}

restart_units() {
  local units="$SERVICE"
  (( WITH_CELERY )) && units="$units $CELERY_UNITS"
  sudo_systemctl restart $units
}

do_rollback() { # $1 = release dir
  local rel="$1"
  [[ -f "$rel/prev_commit" ]] || die "release $rel has no prev_commit"
  local prev; prev="$(cat "$rel/prev_commit")"
  step "Rolling back to $prev (release $(basename "$rel"))"
  if [[ "$(git_live rev-parse HEAD)" != "$prev" ]]; then
    git_live reset --keep "$prev" || die "git reset --keep failed; fix by hand: git -C $LIVE_DIR reset --keep $prev"
  fi
  ok "code at $(git_live log --oneline -1)"
  install_manifest "$rel/prev_static"
  ok "previous manifest.json / service-worker.js restored"
  local since; since="$(date '+%Y-%m-%d %H:%M:%S')"
  local nr; nr="$(unit_prop "$SERVICE" NRestarts)"
  sudo -v
  restart_units
  if verify_service "$since" "$nr" "$rel/prev_static/manifest.json"; then
    ok "rollback verified"; echo "rolled_back $(date -Is)" >>"$rel/status"
    [[ -f "$rel/status" ]] && head -1 "$rel/status" | grep -q '^deployed' \
      || { echo "failed_and_rolled_back $(date -Is)" >"$rel/status"; }
  else
    die "service still unhealthy after rollback; the old assets tarball is $rel/assets-before.tar.gz"
  fi
}

# Release dirs whose deploy completed (status starts with "deployed"), oldest first.
deployed_releases() {
  local d
  for d in "$STATE_DIR"/releases/*/; do
    [[ -f "$d/status" ]] && head -1 "$d/status" | grep -q '^deployed' && echo "${d%/}"
  done
  return 0
}

# --- Mode: rollback -----------------------------------------------------------------
if [[ "$MODE" == rollback ]]; then
  last="$(deployed_releases | tail -1)"
  [[ -n "$last" ]] || refuse "no completed deploys recorded in $STATE_DIR/releases"
  grep -q '^rolled_back' "$last/status" && refuse "$(basename "$last") was already rolled back; roll back further by hand (git reset --keep + restore manifest from an older release)"
  [[ "$(git_live rev-parse HEAD)" == "$(cat "$last/new_commit")" ]] \
    || refuse "live HEAD is not the commit that release deployed; someone changed it since. Roll back by hand."
  echo "Last release: $(basename "$last")  ($(cat "$last/prev_commit") -> $(cat "$last/new_commit" 2>/dev/null || echo '?'))"
  confirm "Roll back to $(cat "$last/prev_commit")?" || refuse "aborted"
  WITH_CELERY="$(cat "$last/with_celery" 2>/dev/null || echo 0)"
  do_rollback "$last"
  exit 0
fi

# --- Mode: prune assets ---------------------------------------------------------------
if [[ "$MODE" == prune ]]; then
  mapfile -t rels < <(deployed_releases | tail -2)
  (( ${#rels[@]} == 2 )) || refuse "need 2 completed deploys recorded to prune safely"
  for r in "${rels[@]}"; do
    [[ -s "$r/new_assets.txt" ]] || refuse "$(basename "$r") has no asset list (deployed with --no-build?); not pruning"
    grep -q '^rolled_back' "$r/status" && refuse "$(basename "$r") was rolled back; not pruning"
  done
  keep="$(mktemp)"
  cat "${rels[0]}/new_assets.txt" "${rels[1]}/new_assets.txt" | sort -u >"$keep"
  echo "manifest.json" >>"$keep"; echo ".gitkeep" >>"$keep"
  cand="$(cd "$LIVE_DIR/superset/static/assets" && find . -type f -printf '%P\n' | sort | comm -23 - <(sort -u "$keep"))"
  n="$(grep -c . <<<"$cand" || true)"
  echo "Files to delete: $n"; head -20 <<<"$cand"
  (( n > 0 )) || { ok "nothing to prune"; exit 0; }
  (( DRY_RUN )) && exit 0
  confirm "Delete these $n files from $LIVE_DIR/superset/static/assets?" || refuse "aborted"
  (cd "$LIVE_DIR/superset/static/assets" && xargs -d '\n' rm -f -- <<<"$cand")
  ok "pruned $n files"; rm -f "$keep"; exit 0
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
py_changed="$(grep -E '^superset/.*\.py$' <<<"$changed" | grep -vc '^superset/static/' || true)"
risky="$(grep -E '^(superset/migrations/versions/|requirements/|pyproject\.toml$|setup\.py$|superset-frontend/package-lock\.json$)' <<<"$changed" || true)"
echo "  Changed files: $(grep -c . <<<"$changed" || true) total, $fe_changed frontend, $py_changed python"

backend_risky="$(grep -vE 'package-lock\.json$' <<<"$risky" || true)"
if [[ -n "$backend_risky" ]]; then
  warn "migrations or Python dependency changes in this update:"
  sed 's/^/       /' <<<"$backend_risky"
  (( ALLOW_BACKEND )) || refuse "this script does not run pip or 'superset db upgrade'. Back up the DB, do those steps by hand, then re-run with --allow-backend-changes"
fi
if (( py_changed > 0 && ! WITH_CELERY )); then
  warn "Python code changed: celery workers keep running old code unless you pass --with-celery"
fi

if (( ! NO_BUILD )); then
  # Node version: the repo pins it in .nvmrc / package.json engines.
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
    echo "       Install a matching Node without sudo:"
    echo "       mkdir -p /var/etls/tools && cd /var/etls/tools && curl -fsSLO https://nodejs.org/dist/v$want_node/node-v$want_node-linux-x64.tar.xz && tar xf node-v$want_node-linux-x64.tar.xz"
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

if pgrep -f 'data_refreshing_scripts/.*\.sh' >/dev/null; then
  warn "an ETL refresh is running now:"; pgrep -af 'data_refreshing_scripts/.*\.sh' | head -3 | cut -c1-150 | sed 's/^/       /'
  echo "       Building alongside it competes for CPU/RAM; consider waiting."
fi

if (( DRY_RUN )); then
  step "Dry run: nothing changed"; echo "Log: $LOG"; exit 0
fi
if [[ "$PREV" == "$TARGET" ]] && ! confirm "No new commits. Rebuild and redeploy $TARGET anyway?"; then
  refuse "nothing to do"
fi
[[ "$PREV" == "$TARGET" ]] || confirm "Deploy $(git_live log --oneline -1 "$TARGET") to production?" || refuse "aborted"

# Ask for the sudo password now, not in the middle of the deploy.
sudo -v || refuse "sudo is needed for systemctl restart"

REL="$STATE_DIR/releases/$TS"
mkdir -p "$REL/prev_static"
echo "$PREV" >"$REL/prev_commit"; echo "$TARGET" >"$REL/new_commit"; echo "$WITH_CELERY" >"$REL/with_celery"

# --- Build in a separate worktree --------------------------------------------------
if (( ! NO_BUILD )); then
  step "Building $TARGET in $BUILD_DIR (live site not touched)"
  if [[ ! -e "$BUILD_DIR/.git" ]]; then
    git_live worktree add --detach "$BUILD_DIR" "$TARGET"
  else
    git -C "$BUILD_DIR" checkout --quiet --detach --force "$TARGET"
  fi
  ok "build worktree at $(git -C "$BUILD_DIR" log --oneline -1)"

  FE="$BUILD_DIR/superset-frontend"
  lock_hash="$(sha256sum "$FE/package-lock.json" | cut -c1-16)-node$(node -v)"
  if [[ ! -d "$FE/node_modules" || "$(cat "$FE/node_modules/.moh-stamp" 2>/dev/null)" != "$lock_hash" ]]; then
    echo "  npm ci (lockfile or node changed) ... log: $REL/npm-ci.log"
    ( cd "$FE" && nice -n 10 ionice -c3 npm ci --no-audit --no-fund ) >"$REL/npm-ci.log" 2>&1 \
      || { tail -30 "$REL/npm-ci.log"; die "npm ci failed (live site untouched)"; }
    echo "$lock_hash" >"$FE/node_modules/.moh-stamp"
    ok "npm ci done"
  else
    ok "node_modules up to date for this lockfile"
  fi

  echo "  npm run build ... log: $REL/build.log (takes several minutes)"
  t0=$(date +%s)
  ( cd "$FE" && nice -n 10 ionice -c3 npm run build ) >"$REL/build.log" 2>&1 \
    || { grep -nE 'ERROR|Error:|FATAL|heap' "$REL/build.log" | tail -20; die "build failed (live site untouched)"; }
  ok "build finished in $(( $(date +%s) - t0 ))s ($(grep -oE 'compiled.*' "$REL/build.log" | tail -1 | sed 's/\x1b\[[0-9;]*m//g'))"

  OUT="$BUILD_DIR/superset/static"
  [[ -s "$OUT/assets/manifest.json" ]] || die "build produced no manifest.json"
  missing=0
  while read -r f; do
    [[ -z "$f" ]] && continue
    [[ -s "$OUT/assets/${f##*/static/assets/}" ]] || { warn "manifest entry missing on disk: $f"; missing=1; }
  done < <(manifest_entries "$OUT/assets/manifest.json")
  (( missing == 0 )) || die "build output is incomplete (live site untouched)"
  (cd "$OUT/assets" && find . -type f -printf '%P\n' | sort) >"$REL/new_assets.txt"
  ok "build output checked: $(wc -l <"$REL/new_assets.txt") files, all manifest entries present"
fi

# --- Back up the current state ----------------------------------------------------
step "Recording release $TS (rollback point)"
cp -p "$LIVE_DIR/superset/static/assets/manifest.json" "$REL/prev_static/" 2>/dev/null || warn "no live manifest.json to back up"
cp -p "$LIVE_DIR/superset/static/service-worker.js" "$REL/prev_static/" 2>/dev/null || true
tar -C "$LIVE_DIR/superset/static" -czf "$REL/assets-before.tar.gz" assets service-worker.js 2>/dev/null \
  && ok "assets backup $(du -h "$REL/assets-before.tar.gz" | cut -f1)" || warn "assets tarball failed (manifest backup still exists)"

ROLLBACK_ARMED=1
on_fail() {
  local rc=$?
  if (( ${ROLLBACK_ARMED:-0} && AUTO_ROLLBACK )); then
    echo; warn "deploy failed (rc=$rc); rolling back automatically"
    ROLLBACK_ARMED=0
    do_rollback "$REL" || true
  elif (( ${ROLLBACK_ARMED:-0} )); then
    warn "deploy failed and --no-auto-rollback is set. To undo: $0 --rollback"
  fi
}
trap 'on_fail' ERR

# --- Update live code and install assets -----------------------------------------
step "Updating live checkout"
if [[ "$PREV" != "$TARGET" ]]; then
  git_live merge --ff-only --quiet "$TARGET"
fi
ok "live code at $(git_live log --oneline -1)"

if (( ! NO_BUILD )); then
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
step "Restarting $SERVICE$( (( WITH_CELERY )) && echo " + celery units")"
since="$(date '+%Y-%m-%d %H:%M:%S')"
nr_before="$(unit_prop "$SERVICE" NRestarts)"
sudo -v
restart_units
ok "restart issued at $since"

step "Verifying"
if ! verify_service "$since" "$nr_before" "$EXPECT_MANIFEST"; then
  false   # triggers ERR -> auto rollback
fi
echo "  waiting ${STABILITY_WAIT}s, then checking again ..."
sleep "$STABILITY_WAIT"
if ! verify_service "$since" "$nr_before" "$EXPECT_MANIFEST"; then
  false
fi

ROLLBACK_ARMED=0
trap - ERR
echo "deployed $(date -Is)" >"$REL/status"

# Keep the last KEEP_RELEASES release records.
ls -1d "$STATE_DIR"/releases/*/ | head -n -"$KEEP_RELEASES" | xargs -r rm -rf --

step "${c_grn}Deploy OK${c_off}: $(git_live log --oneline -1)"
echo "  Release record: $REL"
echo "  Undo:           $LIVE_DIR/scripts/moh/deploy-frontend.sh --rollback"
echo "  Browser check:  hard-refresh (Ctrl+Shift+R) a dashboard; the PWA service worker may serve the old shell once."
echo "  Log: $LOG"
