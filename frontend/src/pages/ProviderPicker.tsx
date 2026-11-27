/**
 * Searchable multi-select used to scope a caller key to providers.
 */

import { useState } from "react";

import type { ProviderConfig } from "../api/types";
import { Icon } from "../components/icons";
import { useI18n } from "../i18n";

function matches(provider: ProviderConfig, needle: string): boolean {
  return (
    !needle || provider.id.toLowerCase().includes(needle) || provider.model.toLowerCase().includes(needle)
  );
}

function PickedList({ selected, onToggle }: { selected: string[]; onToggle: (id: string) => void }) {
  const { t } = useI18n();
  if (selected.length === 0) return <span className="muted">{t("apiKeys.noneSelected")}</span>;
  return (
    <>
      {selected.map((id) => (
        <span className="picked-chip" key={id}>
          {id}
          <button type="button" aria-label={`remove-provider-${id}`} onClick={() => onToggle(id)}>
            ×
          </button>
        </span>
      ))}
    </>
  );
}

function PickerOption({
  provider,
  picked,
  onToggle,
}: {
  provider: ProviderConfig;
  picked: boolean;
  onToggle: (id: string) => void;
}) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={picked}
      aria-label={`provider-option-${provider.id}`}
      className={picked ? "picker-option picked" : "picker-option"}
      onClick={() => onToggle(provider.id)}
    >
      <span>
        <strong>{provider.id}</strong>
        <small>{provider.model}</small>
      </span>
      <span className="picker-mark">{picked ? "✓" : "+"}</span>
    </button>
  );
}

/** Searchable provider multi-select with selected chips. */
export function ProviderPicker({
  providers,
  selected,
  onToggle,
  onSelectAll,
  onClear,
}: {
  providers: ProviderConfig[];
  selected: string[];
  onToggle: (id: string) => void;
  onSelectAll: (ids: string[]) => void;
  onClear: () => void;
}) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const filtered = providers.filter((provider) => matches(provider, needle));
  return (
    <div className="provider-picker">
      <div className="picked-list">
        <PickedList selected={selected} onToggle={onToggle} />
      </div>
      <div className="picker-search">
        <Icon name="search" size={15} />
        <input
          aria-label="provider-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("apiKeys.providerSearch")}
        />
      </div>
      <div
        className="picker-list"
        role="listbox"
        aria-label={t("apiKeys.providers")}
        aria-multiselectable="true"
      >
        {filtered.map((provider) => (
          <PickerOption
            key={provider.id}
            provider={provider}
            picked={selected.includes(provider.id)}
            onToggle={onToggle}
          />
        ))}
        {filtered.length === 0 ? <div className="picker-empty">{t("apiKeys.noProviders")}</div> : null}
      </div>
      <div className="picker-foot">
        <span>{t("apiKeys.selectedCount", { count: selected.length })}</span>
        <button
          type="button"
          className="linkish"
          onClick={() => onSelectAll(filtered.map((provider) => provider.id))}
        >
          {t("apiKeys.selectAll")}
        </button>
        <button type="button" className="linkish" onClick={onClear}>
          {t("apiKeys.clear")}
        </button>
      </div>
    </div>
  );
}
