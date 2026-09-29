# Evidence

Screenshots and captures the rubric asks for. All of these come from **your** runs.

| file | rubric item |
|---|---|
| `branch-protection.png` | A — main protected: PR required, checks required, ≥ 1 approval |
| `conflict-markers.png`, `conflict-resolved.png`, `conflict-merge.png` | A — deliberate merge conflict |
| `blocked-merge.png`, `green-merge.png` | I — red pipeline blocks a merge, then green |
| `screenshot-submit.png`, `screenshot-dashboard.png`, `screenshot-stats.png` | J — README screenshots |
| `isolation.txt` | G — output of `make isolation` (the failing commands) |
| `persistence.txt` | D — output of `make persistence`; plus `kubectl delete pod postgres-0` then row count |
| `hpa-watch.txt` | H — `kubectl -n civicpulse get hpa backend -w` during the load test |
| `hpa-scaling.png` | H — `python scripts/plot_hpa.py` (replicas vs offered load) |
| `vpa-recommendation.txt` | H — `kubectl -n civicpulse describe vpa backend-vpa` |
| `rollout-zero-downtime.txt` | Bonus — output of `scripts/rollout-under-load.sh` |
| `grafana.png` | Bonus — Grafana dashboard with live data |
