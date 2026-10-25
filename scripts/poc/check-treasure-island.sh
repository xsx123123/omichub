#!/usr/bin/env bash
set -euo pipefail
cygnus_repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$cygnus_repo_root"
(
  cd pipelines/Treasure-Seeking_Mouse
  ./node_modules/.bin/tsc --noEmit
)
node frontend/scripts/build-treasure-island.mjs
(
  cd frontend
  ./node_modules/.bin/vue-tsc --noEmit -p poc/treasure-island/tsconfig.json
  ./node_modules/.bin/vitest run --config poc/treasure-island/vitest.config.ts
  ./node_modules/.bin/vite build --config poc/treasure-island/vite.config.ts
)
if [[ -n "${TREASURE_POC_PLAYWRIGHT_PATH:-}" ]]; then
  PLAYWRIGHT_MODULE="$TREASURE_POC_PLAYWRIGHT_PATH" \
    CHROMIUM_PATH="${TREASURE_POC_CHROMIUM:-}" node scripts/poc/treasure-ui-browser.mjs
else
  echo 'Browser evidence not run: set TREASURE_POC_PLAYWRIGHT_PATH and TREASURE_POC_CHROMIUM.'
fi
