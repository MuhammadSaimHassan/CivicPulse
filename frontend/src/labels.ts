/**
 * Display labels. These are presentation (how a value is shown), not business
 * rules. `satisfies Record<Status, string>` makes the compiler fail if the
 * backend adds a status we have no label for.
 *
 * Note what is NOT here: which status may follow which. That is the server's
 * state machine; each complaint arrives with `allowed_transitions`.
 */
import type { Category, Priority, Status } from "./api/client";

export const CATEGORY_LABELS = {
  water: "Water",
  electricity: "Electricity",
  sanitation: "Sanitation",
  roads: "Roads",
  streetlights: "Streetlights",
  other: "Other",
} as const satisfies Record<Category, string>;

export const PRIORITY_LABELS = {
  high: "High",
  normal: "Normal",
  low: "Low",
} as const satisfies Record<Priority, string>;

export const STATUS_LABELS = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  rejected: "Rejected",
} as const satisfies Record<Status, string>;

export function keysOf<T extends object>(o: T): (keyof T)[] {
  return Object.keys(o) as (keyof T)[];
}

export function providerLabel(provider: string): string {
  if (provider === "rules:fallback") return "Keyword rules (LLM fallback)";
  if (provider === "rules") return "Keyword rules";
  if (provider === "simulated") return "Simulated (test)";
  if (provider.startsWith("llm:")) return `LLM · ${provider.slice(4)}`;
  return provider;
}
