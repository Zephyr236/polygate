/**
 * Generated caller API keys with tiers and provider allowlists.
 */

import { useState } from "react";

import { Icon } from "../components/icons";
import { useI18n } from "../i18n";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "../state/queries";
import { ProviderPicker } from "./ProviderPicker";
import { calendarTime } from "../utils/format";
import type { ApiKeyTier, ProviderConfig } from "../api/types";

const TIERS: ApiKeyTier[] = ["premium", "standard", "economy"];

function inputProblem(name: string, providerCount: number, t: ReturnType<typeof useI18n>["t"]): string {
  if (!name.trim()) return t("apiKeys.nameRequired");
  if (providerCount === 0) return t("apiKeys.providersRequired");
  return "";
}

function toggleProvider(active: string[], id: string): string[] {
  return active.includes(id) ? active.filter((item) => item !== id) : [...active, id];
}

async function writeClipboard(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

function CreateFeedback({ error, failure }: { error: string; failure: Error | null }) {
  const { t } = useI18n();
  if (!error && !failure) return null;
  return <span className="error">{error || `${t("apiKeys.createFailed")}: ${failure?.message ?? ""}`}</span>;
}

function GenerateButton({ pending }: { pending: boolean }) {
  const { t } = useI18n();
  return (
    <button className="action" type="submit" disabled={pending}>
      <Icon name="key" />
      {pending ? t("apiKeys.generating") : t("apiKeys.generate")}
    </button>
  );
}

function SecretCard({ secret, copied, onCopy }: { secret: string; copied: boolean; onCopy: () => void }) {
  const { t } = useI18n();
  if (!secret) return null;
  return (
    <div className="secret-card" role="status">
      <div>
        <strong>{t("apiKeys.createdTitle")}</strong>
        <p>{t("apiKeys.createdHint")}</p>
      </div>
      <div className="secret-row">
        <code>{secret}</code>
        <button className="ghost" type="button" onClick={onCopy}>
          <Icon name={copied ? "check" : "save"} size={16} />
          {copied ? t("apiKeys.copied") : t("apiKeys.copy")}
        </button>
      </div>
      <small className="mono">{t("apiKeys.usageHint")}</small>
    </div>
  );
}

function CreatePanel({ providers }: { providers: ProviderConfig[] }) {
  const { t } = useI18n();
  const create = useCreateApiKey();
  const [name, setName] = useState("");
  const [tier, setTier] = useState<ApiKeyTier>("standard");
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [secret, setSecret] = useState("");
  const [copied, setCopied] = useState(false);
  const toggle = (id: string) => {
    setSelected(toggleProvider(selected, id));
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const problem = inputProblem(name, selected.length, t);
    if (problem) {
      setError(problem);
      return;
    }
    setError("");
    setSecret("");
    create.mutate(
      { name: name.trim(), tier, allowed_providers: selected },
      { onSuccess: (created) => setSecret(created.token) },
    );
  };

  const copy = async () => {
    setCopied(await writeClipboard(secret));
  };

  return (
    <section className="card key-panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">{t("apiKeys.createEyebrow")}</div>
          <h3>{t("apiKeys.createTitle")}</h3>
        </div>
      </div>
      <form className="key-form" onSubmit={submit}>
        <label className="field">
          <span className="field-label">{t("apiKeys.name")}</span>
          <input
            aria-label="api-key-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t("apiKeys.namePlaceholder")}
          />
        </label>
        <label className="field">
          <span className="field-label">{t("apiKeys.tier")}</span>
          <select
            aria-label="api-key-tier"
            value={tier}
            onChange={(event) => setTier(event.target.value as ApiKeyTier)}
          >
            {TIERS.map((item) => (
              <option key={item} value={item}>
                {t(`apiKeys.tier.${item}`)}
              </option>
            ))}
          </select>
          <small className="field-hint">{t(`apiKeys.tierHint.${tier}`)}</small>
        </label>
        <div className="field">
          <span className="field-label">{t("apiKeys.providers")}</span>
          <ProviderPicker
            providers={providers}
            selected={selected}
            onToggle={toggle}
            onSelectAll={(ids) => setSelected(Array.from(new Set([...selected, ...ids])))}
            onClear={() => setSelected([])}
          />
          <small className="field-hint">{t("apiKeys.providersHint")}</small>
        </div>
        <CreateFeedback error={error} failure={create.isError ? create.error : null} />
        <GenerateButton pending={create.isPending} />
      </form>
      <SecretCard secret={secret} copied={copied} onCopy={() => void copy()} />
    </section>
  );
}

function KeyRow({
  item,
}: {
  item: {
    id: string;
    name: string;
    prefix: string;
    tier: ApiKeyTier;
    allowed_providers: string[];
    created_at: number;
    last_used_at: number | null;
  };
}) {
  const { t } = useI18n();
  const revoke = useRevokeApiKey();
  return (
    <div className="key-row" data-testid={`api-key-${item.id}`}>
      <div className="key-row-top">
        <div className="key-identity">
          <strong>{item.name}</strong>
          <span className="mono muted">{item.prefix}…</span>
        </div>
        <span className={`tier-badge ${item.tier}`}>{t(`apiKeys.tier.${item.tier}`)}</span>
        <button className="ghost danger" onClick={() => revoke.mutate(item.id)} disabled={revoke.isPending}>
          {t("apiKeys.revoke")}
        </button>
      </div>
      <div className="key-row-bottom">
        <div className="tag-list">
          {item.allowed_providers.map((provider) => (
            <span className="tag" key={provider}>
              {provider}
            </span>
          ))}
        </div>
        <div className="key-meta">
          <span>
            {t("apiKeys.createdAt")}: {calendarTime(item.created_at)}
          </span>
          <span>
            {t("apiKeys.lastUsed")}:{" "}
            {item.last_used_at ? calendarTime(item.last_used_at) : t("apiKeys.never")}
          </span>
        </div>
      </div>
    </div>
  );
}

function keyCount(data: ReturnType<typeof useApiKeys>["data"]): number {
  return data?.keys.length ?? 0;
}

/** API key management page. */
export function ApiKeys({ providers }: { providers: ProviderConfig[] }) {
  const { t } = useI18n();
  const keys = useApiKeys();
  return (
    <div className="main key-page">
      <div className="empty-state key-intro">
        <strong>{t("apiKeys.introTitle")}</strong>
        <span>{t("apiKeys.intro")}</span>
      </div>
      <div className="key-layout">
        <CreatePanel providers={providers} />
        <section className="card key-panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">{t("apiKeys.keyList")}</div>
              <h3>{t("apiKeys.keyList")}</h3>
            </div>
            <span className="pill mono">{keyCount(keys.data)}</span>
          </div>
          <p className="muted">{t("apiKeys.keyListHint")}</p>
          {keys.isPending ? <div className="skeleton" style={{ height: 120 }} /> : null}
          {keys.isError ? (
            <div className="empty-state" role="alert">
              <strong>{t("apiKeys.loadFailed")}</strong>
              <button className="ghost" onClick={() => void keys.refetch()}>
                {t("apiKeys.retry")}
              </button>
            </div>
          ) : null}
          {keys.data && keys.data.keys.length === 0 ? (
            <div className="empty-state">
              <strong>{t("apiKeys.empty")}</strong>
              <span>{t("apiKeys.emptyHint")}</span>
            </div>
          ) : null}
          <div className="key-list">
            {keys.data?.keys.map((item) => (
              <KeyRow item={item} key={item.id} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
