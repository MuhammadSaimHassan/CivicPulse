"""Plot replicas against offered load from a k6 run and an HPA capture.

    python scripts/plot_hpa.py [load/results/k6.csv] [load/results/hpa.csv] [docs/evidence/hpa-scaling.png]

Needs matplotlib (pip install matplotlib). Also prints the measured lag between
load rising and replicas rising — the number ENGINEERING-NOTES Q5 asks for.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

k6_path = Path(sys.argv[1] if len(sys.argv) > 1 else "load/results/k6.csv")
hpa_path = Path(sys.argv[2] if len(sys.argv) > 2 else "load/results/hpa.csv")
out_path = Path(sys.argv[3] if len(sys.argv) > 3 else "docs/evidence/hpa-scaling.png")

# k6 CSV: one row per metric sample. Offered load = requests started per second.
reqs: dict[int, int] = defaultdict(int)
vus: dict[int, float] = {}
with k6_path.open() as f:
    for row in csv.DictReader(f):
        ts = int(float(row["timestamp"]))
        if row["metric_name"] == "http_reqs":
            reqs[ts] += 1
        elif row["metric_name"] == "vus":
            vus[ts] = float(row["metric_value"])

hpa = []
with hpa_path.open() as f:
    for row in csv.DictReader(f):
        cpu = row["cpu_utilization_pct"]
        hpa.append((int(row["unix_ts"]), int(row["current_replicas"] or 0), float(cpu) if cpu else None))

t0 = min(min(reqs), hpa[0][0])
rps_t = sorted(reqs)
fig, ax1 = plt.subplots(figsize=(10, 5))
ax1.plot([t - t0 for t in rps_t], [reqs[t] for t in rps_t], color="#0f766e", alpha=0.6, label="offered load (req/s)")
ax1.set_xlabel("seconds since start")
ax1.set_ylabel("requests per second", color="#0f766e")
ax2 = ax1.twinx()
ax2.step([t - t0 for t, _, _ in hpa], [r for _, r, _ in hpa], where="post", color="#b42318", linewidth=2, label="backend replicas")
ax2.set_ylabel("replicas", color="#b42318")
ax2.set_ylim(0, max(r for _, r, _ in hpa) + 1)
fig.suptitle("CivicPulse backend: HPA replicas vs offered load")
fig.legend(loc="upper left", bbox_to_anchor=(0.08, 0.9))
fig.tight_layout()
out_path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_path, dpi=150)
print(f"wrote {out_path}")

# Lag: first second offered load exceeds half its peak -> first replica increase.
peak = max(reqs.values())
load_up = next(t for t in rps_t if reqs[t] >= peak / 2)
base_replicas = hpa[0][1]
scaled = next((t for t, r, _ in hpa if t >= load_up and r > base_replicas), None)
if scaled:
    print(f"load reached 50% of peak at t={load_up - t0}s; replicas first rose at t={scaled - t0}s; lag = {scaled - load_up}s")
else:
    print("replicas never rose above the starting count during the capture")
