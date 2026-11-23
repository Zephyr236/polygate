/**
 * Application shell wiring navigation, queries and the token gate.
 */

import { useState } from "react";

import { clearToken, setToken } from "./api/client";
import { Dashboard } from "./pages/Dashboard";
import { TokenGate } from "./pages/Login";
import { Playground } from "./pages/Playground";
import { Routes } from "./pages/Routes";
import { ProviderEditor } from "./pages/Providers";
import { useChat, useMetrics, useProviders, useSaveProviders, useSimulate } from "./state/queries";

const TABS = ["Dashboard", "Providers", "Routes", "Playground"] as const;
type Tab = (typeof TABS)[number];

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

  return (
    <div className="app">
      <header className="topbar">
        <h1>polygate</h1>
        <nav className="nav">
          {TABS.map((item) => (
            <button key={item} className={item === tab ? "active" : ""} onClick={() => setTab(item)}>
              {item}
            </button>
          ))}
        </nav>
        <button
          className="action"
          style={{ marginLeft: "auto" }}
          onClick={() => {
            clearToken();
            setTokenState("");
          }}
        >
          Sign out
        </button>
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
  return (
    <>
      {providers.data ? (
        <ProviderEditor
          providers={providers.data.providers}
          onSave={(list) => save.mutate(list)}
          saving={save.isPending}
        />
      ) : null}
      {save.isError ? <div className="main error">Save failed</div> : null}
    </>
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
