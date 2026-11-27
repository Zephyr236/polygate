/**
 * One editable provider card.
 */

import { useState, type ReactNode } from "react";

import type { ProviderConfig } from "../api/types";
import { Icon } from "../components/icons";
import { useI18n } from "../i18n";
import type { ProviderDraft } from "./providerDraft";

type Change = (index: number, patch: Partial<ProviderDraft>) => void;

/** Render one provider with grouped editable fields. */
function ProviderToggle({ open, index, onToggle }: { open: boolean; index: number; onToggle: () => void }) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      className={open ? "provider-toggle open" : "provider-toggle"}
      aria-label={`toggle-provider-${index}`}
      aria-expanded={open}
      title={open ? t("providers.collapse") : t("providers.expand")}
      onClick={onToggle}
    >
      <Icon name="chevron" size={16} />
    </button>
  );
}

function ProviderPills({ draft }: { draft: ProviderDraft }) {
  const { t } = useI18n();
  return (
    <div className="provider-summary-pills">
      <span className="pill">{t("providers.pill.priority", { value: draft.priority || "—" })}</span>
      <span className="pill">{t("providers.pill.cost", { value: draft.cost_coefficient || "—" })}</span>
      <span className="pill">{draft.max_concurrency || "—"}×</span>
      <span className="pill">{draft.model || t("providers.pill.noModel")}</span>
    </div>
  );
}

function ProviderRowHeader({
  draft,
  index,
  open,
  onToggle,
  onChange,
  onRemove,
}: {
  draft: ProviderDraft;
  index: number;
  open: boolean;
  onToggle: () => void;
  onChange: Change;
  onRemove: (index: number) => void;
}) {
  const { t } = useI18n();
  return (
    <header className="provider-row-head">
      <ProviderToggle open={open} index={index} onToggle={onToggle} />
      <div className="provider-primary">
        <div className="eyebrow">{t("providers.eyebrow")}</div>
        <input
          aria-label={`id-${index}`}
          className="provider-id"
          value={draft.id}
          onChange={(event) => onChange(index, { id: event.target.value })}
        />
      </div>
      <span className="provider-url mono" title={draft.base_url}>
        {draft.base_url}
      </span>
      <ProviderPills draft={draft} />
      <div className="provider-row-actions">
        <label className="switch">
          <input
            aria-label={`enabled-${index}`}
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => onChange(index, { enabled: event.target.checked })}
          />
          {t("providers.enabled")}
        </label>
        <button className="danger" onClick={() => onRemove(index)}>
          {t("providers.remove")}
        </button>
      </div>
    </header>
  );
}

/** Render one expandable provider list row with its editable fields. */
export function ProviderCard({
  draft,
  index,
  onChange,
  onRemove,
}: {
  draft: ProviderDraft;
  index: number;
  onChange: Change;
  onRemove: (index: number) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <article className="provider-row" data-testid={`provider-card-${index}`}>
      <ProviderRowHeader
        draft={draft}
        index={index}
        open={open}
        onToggle={() => setOpen((value) => !value)}
        onChange={onChange}
        onRemove={onRemove}
      />
      {open ? (
        <div className="field-grid provider-row-body">
          <ConnectionFields draft={draft} index={index} onChange={onChange} />
          <RuntimeFields draft={draft} index={index} onChange={onChange} />
          <RoutingFields draft={draft} index={index} onChange={onChange} />
          <MetaFields draft={draft} index={index} onChange={onChange} />
        </div>
      ) : null}
    </article>
  );
}

