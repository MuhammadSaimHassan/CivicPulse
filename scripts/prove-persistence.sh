#!/usr/bin/env bash
# Persistence contract: `docker compose down` then `up` preserves every row.
set -euo pipefail
count() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM complaints"'; }

before=$(count)
echo "rows before: $before"
curl -sf -X POST "http://localhost:${FRONTEND_PORT:-8080}/api/complaints" -H 'Content-Type: application/json' \
  -d '{"text":"Persistence check: water pipe leaking near gate 3","location":"Test Street, Islamabad"}' >/dev/null
after_insert=$(count)
echo "rows after insert: $after_insert"
docker compose down          # NOTE: no -v, volumes are kept
docker compose up -d --wait
after_restart=$(count)
echo "rows after down/up: $after_restart"
[ "$after_restart" = "$after_insert" ] && echo "PASS: every row survived" || { echo "FAIL"; exit 1; }
