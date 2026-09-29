#!/usr/bin/env bash
# Sample the HPA every 5 s into load/results/hpa.csv while a load test runs.
# Usage (two terminals, or background this one):
#   ./scripts/hpa-capture.sh &      # records until you Ctrl-C / kill it
#   k6 run --out csv=load/results/k6.csv load/k6-script.js
#   python scripts/plot_hpa.py      # -> docs/evidence/hpa-scaling.png
set -euo pipefail
NS=${NS:-civicpulse}
mkdir -p load/results
out=load/results/hpa.csv
echo "unix_ts,current_replicas,desired_replicas,cpu_utilization_pct" > "$out"
while true; do
  line=$(kubectl -n "$NS" get hpa backend -o jsonpath='{.status.currentReplicas},{.status.desiredReplicas},{.status.currentMetrics[0].resource.current.averageUtilization}')
  echo "$(date +%s),$line" | tee -a "$out"
  sleep 5
done
