/**
 * Typed API client.
 *
 * Every request and response type comes from ./schema.d.ts, which is
 * GENERATED from the backend's OpenAPI schema (`npm run gen:api`). CI
 * regenerates it and fails if the committed file is stale, so a backend
 * contract change that the frontend has not caught up with breaks the build
 * instead of breaking production.
 *
 * All URLs are relative (/api/...). nginx (Compose) or the Ingress (Kubernetes)
 * routes them to the backend, so this bundle contains no backend address and
 * the same image runs in every environment. See docs/adr/0002.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];
export type Complaint = Schemas["ComplaintOut"];
export type ComplaintCreated = Schemas["ComplaintCreated"];
export type ComplaintCreate = Schemas["ComplaintCreate"];
export type ComplaintPage = Schemas["ComplaintPage"];
export type Stats = Schemas["Stats"];
export type ProvidersMeta = Schemas["ProvidersMeta"];
export type Category = Schemas["Category"];
export type Priority = Schemas["Priority"];
export type Status = Schemas["Status"];
export type FieldError = Schemas["FieldError"];

export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: FieldError[];
  readonly retryAfterSeconds: number | null;

  constructor(status: number, detail: string, fieldErrors: FieldError[] = [], retryAfter: number | null = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.retryAfterSeconds = retryAfter;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<{ data: T; headers: Headers }> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    let fieldErrors: FieldError[] = [];
    try {
      const body = (await res.json()) as Partial<Schemas["ErrorBody"]>;
      if (typeof body.detail === "string") detail = body.detail;
      if (Array.isArray(body.errors)) fieldErrors = body.errors;
    } catch {
      /* non-JSON error body: keep the generic message */
    }
    const retry = res.headers.get("Retry-After");
    throw new ApiError(res.status, detail, fieldErrors, retry ? Number(retry) : null);
  }
  return { data: (await res.json()) as T, headers: res.headers };
}

export interface ListParams {
  category?: Category | "";
  priority?: Priority | "";
  status?: Status | "";
  page: number;
  page_size: number;
}

export const api = {
  async createComplaint(body: ComplaintCreate): Promise<ComplaintCreated> {
    return (await request<ComplaintCreated>("/api/complaints", { method: "POST", body: JSON.stringify(body) })).data;
  },

  async listComplaints(params: ListParams): Promise<ComplaintPage> {
    const q = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== "" && value !== undefined) q.set(key, String(value));
    }
    return (await request<ComplaintPage>(`/api/complaints?${q.toString()}`)).data;
  },

  async changeStatus(id: string, status: Status): Promise<Complaint> {
    return (
      await request<Complaint>(`/api/complaints/${encodeURIComponent(id)}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      })
    ).data;
  },

  async getStats(): Promise<{ stats: Stats; cache: "HIT" | "MISS" | "UNKNOWN" }> {
    const { data, headers } = await request<Stats>("/api/stats");
    const cache = headers.get("X-Cache");
    return { stats: data, cache: cache === "HIT" || cache === "MISS" ? cache : "UNKNOWN" };
  },

  async getProviders(): Promise<ProvidersMeta> {
    return (await request<ProvidersMeta>("/api/meta/providers")).data;
  },
};
