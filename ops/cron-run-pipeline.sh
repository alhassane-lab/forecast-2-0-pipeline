#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

LOG_LEVEL="${LOG_LEVEL:-INFO}"

TARGET_DATE="${1:-$(python - <<'PY'
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"))
PY)}"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

if [[ -z "${RUN_ID:-}" ]]; then
  RUN_ID="$(python - <<'PY'
import uuid, sys
print(uuid.uuid4())
PY)"
  export RUN_ID
fi

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Lancement pipeline pour la date ${TARGET_DATE} (RUN_ID=${RUN_ID})"

docker compose run --rm pipeline --date "${TARGET_DATE}" --log-level "${LOG_LEVEL}"
