/**
 * Application shell wiring navigation, queries and the token gate.
 */

import { useState } from "react";

import { clearToken, setToken } from "./api/client";
import { Icon } from "./components/icons";
import { Dashboard } from "./pages/Dashboard";
import { TokenGate } from "./pages/Login";
import { Playground } from "./pages/Playground";
import { Routes } from "./pages/Routes";
import { ProviderEditor } from "./pages/Providers";
import { useChat, useMetrics, useProviders, useSaveProviders, useSimulate } from "./state/queries";

type Tab = "Dashboard" | "Providers" | "Routes" | "Playground";

const NAV = [
  { name: "Dashboard", icon: "dashboard" },
  { name: "Providers", icon: "server" },
  { name: "Routes", icon: "route" },
  { name: "Playground", icon: "play" },
] as const satisfies readonly { name: Tab; icon: "dashboard" | "server" | "route" | "play" }[];

/** Root component rendering the selected tab. */
export function App({ initialToken }: { initialToken: string }) {
  const [token, setTokenState] = useState(initialToken);
  const [tab, setTab] = useState<Tab>("Dashboard");
  const [range, setRange] = useState("1h");
  const providers = useProviders();
  const metrics = useMetrics(range);
  const save = useSaveProviders();
  const simulation = useSimulate();
  const chat = useChat();

  if (!token) {
    return (
      <TokenGate
        onSubmit={(value) => {
          setToken(value);
          setTokenState(value);
        }}
      />
    );
  }

  const providerCount = providers.data?.providers.length ?? 0;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">PG</div>
          <div>
            <h1>polygate</h1>
            <p>routing gateway</p>
          </div>
        </div>
        <nav className="side-nav" aria-label="Primary">
          {NAV.map((item) => (
            <button
              key={item.name}
              className={item.name === tab ? "active" : ""}
              onClick={() => setTab(item.name)}
            >
              <Icon name={item.icon} />
              <span>{item.name}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="status-line">
            <span className="status-dot" />
            <span>ready</span>
          </div>
          <div className="muted">{providerCount} providers</div>
          <button
            className="ghost"
            onClick={() => {
              clearToken();
              setTokenState("");
            }}
          >
            <Icon name="logout" />
            Sign out
          </button>
        </div>
      </aside>
      <section className="workspace">
        <header className="workspace-head">
          <div>
            <div className="eyebrow">Workspace</div>
            <h2>{tab}</h2>
          </div>
          <div className="workspace-meta">
            <span className="pill">
              <Icon name="pulse" size={14} />
              live
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
          <strong>Providers could not be loaded</strong>
          <span>{providers.error.message}</span>
          <button className="ghost" onClick={() => void providers.refetch()}>
            Retry
          </button>
        </div>
      </div>
    );
  }
  return <ProvidersReady providers={providers} save={save} />;
}

function ProvidersReady({ providers, save }: Pick<TabBodyProps, "providers" | "save">) {
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
          <strong>Save failed</strong>
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
  return (
    <>
      {metrics.isError ? <div className="main error">Failed to load metrics</div> : null}
      <Dashboard data={metrics.data} range={range} onRangeChange={onRangeChange} />
    </>
  );
}
