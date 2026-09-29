import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SubmitPage } from "../src/pages/SubmitPage";
import { created, json, mockFetch } from "./helpers";

async function fillAndSubmit(text: string, location: string) {
  const user = userEvent.setup();
  if (text) await user.type(screen.getByLabelText("What is wrong?"), text);
  if (location) await user.type(screen.getByLabelText("Where?"), location);
  await user.click(screen.getByRole("button", { name: /submit complaint/i }));
}

describe("SubmitPage", () => {
  it("validates on the client and does not call the server for invalid input", async () => {
    const fetch = mockFetch(() => json({}));
    render(<SubmitPage />);
    await fillAndSubmit("too short", "x");
    // Limits come from the backend's OpenAPI schema (min 10 / min 3).
    expect(screen.getByText("Complaint must be at least 10 characters.")).toBeInTheDocument();
    expect(screen.getByText("Location must be at least 3 characters.")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("shows an honest loading state, then category, priority, summary and provider", async () => {
    let release!: (r: Response) => void;
    const fetch = mockFetch(() => new Promise<Response>((resolve) => (release = resolve)));
    render(<SubmitPage />);
    await fillAndSubmit("Burst water main flooding Street 12", "G-9/2, Islamabad");

    expect(screen.getByRole("status")).toHaveTextContent(/triaging your complaint/i);
    expect(screen.getByRole("button", { name: /submitting/i })).toBeDisabled();

    release(json(created({ triage: { provider: "rules:fallback", confidence: 0.5, fallback: true, cache_hit: false, guardrail_applied: false } }), 201));
    const result = await screen.findByTestId("triage-result");
    expect(result).toHaveTextContent("Water");
    expect(result).toHaveTextContent("High");
    expect(result).toHaveTextContent("Burst main flooding Street 12");
    expect(screen.getByTestId("provider")).toHaveTextContent("Keyword rules (LLM fallback)");
    expect(screen.getByTestId("provider")).toHaveTextContent("fallback");

    const [url, init] = fetch.mock.calls[0]!;
    expect(url).toBe("/api/complaints"); // relative: no baked-in backend URL
    expect(JSON.parse(String(init?.body))).toMatchObject({ text: "Burst water main flooding Street 12", reporter_contact: null });
  });

  it("maps the server's field-level 400 errors onto the form", async () => {
    mockFetch(() =>
      json({ detail: "Validation failed", errors: [{ field: "location", message: "Location looks invalid" }] }, 400),
    );
    render(<SubmitPage />);
    await fillAndSubmit("Water pipe leaking near masjid", "Somewhere");
    expect(await screen.findByText("Location looks invalid")).toBeInTheDocument();
  });

  it("explains a 429 using the server's message", async () => {
    mockFetch(() => json({ detail: "Too many complaints from this address. Try again in 42 s." }, 429, { "Retry-After": "42" }));
    render(<SubmitPage />);
    await fillAndSubmit("Water pipe leaking near masjid", "Satellite Town");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Try again in 42 s."));
  });
});
