#!/usr/bin/env bash
set -euo pipefail

DEST="../s2778911/src/"

rsync -avhr --files-from=- ./ "$DEST" <<'FILES'
docs/
tools/
workflow/
run.sh
config.yml
FILES
