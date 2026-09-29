#!/usr/bin/env bash
# Zero-downtime rollout demo (bonus): constant load while the backend image
# changes; k6 fails the run if even one request fails.
#   ./scripts/rollout-under-load.sh civicpulse-backend:dev2
set -euo pipefail
NEW_IMAGE=${1:?usage: $0 <new backend image, e.g. civicpulse-backend:dev2>}
NS=${NS:-civicpulse}
BASE_URL=${BASE_URL:-http://civicpulse.localhost:8081}

k6 run -e BASE_URL="$BASE_URL" -e PROFILE=steady load/k6-script.js &
K6=$!
sleep 20
kubectl -n "$NS" set image deployment/backend backend="$NEW_IMAGE"
kubectl -n "$NS" rollout status deployment/backend --timeout=300s
wait $K6 && echo "PASS: rollout completed with zero failed requests"