function Field({ label, wide = false, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return (
    <label className={`field${wide ? " wide" : ""}`}>
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}

function ConnectionFields({
  draft,
  index,
  onChange,
}: {
  draft: ProviderDraft;
  index: number;
  onChange: Change;
}) {
  const { t } = useI18n();
  return (
    <>
      <Field label={t("providers.field.baseUrl")} wide>
        <input
          aria-label={`base_url-${index}`}
          value={draft.base_url}
          onChange={(event) => onChange(index, { base_url: event.target.value })}
        />
      </Field>
      <Field label={t("providers.field.model")}>
        <input
          aria-label={`model-${index}`}
          value={draft.model}
          onChange={(event) => onChange(index, { model: event.target.value })}
        />
      </Field>
      <Field label={t("providers.field.apiKeyEnv")}>
        <input
          aria-label={`api_key_env-${index}`}
          value={draft.api_key_env}
          onChange={(event) => onChange(index, { api_key_env: event.target.value })}
        />
      </Field>
      <Field label={t("providers.field.protocol")}>
        <select
          aria-label={`protocol-${index}`}
          value={draft.protocol}
          onChange={(event) =>
            onChange(index, { protocol: event.target.value as ProviderConfig["protocol"] })
          }
        >
          <option value="openai">{t("providers.protocol.openai")}</option>
          <option value="anthropic">{t("providers.protocol.anthropic")}</option>
        </select>
      </Field>
      <Field label={t("providers.field.auth")}>
        <select
          aria-label={`auth-${index}`}
          value={draft.auth_style}
          onChange={(event) =>
            onChange(index, { auth_style: event.target.value as ProviderConfig["auth_style"] })
          }
        >
          <option value="bearer">{t("providers.auth.bearer")}</option>
          <option value="x-api-key">{t("providers.auth.x-api-key")}</option>
          <option value="both">{t("providers.auth.both")}</option>
        </select>
      </Field>
      <Field label={t("providers.field.sessionHeader")}>
        <input
          aria-label={`session-${index}`}
          placeholder={t("providers.sessionPlaceholder")}
          value={draft.session_header}
          onChange={(event) => onChange(index, { session_header: event.target.value })}
        />
      </Field>
    </>
  );
}

function RuntimeFields({
  draft,
  index,
  onChange,
}: {
  draft: ProviderDraft;
  index: number;
  onChange: Change;
}) {
  const { t } = useI18n();
  return (
    <>
      <Field label={t("providers.field.sessionMode")}>
        <select
          aria-label={`session_mode-${index}`}
          value={draft.session_mode}
          onChange={(event) =>
            onChange(index, { session_mode: event.target.value as ProviderConfig["session_mode"] })
          }
        >
          <option value="none">{t("providers.session.none")}</option>
          <option value="uuid-per-request">{t("providers.session.uuid-per-request")}</option>
          <option value="uuid-per-lane">{t("providers.session.uuid-per-lane")}</option>
        </select>
      </Field>
      <Field label={t("providers.field.lanes")}>
        <input
          aria-label={`lanes-${index}`}
          inputMode="numeric"
          value={draft.lanes}
          onChange={(event) => onChange(index, { lanes: event.target.value })}
        />
      </Field>
      <Field label={t("providers.field.concurrency")}>
        <input
          aria-label={`concurrency-${index}`}
          inputMode="numeric"
          value={draft.max_concurrency}
          onChange={(event) => onChange(index, { max_concurrency: event.target.value })}
        />
      </Field>
      <Field label={t("providers.field.minTokens")}>
        <input
          aria-label={`min-tokens-${index}`}
          inputMode="numeric"
          value={draft.max_tokens_min}
          onChange={(event) => onChange(index, { max_tokens_min: event.target.value })}
        />
      </Field>
    </>
  );
}

function RoutingFields({
  draft,
  index,
  onChange,
}: {
  draft: ProviderDraft;
  index: number;
  onChange: Change;
}) {
  const { t } = useI18n();
  return (
    <>
      <Field label={t("providers.field.cost")}>
        <input
          aria-label={`cost-${index}`}
          inputMode="decimal"
          value={draft.cost_coefficient}
          onChange={(event) => onChange(index, { cost_coefficient: event.target.value })}
        />
      </Field>
      <Field label={t("providers.field.priority")}>
        <input
          aria-label={`priority-${index}`}
          inputMode="numeric"
          value={draft.priority}
          onChange={(event) => onChange(index, { priority: event.target.value })}
        />
      </Field>
      <Field label={t("providers.field.streamUsage")}>
        <select
          aria-label={`stream_usage-${index}`}
          value={draft.stream_usage}
          onChange={(event) =>
            onChange(index, { stream_usage: event.target.value as ProviderConfig["stream_usage"] })
          }
        >
          <option value="none">{t("providers.stream.none")}</option>
          <option value="include_usage">{t("providers.stream.include_usage")}</option>
          <option value="message_delta">{t("providers.stream.message_delta")}</option>
        </select>
      </Field>
    </>
  );
}

function MetaFields({ draft, index, onChange }: { draft: ProviderDraft; index: number; onChange: Change }) {
  const { t } = useI18n();
  return (
    <Field label={t("providers.field.tags")} wide>
      <input
        aria-label={`tags-${index}`}
        placeholder={t("providers.tagsPlaceholder")}
        value={draft.tags}
        onChange={(event) => onChange(index, { tags: event.target.value })}
      />
    </Field>
  );
}
