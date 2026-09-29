import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DashboardPage } from "../src/pages/DashboardPage";
import { complaint, json, mockFetch } from "./helpers";

const SERVER_409 = "Invalid status transition 'open' -> 'resolved' (allowed from 'open': in_progress, rejected)";

describe("DashboardPage", () => {
  it("surfaces the server's 409 message verbatim, next to the row", async () => {
    mockFetch((_url, init) => {
      if (init?.method === "PATCH") return json({ detail: SERVER_409 }, 409);
      return json({ items: [complaint()], total: 1, page: 1, page_size: 10 });
    });
    render(<DashboardPage />);
    const select = await screen.findByLabelText(/set status for complaint/i);
    await userEvent.selectOptions(select, "resolved");
    expect(await screen.findByRole("alert")).toHaveTextContent(SERVER_409);
  });

  it("renders only server-provided transitions as buttons and applies a valid one", async () => {
    mockFetch((_url, init) => {
      if (init?.method === "PATCH") {
        return json(complaint({ status: "in_progress", allowed_transitions: ["resolved", "rejected"] }));
      }
      return json({ items: [complaint()], total: 1, page: 1, page_size: 10 });
    });
    render(<DashboardPage />);
    const row = (await screen.findByText("Burst main flooding Street 12")).closest("tr")!;
    await userEvent.click(within(row).getByRole("button", { name: "→ In progress" }));
    expect(await within(row).findByText("In progress", { selector: ".badge" })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "→ Resolved" })).toBeInTheDocument();
  });

  it("sends filters and page as query parameters and shows the total", async () => {
    const fetch = mockFetch(() => json({ items: [complaint()], total: 23, page: 1, page_size: 10 }));
    render(<DashboardPage />);
    expect(await screen.findByTestId("page-info")).toHaveTextContent("Page 1 of 3 · 23 total");

    await userEvent.selectOptions(screen.getByLabelText("Category"), "water");
    await userEvent.selectOptions(screen.getByLabelText("Priority"), "high");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));

    const last = new URL(String(fetch.mock.calls.at(-1)![0]), "http://x");
    expect(last.pathname).toBe("/api/complaints");
    expect(Object.fromEntries(last.searchParams)).toEqual({ category: "water", priority: "high", page: "2", page_size: "10" });
  });
});
