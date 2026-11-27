/**
 * Component tests for the provider pool editor states.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProviderEditor } from "@/pages/Providers";
import { providerFixtures } from "../msw";

describe("ProviderEditor states", () => {
  it("shows an empty state and can add the first provider", async () => {
    render(<ProviderEditor providers={[]} onSave={vi.fn()} saving={false} />);
    expect(screen.getByText("No providers configured")).toBeInTheDocument();
    await userEvent.click(screen.getAllByText("Add provider")[0]!);
    expect(screen.getByLabelText("id-0")).toBeInTheDocument();
  });

  it("filters providers and reports no matches", async () => {
    render(<ProviderEditor providers={providerFixtures} onSave={vi.fn()} saving={false} />);
    const filter = screen.getByLabelText("provider-filter");
    await userEvent.type(filter, "zen");
    expect(screen.getByLabelText("id-1")).toBeInTheDocument();
    expect(screen.queryByLabelText("id-0")).toBeNull();
    await userEvent.clear(filter);
    await userEvent.type(filter, "nothing-matches");
    expect(screen.getByText("No matches")).toBeInTheDocument();
  });

  it("removes a provider", async () => {
    render(<ProviderEditor providers={providerFixtures} onSave={vi.fn()} saving={false} />);
    await userEvent.click(screen.getAllByText("Remove")[0]!);
    expect(screen.getAllByLabelText(/^id-/)).toHaveLength(1);
    expect(screen.getByLabelText("id-0")).toHaveValue("zen");
  });
});
