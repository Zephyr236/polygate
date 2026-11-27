/**
 * Component tests for caller API key generation and provider scoping.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ApiKeys } from "@/pages/ApiKeys";
import { createServer, providerFixtures } from "../msw";

const server = createServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ApiKeys providers={providerFixtures} />
    </QueryClientProvider>,
  );
}

describe("ApiKeys", () => {
  it("lists generated keys without exposing secrets", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId("api-key-key_alpha")).toBeInTheDocument());
    expect(screen.getByText("Team alpha")).toBeInTheDocument();
    expect(screen.getAllByText("Premium").length).toBeGreaterThan(0);
    expect(screen.getByText("pg_testalpha…")).toBeInTheDocument();
    expect(screen.queryByText(/pg_testalpha_token/)).not.toBeInTheDocument();
  });

  it("generates a key and reveals the secret exactly once", async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText("api-key-name"), "Team beta");
    await userEvent.selectOptions(screen.getByLabelText("api-key-tier"), "economy");
    await userEvent.click(screen.getByRole("button", { name: "Generate key" }));
    await waitFor(() => expect(screen.getByText("pg_newsecret_token")).toBeInTheDocument());
    expect(screen.getByText("Key generated")).toBeInTheDocument();
    expect(
      screen.getByText("Cost first; may cross priority tiers for cheaper providers."),
    ).toBeInTheDocument();
  });

  it("requires a name and at least one provider before generating", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Generate key" }));
    expect(screen.getByText("Enter a name")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("api-key-name"), "Team beta");
    for (const provider of providerFixtures) {
      await userEvent.click(screen.getByLabelText(`provider-${provider.id}`));
    }
    await userEvent.click(screen.getByRole("button", { name: "Generate key" }));
    expect(screen.getByText("Select at least one provider")).toBeInTheDocument();
  });

  it("shows generation failures and revokes keys", async () => {
    server.use(http.post("**/admin/api-keys", () => HttpResponse.json({ detail: "boom" }, { status: 500 })));
    renderPage();
    await userEvent.type(screen.getByLabelText("api-key-name"), "Team beta");
    await userEvent.click(screen.getByRole("button", { name: "Generate key" }));
    await waitFor(() => expect(screen.getByText(/Could not generate the key/)).toBeInTheDocument());
    server.resetHandlers();
    await waitFor(() => expect(screen.getByTestId("api-key-key_alpha")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Revoke"));
    await waitFor(() => expect(screen.queryByText("Revoke")).not.toBeDisabled());
  });

  it("renders the empty key state", async () => {
    server.use(http.get("**/admin/api-keys", () => HttpResponse.json({ keys: [] })));
    renderPage();
    await waitFor(() => expect(screen.getByText("No API keys yet")).toBeInTheDocument());
  });
});
