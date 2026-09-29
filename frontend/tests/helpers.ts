import { vi } from "vitest";
import type { Complaint, ComplaintCreated } from "../src/api/client";

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

/** Replace global fetch with a handler; returns the mock for call assertions. */
export function mockFetch(handler: Handler) {
  const fn = vi.fn((input: RequestInfo | URL, init?: RequestInit) => Promise.resolve(handler(String(input), init)));
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function complaint(overrides: Partial<Complaint> = {}): Complaint {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    text: "Burst water main flooding Street 12 since fajr",
    location: "G-9/2, Islamabad",
    reporter_contact: null,
    category: "water",
    priority: "high",
    status: "open",
    ai_summary: "Burst main flooding Street 12",
    triaged_by: "llm:groq",
    triage_latency_ms: 812,
    created_at: "2026-09-27T06:00:00Z",
    updated_at: "2026-09-27T06:00:00Z",
    allowed_transitions: ["in_progress", "rejected"],
    ...overrides,
  };
}

export function created(overrides: Partial<ComplaintCreated> = {}): ComplaintCreated {
  return {
    ...complaint(),
    triage: { provider: "llm:groq", confidence: 0.91, fallback: false, cache_hit: false, guardrail_applied: false },
    ...overrides,
  };
}
