/**
 * Component tests for dashboard widgets and pages using MSW data.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import type { MetricsResponse } from "@/api/types";
import { CapacityBar, HealthBadge, KpiCard, ReasonList, SuccessRing } from "@/components/widgets";
import { Dashboard } from "@/pages/Dashboard";
import { Playground } from "@/pages/Playground";
import { ProviderEditor, fromDraft, toDraft, validateDraft } from "@/pages/Providers";
import { TokenGate } from "@/pages/Login";
import { Routes } from "@/pages/Routes";
import { createServer, metricsFixture, providerFixtures } from "../msw";

const server = createServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("widgets", () => {
  it("renders KPI, badge, ring and reason list", () => {
    render(
      <div>
        <KpiCard label="Calls" value="42" hint="2 providers" />
        <HealthBadge state="half_open" />
        <SuccessRing rate={0.84} />
        <ReasonList reasons={["disabled"]} />
        <ReasonList reasons={[]} />
      </div>,
    );
    expect(screen.getByText("Calls")).toBeInTheDocument();
    expect(screen.getByText("2 providers")).toBeInTheDocument();
    expect(screen.getByText("half open")).toBeInTheDocument();
    expect(screen.getByText("84%")).toBeInTheDocument();
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.getByText("eligible")).toBeInTheDocument();
  });

  it("fills the capacity bar proportionally", () => {
    const { container } = render(<CapacityBar inflight={3} capacity={10} />);
    expect(screen.getByText("3 / 10")).toBeInTheDocument();
    const fill = container.querySelector<HTMLElement>("[data-testid='capacity-fill']");
    expect(fill?.style.width).toBe("30%");
  });

  it("treats a saturated bar as danger and guards zero capacity", () => {
    const { container } = render(<CapacityBar inflight={5} capacity={4} />);
    const fill = container.querySelector<HTMLElement>("[data-testid='capacity-fill']");
    expect(fill?.style.width).toBe("100%");
    expect(fill?.style.background).toBe("var(--bad)");
  });

  it("guards zero capacity", () => {
    render(<CapacityBar inflight={0} capacity={0} />);
    expect(screen.getByText("0 / 0")).toBeInTheDocument();
  });
});

describe("Dashboard", () => {
  it("renders KPI totals, provider cards and detail rows", () => {
    render(<Dashboard data={metricsFixture} range="1h" onRangeChange={vi.fn()} />);
    expect(screen.getByText("32")).toBeInTheDocument();
    expect(screen.getByTestId("provider-amr")).toBeInTheDocument();
    expect(screen.getByTestId("provider-zen")).toBeInTheDocument();
    expect(screen.getByText("p50 2.10s · p95 2.10s")).toBeInTheDocument();
  });

  it("switches ranges via the buttons", async () => {
    const onRangeChange = vi.fn();
    render(<Dashboard data={metricsFixture} range="1h" onRangeChange={onRangeChange} />);
    await userEvent.click(screen.getByText("24h"));
    expect(onRangeChange).toHaveBeenCalledWith("24h");
  });

  it("renders an empty dashboard without data", () => {
    render(<Dashboard data={undefined} range="15m" onRangeChange={vi.fn()} />);
    expect(screen.getByText("Traffic (calls per bucket)")).toBeInTheDocument();
    expect(screen.queryByTestId("provider-amr")).toBeNull();
  });

  it("handles providers without health entries and zero calls", () => {
    const data: MetricsResponse = {
      ...metricsFixture,
      health: [],
      providers: [{ ...metricsFixture.providers[0]!, calls: 0, prompt_tokens: 0, failures: 0 }],
      series: [],
    };
    render(<Dashboard data={data} range="1h" onRangeChange={vi.fn()} />);
    expect(screen.getByTestId("provider-amr")).toBeInTheDocument();
    expect(screen.queryByText("0 / 10")).toBeNull();
  });
});

describe("Provider editor", () => {
  it("converts drafts round-trip", () => {
    const config = providerFixtures[1]!;
    const draft = toDraft(config);
    expect(draft.session_header).toBe("x-opencode-session");
    expect(fromDraft(draft)).toMatchObject({ id: "zen", session_mode: "uuid-per-request", priority: 2 });
    expect(fromDraft({ ...draft, session_header: "" }).session_header).toBeNull();
    expect(fromDraft({ ...draft, tags: " a , , b " }).tags).toEqual(["a", "b"]);
  });

  it("flags invalid drafts", () => {
    const draft = toDraft(providerFixtures[0]!);
    expect(validateDraft(draft)).toEqual([]);
    expect(validateDraft({ ...draft, id: "Bad ID", base_url: "ftp://x", max_concurrency: "0" })).toEqual([
      "id must be lowercase alphanumeric with dashes",
      "base_url must be an http(s) URL",
      "max_concurrency must be at least 1",
    ]);
    expect(validateDraft({ ...draft, cost_coefficient: "0" })).toContain("cost_coefficient must be positive");
  });

  it("edits fields and saves the pool", async () => {
    const onSave = vi.fn();
    render(<ProviderEditor providers={providerFixtures} onSave={onSave} saving={false} />);
    await userEvent.click(screen.getByLabelText("toggle-provider-0"));
    await userEvent.clear(screen.getByLabelText("id-0"));
    await userEvent.type(screen.getByLabelText("id-0"), "amr-2");
    await userEvent.clear(screen.getByLabelText("cost-0"));
    await userEvent.type(screen.getByLabelText("cost-0"), "0.5");
    await userEvent.click(screen.getByText("Save providers"));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0]![0][0]).toMatchObject({ id: "amr-2", cost_coefficient: 0.5 });
  });

  it("blocks saving invalid input and can add rows", async () => {
    const onSave = vi.fn();
    render(<ProviderEditor providers={providerFixtures} onSave={onSave} saving={false} />);
    await userEvent.click(screen.getByLabelText("toggle-provider-0"));
    await userEvent.clear(screen.getByLabelText("base_url-0"));
    await userEvent.type(screen.getByLabelText("base_url-0"), "ftp://bad");
    await userEvent.click(screen.getByText("Save providers"));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
    await userEvent.click(screen.getByText("Add provider"));
    expect(screen.getByLabelText("id-2")).toBeInTheDocument();
  });

  it("toggles protocol, auth, session and enabled inputs", async () => {
    const onSave = vi.fn();
    render(<ProviderEditor providers={providerFixtures} onSave={onSave} saving={true} />);
    expect(screen.getByText("Saving…")).toBeDisabled();
    await userEvent.click(screen.getByLabelText("toggle-provider-0"));
    await userEvent.click(screen.getByLabelText("toggle-provider-1"));
    await userEvent.selectOptions(screen.getByLabelText("protocol-0"), "anthropic");
    await userEvent.selectOptions(screen.getByLabelText("auth-0"), "both");
    await userEvent.type(screen.getByLabelText("session-0"), "x-header");
    await userEvent.click(screen.getByLabelText("enabled-1"));
    await userEvent.type(screen.getByLabelText("model-1"), "x");
  });
});

describe("TokenGate", () => {
  it("logs in with the admin password", async () => {
    const onSubmit = vi.fn();
    render(<TokenGate initialConfigured={true} onSubmit={onSubmit} />);
    expect(screen.getByText("Sign in")).toBeDisabled();
    await userEvent.type(screen.getByLabelText("admin-password"), "correct horse");
    await userEvent.click(screen.getByText("Sign in"));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("test-session"));
    await userEvent.type(screen.getByLabelText("admin-password"), "{enter}");
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
  });

  it("sets the first-run password after confirmation", async () => {
    const onSubmit = vi.fn();
    render(<TokenGate initialConfigured={false} onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("admin-password"), "correct horse");
    await userEvent.type(screen.getByLabelText("admin-password-confirm"), "correct horse");
    await userEvent.click(screen.getByText("Set password and enter"));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("test-session"));
  });

  it("rejects mismatched and short passwords before calling the API", async () => {
    const onSubmit = vi.fn();
    render(<TokenGate initialConfigured={false} onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("admin-password"), "correct horse");
    await userEvent.type(screen.getByLabelText("admin-password-confirm"), "different");
    await userEvent.click(screen.getByText("Set password and enter"));
    expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("admin-password"));
    await userEvent.clear(screen.getByLabelText("admin-password-confirm"));
    await userEvent.type(screen.getByLabelText("admin-password"), "short");
    await userEvent.type(screen.getByLabelText("admin-password-confirm"), "short");
    await userEvent.click(screen.getByText("Set password and enter"));
    expect(screen.getByText("Use at least 8 characters")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows an invalid-password error from login", async () => {
    server.use(
      http.post("**/admin/auth/login", () =>
        HttpResponse.json({ detail: "invalid admin password" }, { status: 401 }),
      ),
    );
    const onSubmit = vi.fn();
    render(<TokenGate initialConfigured={true} onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("admin-password"), "wrong password");
    await userEvent.click(screen.getByText("Sign in"));
    await waitFor(() => expect(screen.getByText("Invalid admin token. Try again.")).toBeInTheDocument());
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows a retry state when auth status cannot be loaded", async () => {
    server.use(
      http.get("**/admin/auth/status", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    render(<TokenGate onSubmit={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Could not load sign-in status")).toBeInTheDocument());
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});

describe("Playground", () => {
  it("sends a chat and renders the response", async () => {
    const onChat = vi.fn();
    render(<Playground onChat={onChat} result={undefined} pending={false} error={undefined} />);
    await userEvent.click(screen.getByLabelText("playground-stream"));
    await userEvent.click(screen.getByText("Send"));
    expect(onChat).toHaveBeenCalledWith({
      model: "deepseek-v4.1-flash",
      prompt: "Reply with exactly: PONG",
      stream: false,
    });
    expect(screen.getByLabelText("playground-stream")).not.toBeChecked();
  });

  it("shows pending, error and result states", () => {
    render(
      <Playground
        onChat={vi.fn()}
        result={{ content: "PONG", provider: "amr", promptTokens: 5, completionTokens: 2, cachedTokens: 1 }}
        pending={true}
        error="boom"
      />,
    );
    expect(screen.getByText("Running…")).toBeDisabled();
    expect(screen.getByText("boom")).toBeInTheDocument();
    expect(screen.getByTestId("playground-output")).toHaveTextContent("PONG");
  });
});

describe("Routes", () => {
  it("simulates and renders candidates", async () => {
    const onSimulate = vi.fn();
    render(
      <Routes
        onSimulate={onSimulate}
        pending={false}
        data={{
          model: "m",
          prompt_length: 5,
          ranking: [
            { provider_id: "amr", success: 0.98, speed: 1, cost: 1, cache: 0.2, total: 0.94, priority: 1 },
          ],
          decisions: [{ provider_id: "amr", model: "m", eligible: false, reasons: ["disabled"] }],
        }}
      />,
    );
    await userEvent.click(screen.getByText("Simulate"));
    expect(onSimulate).toHaveBeenCalledWith({ model: "deepseek-v4.1-flash", prompt: "hello" });
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.getByText("0.940")).toBeInTheDocument();
  });

  it("shows the pending label and tolerates missing decisions", () => {
    render(
      <Routes
        onSimulate={vi.fn()}
        pending={true}
        data={{
          model: "m",
          prompt_length: 0,
          ranking: [{ provider_id: "amr", success: 1, speed: 1, cost: 1, cache: 0, total: 1, priority: 0 }],
          decisions: [],
        }}
      />,
    );
    expect(screen.getByText("Simulating…")).toBeDisabled();
    expect(screen.getByText("eligible")).toBeInTheDocument();
  });
});
