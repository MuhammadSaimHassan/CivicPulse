#!/usr/bin/env bash
# Network segmentation evidence for the demo video.
# The frontend is on `edge` only; postgres/redis are on `internal` only.
# Every "frontend -> data" attempt below is EXPECTED TO FAIL.
set -uo pipefail

run() { echo "\$ $*"; "$@"; echo "  -> exit code $?"; echo; }

echo "== frontend -> postgres (expected: fail)"
run docker compose exec -T frontend ping -c 1 -W 2 postgres
run docker compose exec -T frontend wget -q -T 2 -O /dev/null http://postgres:5432/

echo "== frontend -> redis (expected: fail)"
run docker compose exec -T frontend wget -q -T 2 -O /dev/null http://redis:6379/

echo "== backend -> postgres (expected: succeed — the backend bridges both networks)"
run docker compose exec -T backend python -c "import socket; socket.create_connection(('postgres', 5432), 2); print('backend reached postgres:5432')"

echo "== networks each service is attached to"
for s in frontend backend postgres redis; do
  printf '%-9s ' "$s"
  docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$(docker compose ps -q $s)"
done
