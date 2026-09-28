import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "../src/components/ErrorBoundary";
import { StatsPage } from "../src/pages/StatsPage";
import { json, mockFetch } from "./helpers";

const STATS = {
  total: 5,
  by_category: { water: 3, roads: 2 },
  by_priority: { high: 4, low: 1 },
  by_status: { open: 5 },
  generated_at: "2026-09-27T06:00:00Z",
};
const META = {
  active_provider: "llm:groq",
  fallback_provider: "rules",
  triage_cache: { hits: 1, misses: 3, hit_rate: 0.25 },
  recent: [
    { complaint_id: "a", provider: "rules:fallback", latency_ms: 10012, fallback: true, cache_hit: false, error: "TriageTimeout", at: "2026-09-27T06:00:00Z" },
  ],
};

describe("StatsPage", () => {
  it("renders aggregates and the X-Cache state from the response header", async () => {
    let n = 0;
    mockFetch((url) => {
      if (url === "/api/meta/providers") return json(META);
      n += 1;
      return json(STATS, 200, { "X-Cache": n === 1 ? "MISS" : "HIT" });
    });
    render(<StatsPage />);
    expect(await screen.findByTestId("cache-state")).toHaveTextContent("X-Cache: MISS");
    expect(screen.getByTestId("count-water")).toHaveTextContent("3");
    expect(screen.getByTestId("count-high")).toHaveTextContent("4");
    expect(screen.getByTestId("count-electricity")).toHaveTextContent("0");
    expect(screen.getByText(/25% \(1 hits \/ 3/)).toBeInTheDocument();
    expect(screen.getByText("yes (TriageTimeout)")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(await screen.findByText("X-Cache: HIT")).toBeInTheDocument();
  });
});

describe("ErrorBoundary", () => {
  it("shows a recoverable message instead of a blank page", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    // React re-throws render errors to window in development; keep the test output clean.
    const swallow = (e: ErrorEvent) => e.preventDefault();
    window.addEventListener("error", swallow);
    let broken = true;
    function Flaky() {
      if (broken) throw new Error("boom");
      return <p>recovered</p>;
    }
    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong on this page.");
    broken = false;
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByText("recovered")).toBeInTheDocument();
    window.removeEventListener("error", swallow);
  });
});
