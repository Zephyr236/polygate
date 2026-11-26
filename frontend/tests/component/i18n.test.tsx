/**
 * i18n provider and locale switch tests.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { I18nProvider, LocaleSwitch, storedLocale, useI18n } from "@/i18n";

function Probe() {
  const { locale, t } = useI18n();
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="label">{t("nav.providers")}</span>
      <span data-testid="count">{t("providers.count", { count: 3 })}</span>
      <LocaleSwitch />
    </div>
  );
}

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("i18n", () => {
  it("defaults to simplified Chinese and persists a switch", async () => {
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("locale")).toHaveTextContent("zh-CN");
    expect(screen.getByTestId("label")).toHaveTextContent("渠道");
    expect(screen.getByTestId("count")).toHaveTextContent("3 个渠道");
    await userEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByTestId("locale")).toHaveTextContent("en");
    expect(screen.getByTestId("label")).toHaveTextContent("Providers");
    expect(window.localStorage.getItem("polygate.locale")).toBe("en");
  });

  it("uses a stored English locale", () => {
    window.localStorage.setItem("polygate.locale", "en");
    expect(storedLocale()).toBe("en");
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("locale")).toHaveTextContent("en");
  });

  it("survives unavailable storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(storedLocale()).toBe("zh-CN");
  });
});
