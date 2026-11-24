#!/usr/bin/env bash
# Build the current branch's frontend/template changes on the server and install them on the TRAINING replica only.
# Production is never touched: the build happens in the separate worktree /var/etls/moh-superset-build, which must be at
# production's commit (checked), and nothing is copied to /var/etls/moh-superset.
#   tools/ship-to-training.sh            run from a checkout of the branch; needs ssh to the server (no sudo)
set -euo pipefail
HOST=${MOH_HOST:-sysadmin@196.189.126.21}
REPO=$(git rev-parse --show-toplevel); cd "$REPO"
BASE=${BASE:-origin/master}
git diff "$BASE" HEAD -- superset superset-frontend > /var/tmp/moh-a11y.patch
[[ -s /var/tmp/moh-a11y.patch ]] || { echo "empty patch against $BASE"; exit 2; }
scp -q /var/tmp/moh-a11y.patch "$HOST:/var/tmp/moh-a11y.patch"
# every changed file under superset/ (templates, python) is copied to the replica as well as the built assets
CHANGED=$(git diff --name-only "$BASE" HEAD -- superset | grep -v '^superset/static/' | tr '\n' ' ')
ssh "$HOST" "CHANGED='$CHANGED'" 'set -e
PROD=$(git -C /var/etls/moh-superset rev-parse HEAD)
cd /var/etls/moh-superset-build
[ "$(git rev-parse HEAD)" = "$PROD" ] || { echo "build tree is not at production commit ($PROD)"; exit 3; }
git checkout -q -- superset superset-frontend/src; git clean -fdq superset-frontend/src superset/templates
git apply /var/tmp/moh-a11y.patch
cd superset-frontend && nice -n 10 ionice -c3 npm run build > /var/tmp/a11y-build.log 2>&1 || { tail -20 /var/tmp/a11y-build.log; exit 1; }
B=/var/etls/moh-superset-build/superset; T=/var/etls/moh-sstraining/app/superset
[ -s $B/static/assets/manifest.json ] || { echo no manifest; exit 1; }
rsync -a --exclude manifest.json $B/static/assets/ $T/static/assets/
cp -p $B/static/assets/manifest.json $T/static/assets/manifest.json.new && mv $T/static/assets/manifest.json.new $T/static/assets/manifest.json
cp -p $B/static/service-worker.js $T/static/service-worker.js
R=/var/etls/moh-superset-build; A=/var/etls/moh-sstraining/app
for f in $CHANGED; do mkdir -p "$(dirname $A/$f)"; cp -p "$R/$f" "$A/$f.new" && mv "$A/$f.new" "$A/$f"; done
P=$(systemctl show -p MainPID --value sst-web); kill -HUP $P; sleep 12
systemctl is-active sst-web; curl -s -o /dev/null -m 20 -w "health %{http_code}\n" http://127.0.0.1:18189/health
# leave the build tree clean so production deploys are not affected
cd /var/etls/moh-superset-build && git checkout -q -- superset superset-frontend/src && git clean -fdq superset-frontend/src superset/templates && git status --short | head -3'
