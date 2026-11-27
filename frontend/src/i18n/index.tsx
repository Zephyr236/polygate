/**
 * Minimal typed i18n provider. Defaults to simplified Chinese in the app;
 * isolated component tests get English when no provider is mounted.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import en from "./en.json";
import zh from "./zh-CN.json";

export type Locale = "zh-CN" | "en";
export type MessageKey = keyof typeof en;
export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string;

interface I18nValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Translate;
}

const DICTIONARIES: Record<Locale, typeof en> = { "zh-CN": zh, en };
const STORAGE_KEY = "polygate.locale";

function translate(locale: Locale, key: MessageKey, vars?: Record<string, string | number>): string {
  const template = DICTIONARIES[locale][key] ?? en[key];
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`));
}

const fallback: I18nValue = {
  locale: "en",
  setLocale: () => undefined,
  t: (key, vars) => translate("en", key, vars),
};

const I18nContext = createContext<I18nValue>(fallback);

/** Read a persisted locale without letting storage failures break startup. */
export function storedLocale(): Locale {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "zh-CN";
  } catch {
    return "zh-CN";
  }
}

/** Provide translations to the application. */
export function I18nProvider({
  initialLocale,
  children,
}: {
  initialLocale?: Locale | undefined;
  children: ReactNode;
}) {
  const [locale, setLocale] = useState<Locale>(() => initialLocale ?? storedLocale());
  useEffect(() => {
    document.documentElement.lang = locale;
    try {
      window.localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      /* storage may be unavailable in private mode */
    }
  }, [locale]);
  const value = useMemo<I18nValue>(
    () => ({ locale, setLocale, t: (key, vars) => translate(locale, key, vars) }),
    [locale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** Access the current locale and translator. */
export function useI18n(): I18nValue {
  return useContext(I18nContext);
}

/** Compact Chinese/English switcher. */
export function LocaleSwitch() {
  const { locale, setLocale, t } = useI18n();
  return (
    <div className="locale-switch" role="group" aria-label={t("nav.language")}>
      <button className={locale === "zh-CN" ? "active" : ""} onClick={() => setLocale("zh-CN")}>
        简体中文
      </button>
      <button className={locale === "en" ? "active" : ""} onClick={() => setLocale("en")}>
        EN
      </button>
    </div>
  );
}
