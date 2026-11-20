#!/usr/bin/env bash
# Fast responsive + accessibility gate against a RUNNING instance (read-only).
#
#   run-gate.sh [--target prod|training] [--url URL] [--out DIR]
#
# Exit codes:  0 PASS | 1 REGRESSION (a page is over its budget)
#              2 usage/setup error | 3 NOT VERIFIED (could not measure)
# Credentials: MOH_UI_USER/MOH_UI_PASS, or MOH_UI_CREDS_FILE, or ~/.config/moh-ui-test/<target>.env
# (never printed). Takes about 8 minutes at 4 workers (63 checks on production).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET=prod; URL=""; OUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift ;;
    --url) URL="$2"; shift ;;
    --out) OUT="$2"; shift ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
[[ -n "$URL" ]] || { echo "run-gate.sh: --url is required" >&2; exit 2; }
OUT="${OUT:-$HERE/results/gate-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"
cd "$HERE" || exit 2

command -v node >/dev/null 2>&1 || { echo "NOT VERIFIED: node not found" | tee "$OUT/summary.txt"; exit 3; }

# dependencies, keyed by the lockfile so a changed lock reinstalls
lock="$(sha256sum package-lock.json | cut -c1-16)"
if [[ ! -d node_modules/@playwright || "$(cat node_modules/.gate-stamp 2>/dev/null)" != "$lock" ]]; then
  echo "  installing UI test dependencies (npm ci) ..."
  npm ci --no-audit --no-fund >"$OUT/npm-ci.log" 2>&1 \
    || { echo "NOT VERIFIED: npm ci failed (see $OUT/npm-ci.log)" | tee "$OUT/summary.txt"; exit 3; }
  echo "$lock" >node_modules/.gate-stamp
fi

# browser: system Chrome if present, else a Playwright Chromium kept next to the tests
if [[ -z "${MOH_UI_CHANNEL:-}" ]]; then
  if command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1; then
    export MOH_UI_CHANNEL=chrome
  else
    export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HERE/.pw-browsers}"
    npx playwright install chromium >"$OUT/browser-install.log" 2>&1 \
      || { echo "NOT VERIFIED: no Chrome and 'playwright install chromium' failed (see $OUT/browser-install.log)" | tee "$OUT/summary.txt"; exit 3; }
  fi
fi

export MOH_UI_TARGET="$TARGET" MOH_UI_BASE_URL="$URL" MOH_UI_PROFILE=gate
export MOH_UI_WORKERS="${MOH_UI_WORKERS:-4}" MOH_UI_RUN_ID="${MOH_UI_RUN_ID:-gate-$(date +%s)}"
export PLAYWRIGHT_JSON_OUTPUT_NAME="$OUT/report.json"

echo "  running the UI gate against $URL (target $TARGET, profile gate, $MOH_UI_WORKERS workers) ..."
npx playwright test tests/ui-quality.spec.ts ${MOH_UI_GREP:+--grep "$MOH_UI_GREP"} --reporter=line,json --output="$OUT/test-results" >"$OUT/playwright.log" 2>&1
node tools/gate-summary.mjs "$OUT/report.json" "$OUT/summary.txt"
exit $?
