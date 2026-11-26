/**
 * Provider editor: edit per-channel routing, concurrency, cost and windows.
 */

import { useState } from "react";

import type { ProviderConfig } from "../api/types";
import { Icon } from "../components/icons";
import { ProviderCard } from "./ProviderCard";
import type { ProviderDraft } from "./providerDraft";

/** Build an editable draft from a provider config. */
export function toDraft(config: ProviderConfig): ProviderDraft {
  return {
    id: config.id,
    base_url: config.base_url,
    protocol: config.protocol,
    model: config.model,
    api_key_env: config.api_key_env,
    auth_style: config.auth_style,
    session_header: config.session_header ?? "",
    session_mode: config.session_mode,
    lanes: String(config.lanes),
    max_concurrency: String(config.max_concurrency),
    max_tokens_min: String(config.max_tokens_min),
    stream_usage: config.stream_usage,
    cost_coefficient: String(config.cost_coefficient),
    priority: String(config.priority),
    enabled: config.enabled,
    tags: config.tags.join(","),
  };
}

/** Parse comma-separated tags into a trimmed list. */
function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

/** Parse an optional header name, mapping blanks to null. */
function optionalHeader(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

/** Convert an editable draft back into an API payload. */
export function fromDraft(draft: ProviderDraft): ProviderConfig {
  return {
    id: draft.id.trim(),
    base_url: draft.base_url.trim(),
    protocol: draft.protocol,
    model: draft.model.trim(),
    aliases: [],
    api_key_env: draft.api_key_env.trim(),
    auth_style: draft.auth_style,
    session_header: optionalHeader(draft.session_header),
    session_mode: draft.session_mode,
    lanes: Number(draft.lanes) || 1,
    max_concurrency: Number(draft.max_concurrency) || 1,
    max_tokens_min: Number(draft.max_tokens_min) || 0,
    stream_usage: draft.stream_usage,
    cost_coefficient: Number(draft.cost_coefficient) || 1,
    priority: Number(draft.priority) || 0,
    enabled: draft.enabled,
    tags: parseTags(draft.tags),
  };
}

/** Validate a draft before sending it to the server. */
export function validateDraft(draft: ProviderDraft): string[] {
  const problems: string[] = [];
  if (!/^[a-z0-9][a-z0-9-]*$/.test(draft.id)) problems.push("id must be lowercase alphanumeric with dashes");
  if (!draft.base_url.startsWith("http")) problems.push("base_url must be an http(s) URL");
  if (Number(draft.max_concurrency) < 1) problems.push("max_concurrency must be at least 1");
  if (Number(draft.cost_coefficient) <= 0) problems.push("cost_coefficient must be positive");
  return problems;
}

const EMPTY_DRAFT: ProviderDraft = {
  id: "new-provider",
  base_url: "https://example.com",
  protocol: "openai",
  model: "deepseek-v4.1-flash",
  api_key_env: "NEW_PROVIDER_KEY",
  auth_style: "bearer",
  session_header: "",
  session_mode: "none",
  lanes: "1",
  max_concurrency: "4",
  max_tokens_min: "0",
  stream_usage: "none",
  cost_coefficient: "1",
  priority: "1",
  enabled: true,
  tags: "",
};

/** Filter drafts by id, model or tags. */
function filterDrafts(drafts: ProviderDraft[], filter: string): { draft: ProviderDraft; index: number }[] {
  const needle = filter.trim().toLowerCase();
  return drafts
    .map((draft, index) => ({ draft, index }))
    .filter(
      ({ draft }) =>
        needle === "" ||
        draft.id.toLowerCase().includes(needle) ||
        draft.model.toLowerCase().includes(needle) ||
        draft.tags.toLowerCase().includes(needle),
    );
}

/** Render the provider cards or an appropriate empty state. */
function ProviderList({
  drafts,
  visible,
  update,
  remove,
}: {
  drafts: ProviderDraft[];
  visible: { draft: ProviderDraft; index: number }[];
  update: (index: number, patch: Partial<ProviderDraft>) => void;
  remove: (index: number) => void;
}) {
  if (drafts.length === 0) {
    return (
      <div className="empty-state">
        <strong>No providers configured</strong>
        <span>Add a provider to start routing traffic.</span>
      </div>
    );
  }
  if (visible.length === 0) {
    return (
      <div className="empty-state">
        <strong>No matches</strong>
        <span>Clear the filter to see all {drafts.length} providers.</span>
      </div>
    );
  }
  return (
    <div className="provider-grid">
      {visible.map(({ draft, index }) => (
        <ProviderCard key={index} draft={draft} index={index} onChange={update} onRemove={remove} />
      ))}
    </div>
  );
}

/** Editable provider pool. */
export function ProviderEditor({
  providers,
  onSave,
  saving,
}: {
  providers: ProviderConfig[];
  onSave: (providers: ProviderConfig[]) => void;
  saving: boolean;
}) {
  const [drafts, setDrafts] = useState<ProviderDraft[]>(() => providers.map(toDraft));
  const [errors, setErrors] = useState<string[]>([]);
  const [filter, setFilter] = useState("");

  const update = (index: number, patch: Partial<ProviderDraft>) => {
    setDrafts((current) => current.map((draft, i) => (i === index ? { ...draft, ...patch } : draft)));
  };

  const remove = (index: number) => {
    setDrafts((current) => current.filter((_, i) => i !== index));
    setErrors([]);
  };

  const submit = () => {
    const problems = drafts.flatMap(validateDraft);
    setErrors(problems);
    if (problems.length > 0) return;
    onSave(drafts.map(fromDraft));
  };

  const visible = filterDrafts(drafts, filter);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Provider pool</div>
          <p>Channel endpoints, credentials, concurrency and cost. Secrets stay in environment variables.</p>
        </div>
        <div className="toolbar">
          <input
            aria-label="provider-filter"
            placeholder="Filter by id, model or tag"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            style={{ width: 240 }}
          />
          <button
            className="ghost"
            onClick={() => {
              setDrafts((current) => [...current, { ...EMPTY_DRAFT }]);
              setErrors([]);
            }}
          >
            <Icon name="plus" size={16} />
            Add provider
          </button>
        </div>
      </div>

      {errors.length > 0 ? (
        <div className="card" role="alert">
          <div className="eyebrow">Validation</div>
          {errors.map((problem) => (
            <div className="error" key={problem}>
              {problem}
            </div>
          ))}
        </div>
      ) : null}

      <ProviderList drafts={drafts} visible={visible} update={update} remove={remove} />

      <div className="savebar">
        <div className="muted">
          {drafts.length} provider{drafts.length === 1 ? "" : "s"}
          {filter ? ` · ${visible.length} shown` : ""}
        </div>
        <button className="action" onClick={submit} disabled={saving}>
          {saving ? "Saving…" : "Save providers"}
        </button>
      </div>
    </>
  );
}
