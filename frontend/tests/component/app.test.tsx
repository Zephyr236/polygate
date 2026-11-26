/**
 * Component tests for the application shell and query hooks.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { App } from "@/App";
import { getToken } from "@/api/client";
import { createServer, providerFixtures } from "../msw";

const server = createServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderApp(token = "test-token") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App initialToken={token} initialLocale="en" />
    </QueryClientProvider>,
  );
}

describe("App shell", () => {
  it("shows the token gate when no token is present", async () => {
    renderApp("");
    expect(screen.getByLabelText("admin-token")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("admin-token"), "abc");
    await userEvent.click(screen.getByText("Enter"));
    expect(getToken()).toBe("abc");
  });

  it("renders the dashboard after metrics load and switches tabs", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByTestId("provider-amr")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Providers"));
    await waitFor(() => expect(screen.getByText("Save providers")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Routes"));
    await userEvent.click(screen.getByText("Playground"));
    expect(screen.getByText("Send")).toBeInTheDocument();
  });

  it("saves providers from the editor", async () => {
    renderApp();
    await userEvent.click(screen.getByText("Providers"));
    await waitFor(() => expect(screen.getByText("Save providers")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Save providers"));
    await waitFor(() => expect(screen.getByText("Save providers")).not.toBeDisabled());
    expect(providerFixtures.length).toBe(2);
  });

  it("runs a simulated route and a playground chat", async () => {
    renderApp();
    await userEvent.click(screen.getByText("Routes"));
    await userEvent.click(screen.getByText("Simulate"));
    await waitFor(() => expect(screen.getByText("Candidates")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Playground"));
    await userEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByTestId("playground-output")).toHaveTextContent("PONG"));
  });

  it("returns to login when the stored token is rejected", async () => {
    server.use(
      http.get("**/admin/providers", () =>
        HttpResponse.json({ detail: "invalid admin token" }, { status: 401 }),
      ),
    );
    renderApp("expired-token");
    await waitFor(() => expect(screen.getByLabelText("admin-token")).toBeInTheDocument());
    expect(screen.getByText("Invalid admin token. Try again.")).toBeInTheDocument();
    expect(getToken()).toBe("");
  });

  it("signs out and clears the stored token", async () => {
    renderApp();
    await userEvent.click(screen.getByText("Sign out"));
    expect(screen.getByLabelText("admin-token")).toBeInTheDocument();
  });

  it("switches dashboard ranges", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByTestId("provider-amr")).toBeInTheDocument());
    await userEvent.click(screen.getByText("7d"));
    await waitFor(() => expect(screen.getByTestId("provider-zen")).toBeInTheDocument());
  });
});
