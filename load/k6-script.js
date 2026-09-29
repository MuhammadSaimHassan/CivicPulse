// Load test for the HPA demo and the zero-downtime rollout demo.
//
//   k6 run -e BASE_URL=http://civicpulse.localhost:8081 load/k6-script.js
//   k6 run -e BASE_URL=... -e PROFILE=steady load/k6-script.js    # constant load (rollout demo)
//   k6 run --out csv=load/results/k6.csv ...                       # for scripts/plot_hpa.py
//
// Mostly reads: POST /api/complaints is rate-limited to 10/min per client IP
// (by design), so a single load generator cannot push writes. The list query
// with page_size=100 is the CPU-heavy path (100 rows serialised per request).
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://civicpulse.localhost:8081";
const PROFILE = __ENV.PROFILE || "ramp";

const profiles = {
  ramp: {
    stages: [
      { duration: "30s", target: 5 }, // baseline
      { duration: "1m", target: 60 }, // load arrives
      { duration: "3m", target: 60 }, // sustained: watch replicas rise
      { duration: "1m", target: 0 }, // load leaves (scale-down waits 300 s)
    ],
  },
  steady: { stages: [{ duration: "10s", target: 20 }, { duration: "3m", target: 20 }] },
};

export const options = {
  ...profiles[PROFILE],
  thresholds: {
    // For the rollout demo: ANY failed request fails the run.
    http_req_failed: PROFILE === "steady" ? ["rate==0"] : ["rate<0.01"],
    http_req_duration: ["p(95)<2000"],
  },
};

const categories = ["water", "electricity", "sanitation", "roads", "streetlights", "other"];

export default function () {
  const cat = categories[Math.floor(Math.random() * categories.length)];
  const list = http.get(`${BASE}/api/complaints?page_size=100&category=${cat}`, { tags: { name: "list" } });
  check(list, { "list 200": (r) => r.status === 200 });

  const stats = http.get(`${BASE}/api/stats`, { tags: { name: "stats" } });
  check(stats, { "stats 200": (r) => r.status === 200 });

  const items = list.status === 200 ? list.json("items") : [];
  if (items && items.length) {
    const one = http.get(`${BASE}/api/complaints/${items[0].id}`, { tags: { name: "get" } });
    check(one, { "get 200": (r) => r.status === 200 });
  }
  sleep(0.2);
}
