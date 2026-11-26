/**
 * Component tests for the provider card fields.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProviderCard } from "@/pages/ProviderCard";
import { toDraft } from "@/pages/Providers";
import { providerFixtures } from "../msw";

describe("ProviderCard", () => {
  it("edits every field and removes the card", async () => {
    const onChange = vi.fn();
    const onRemove = vi.fn();
    render(
      <ProviderCard
        draft={toDraft(providerFixtures[0]!)}
        index={0}
        onChange={onChange}
        onRemove={onRemove}
      />,
    );

    for (const label of [
      "id",
      "base_url",
      "model",
      "api_key_env",
      "session",
      "lanes",
      "concurrency",
      "min-tokens",
      "cost",
      "priority",
      "tags",
    ]) {
      const input = screen.getByLabelText(`${label}-0`);
      await userEvent.clear(input);
      await userEvent.type(input, "x");
    }
    await userEvent.selectOptions(screen.getByLabelText("protocol-0"), "anthropic");
    await userEvent.selectOptions(screen.getByLabelText("auth-0"), "both");
    await userEvent.selectOptions(screen.getByLabelText("session_mode-0"), "uuid-per-lane");
    await userEvent.selectOptions(screen.getByLabelText("stream_usage-0"), "message_delta");
    await userEvent.click(screen.getByLabelText("enabled-0"));
    await userEvent.click(screen.getByText("Remove"));

    expect(onChange).toHaveBeenCalled();
    expect(onRemove).toHaveBeenCalledWith(0);
  });

  it("renders fallback labels for empty optional values", () => {
    const draft = { ...toDraft(providerFixtures[0]!), priority: "", cost_coefficient: "", model: "" };
    render(<ProviderCard draft={draft} index={0} onChange={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText("priority —")).toBeInTheDocument();
    expect(screen.getByText("cost ×—")).toBeInTheDocument();
    expect(screen.getByText("no model")).toBeInTheDocument();
  });
});
