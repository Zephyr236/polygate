/**
 * Application shell wiring navigation, queries and the token gate.
 */

import { useEffect, useState } from "react";

import { ApiError, clearToken, setToken } from "./api/client";
import { Icon } from "./components/icons";
import { I18nProvider, LocaleSwitch, useI18n, type Locale } from "./i18n";
import { Dashboard } from "./pages/Dashboard";
import { TokenGate } from "./pages/Login";
import { Playground } from "./pages/Playground";
import { Routes } from "./pages/Routes";
import { ProviderEditor } from "./pages/Providers";
import { useChat, useMetrics, useProviders, useSaveProviders, useSimulate } from "./state/queries";

type Tab = "Dashboard" | "Providers" | "Routes" | "Playground";

const NAV = [
  { name: "Dashboard", key: "nav.dashboard", icon: "dashboard" },
  { name: "Providers", key: "nav.providers", icon: "server" },
  { name: "Routes", key: "nav.routes", icon: "route" },
  { name: "Playground", key: "nav.playground", icon: "play" },
] as const satisfies readonly {
  name: Tab;
  key: "nav.dashboard" | "nav.providers" | "nav.routes" | "nav.playground";
  icon: "dashboard" | "server" | "route" | "play";
}[];

/** Root component providing locale context. */
export function App({ initialToken, initialLocale }: { initialToken: string; initialLocale?: Locale }) {
  return (
    <I18nProvider initialLocale={initialLocale}>
      <AppContent initialToken={initialToken} />
    </I18nProvider>
  );
}

function AppContent({ initialToken }: { initialToken: string }) {
  const { t } = useI18n();
  const [token, setTokenState] = useState(initialToken);
  const [tab, setTab] = useState<Tab>("Dashboard");
  const [range, setRange] = useState("1h");
  const providers = useProviders();
  const metrics = useMetrics(range);
  const save = useSaveProviders();
  const simulation = useSimulate();
  const chat = useChat();

  const unauthorized = providers.error instanceof ApiError && providers.error.status === 401;
  useEffect(() => {
    if (unauthorized) clearToken();
  }, [unauthorized]);

  if (!token || unauthorized) {
    return (
      <TokenGate
        invalid={unauthorized}
        onSubmit={(value) => {
          setToken(value);
          setTokenState(value);
          void providers.refetch();
        }}
      />
    );
  }

  const providerCount = providers.data?.providers.length ?? 0;
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">PG</div>
          <div>
            <h1>polygate</h1>
            <p>{t("app.tagline")}</p>
          </div>
        </div>
        <nav className="nav" aria-label={t("app.workspace")}>
          {NAV.map((item) => (
            <button
              key={item.name}
              className={item.name === tab ? "active" : ""}
              onClick={() => setTab(item.name)}
            >
              <Icon name={item.icon} size={16} />
              <span>{t(item.key)}</span>
            </button>
          ))}
        </nav>
        <div className="topbar-actions">
          <span className="pill mono">{t("providers.count", { count: providerCount })}</span>
          <LocaleSwitch />
          <button
            className="ghost"
            onClick={() => {
              clearToken();
              setTokenState("");
            }}
          >
            <Icon name="logout" size={16} />
            {t("app.signOut")}
          </button>
        </div>
      </header>
      <section className="workspace">
        <header className="workspace-head">
          <div>
            <div className="eyebrow">{t("app.workspace")}</div>
            <h2>{t(NAV.find((item) => item.name === tab)?.key ?? "nav.dashboard")}</h2>
          </div>
          <div className="workspace-meta">
            <span className="pill">
              <span className="status-dot" />
              {t("app.live")}
            </span>
            <span className="pill mono">v0.1.0</span>
          </div>
        </header>
        <TabBody
          tab={tab}
          range={range}
          onRangeChange={setRange}
          metrics={metrics}
          providers={providers}
          save={save}
          simulation={simulation}
          chat={chat}
        />
      </section>
    </div>
  );
}

/** Props of the active-tab content. */
type TabBodyProps = {
  tab: Tab;
  range: string;
  onRangeChange: (range: string) => void;
  metrics: ReturnType<typeof useMetrics>;
  providers: ReturnType<typeof useProviders>;
  save: ReturnType<typeof useSaveProviders>;
  simulation: ReturnType<typeof useSimulate>;
  chat: ReturnType<typeof useChat>;
};

function TabBody({ tab, range, onRangeChange, metrics, providers, save, simulation, chat }: TabBodyProps) {
  if (tab === "Providers") return <ProvidersTab providers={providers} save={save} />;
  if (tab === "Routes") return <RoutesTab simulation={simulation} />;
  if (tab === "Playground") return <PlaygroundTab chat={chat} />;
  return <DashboardTab metrics={metrics} range={range} onRangeChange={onRangeChange} />;
}

function ProvidersTab({ providers, save }: Pick<TabBodyProps, "providers" | "save">) {
  return <ProvidersState providers={providers} save={save} />;
}

function ProvidersState({ providers, save }: Pick<TabBodyProps, "providers" | "save">) {
  const { t } = useI18n();
  if (providers.isPending) {
    return (
      <div className="main">
        <div className="skeleton" style={{ height: 120 }} />
        <div className="skeleton" style={{ height: 260 }} />
      </div>
    );
  }
  if (providers.isError) {
    return (
      <div className="main">
        <div className="empty-state">
          <strong>{t("providers.loadFailed")}</strong>
          <span>{providers.error.message}</span>
          <button className="ghost" onClick={() => void providers.refetch()}>
            {t("providers.retry")}
          </button>
        </div>
      </div>
    );
  }
  return <ProvidersReady providers={providers} save={save} />;
}

function ProvidersReady({ providers, save }: Pick<TabBodyProps, "providers" | "save">) {
  const { t } = useI18n();
  return (
    <div className="main">
      {providers.data ? (
        <ProviderEditor
          providers={providers.data.providers}
          onSave={(list) => save.mutate(list)}
          saving={save.isPending}
        />
      ) : null}
      {save.isError ? (
        <div className="empty-state" role="alert">
          <strong>{t("providers.saveFailed")}</strong>
          <span>{save.error.message}</span>
        </div>
      ) : null}
    </div>
  );
}

function RoutesTab({ simulation }: Pick<TabBodyProps, "simulation">) {
  return (
    <Routes
      onSimulate={(input) => simulation.mutate(input)}
      data={simulation.data}
      pending={simulation.isPending}
    />
  );
}

function PlaygroundTab({ chat }: Pick<TabBodyProps, "chat">) {
  return (
    <Playground
      onChat={(input) => chat.mutate(input)}
      result={chat.data}
      pending={chat.isPending}
      error={chat.isError ? chat.error.message : undefined}
    />
  );
}

function DashboardTab({
  metrics,
  range,
  onRangeChange,
}: Pick<TabBodyProps, "metrics" | "range" | "onRangeChange">) {
  const { t } = useI18n();
  return (
    <>
      {metrics.isError ? <div className="main error">{t("dashboard.loadFailed")}</div> : null}
      <Dashboard data={metrics.data} range={range} onRangeChange={onRangeChange} />
    </>
  );
}
