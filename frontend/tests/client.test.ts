import { describe, expect, it } from "vitest";
import { ApiError, api } from "../src/api/client";
import { LIMITS, validate } from "../src/validation";
import { json, mockFetch } from "./helpers";

describe("api client", () => {
  it("turns an error body into an ApiError carrying detail and Retry-After", async () => {
    mockFetch(() => json({ detail: "slow down" }, 429, { "Retry-After": "17" }));
    const err = await api.createComplaint({ text: "x".repeat(20), location: "abc" }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 429, message: "slow down", retryAfterSeconds: 17 });
  });

  it("reports a network failure without leaking a stack trace to the user", async () => {
    mockFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    await expect(api.getStats()).rejects.toThrow("Could not reach the server");
  });
});

describe("validation mirrors the server schema", () => {
  it("reads its limits from openapi.json", () => {
    expect(LIMITS.text).toMatchObject({ minLength: 10, maxLength: 2000 });
    expect(LIMITS.location).toMatchObject({ minLength: 3, maxLength: 200 });
    expect(LIMITS.reporter_contact).toMatchObject({ maxLength: 200 });
  });

  it("treats whitespace-only text as empty, like the server's strip_whitespace", () => {
    expect(validate({ text: " ".repeat(30), location: "F-10", reporter_contact: "" }).text).toBeDefined();
    expect(validate({ text: "Pani nahi aa raha", location: "F-10", reporter_contact: "" })).toEqual({});
  });
});
