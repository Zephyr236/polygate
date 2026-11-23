/**
 * Provider editor: edit per-channel routing, concurrency, cost and windows.
 */

import { useState } from "react";

import type { ProviderConfig } from "../api/types";

/** Editable copy of a provider config with string-encoded numeric inputs. */
interface ProviderDraft {
  id: string;
  base_url: string;
  protocol: ProviderConfig["protocol"];
  model: string;
  api_key_env: string;
  auth_style: ProviderConfig["auth_style"];
  session_header: string;
  session_mode: ProviderConfig["session_mode"];
  lanes: string;
  max_concurrency: string;
  max_tokens_min: string;
  stream_usage: ProviderConfig["stream_usage"];
  cost_coefficient: string;
  priority: string;
  enabled: boolean;
  tags: string;
}

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

/** Editable table of provider configs. */
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

  const update = (index: number, patch: Partial<ProviderDraft>) => {
    setDrafts((current) => current.map((draft, i) => (i === index ? { ...draft, ...patch } : draft)));
  };

  const submit = () => {
    const problems = drafts.flatMap(validateDraft);
    setErrors(problems);
    if (problems.length > 0) return;
    onSave(drafts.map(fromDraft));
  };

  return (
    <div className="main">
      {errors.length > 0 ? (
        <div className="card" role="alert">
          {errors.map((problem) => (
            <div className="error" key={problem}>
              {problem}
            </div>
          ))}
        </div>
      ) : null}
      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>base_url</th>
              <th>protocol</th>
              <th>model</th>
              <th>api_key_env</th>
              <th>auth</th>
              <th>session header</th>
              <th>lanes</th>
              <th>concurrency</th>
              <th>min tokens</th>
              <th>cost coefficient</th>
              <th>priority</th>
              <th>enabled</th>
            </tr>
          </thead>
          <tbody>
            {drafts.map((draft, index) => (
              <tr key={index}>
                <td>
                  <input
                    aria-label={`id-${index}`}
                    value={draft.id}
                    onChange={(event) => update(index, { id: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`base_url-${index}`}
                    value={draft.base_url}
                    onChange={(event) => update(index, { base_url: event.target.value })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`protocol-${index}`}
                    value={draft.protocol}
                    onChange={(event) =>
                      update(index, { protocol: event.target.value as ProviderConfig["protocol"] })
                    }
                  >
                    <option value="openai">openai</option>
                    <option value="anthropic">anthropic</option>
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`model-${index}`}
                    value={draft.model}
                    onChange={(event) => update(index, { model: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`api_key_env-${index}`}
                    value={draft.api_key_env}
                    onChange={(event) => update(index, { api_key_env: event.target.value })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`auth-${index}`}
                    value={draft.auth_style}
                    onChange={(event) =>
                      update(index, { auth_style: event.target.value as ProviderConfig["auth_style"] })
                    }
                  >
                    <option value="bearer">bearer</option>
                    <option value="x-api-key">x-api-key</option>
                    <option value="both">both</option>
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`session-${index}`}
                    value={draft.session_header}
                    onChange={(event) => update(index, { session_header: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`lanes-${index}`}
                    value={draft.lanes}
                    onChange={(event) => update(index, { lanes: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`concurrency-${index}`}
                    value={draft.max_concurrency}
                    onChange={(event) => update(index, { max_concurrency: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`min-tokens-${index}`}
                    value={draft.max_tokens_min}
                    onChange={(event) => update(index, { max_tokens_min: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`cost-${index}`}
                    value={draft.cost_coefficient}
                    onChange={(event) => update(index, { cost_coefficient: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`priority-${index}`}
                    value={draft.priority}
                    onChange={(event) => update(index, { priority: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`enabled-${index}`}
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(event) => update(index, { enabled: event.target.checked })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", gap: 12 }}>
        <button className="action" onClick={() => setDrafts((current) => [...current, { ...EMPTY_DRAFT }])}>
          Add provider
        </button>
        <button className="action" onClick={submit} disabled={saving}>
          {saving ? "Saving…" : "Save providers"}
        </button>
      </div>
    </div>
  );
}
