/**
 * Token gate and root application shell.
 */

import { useState } from "react";

import { Icon } from "../components/icons";
import { useI18n } from "../i18n";

/** Login form storing the admin bearer token. */
export function TokenGate({ onSubmit }: { onSubmit: (token: string) => void }) {
  const { t } = useI18n();
  const [token, setToken] = useState("");
  return (
    <div className="login-shell">
      <main className="login-card">
        <div className="brand">
          <div className="brand-mark">PG</div>
          <div>
            <h1>polygate</h1>
            <p>{t("app.tagline")}</p>
          </div>
        </div>
        <div>
          <h2>{t("login.title")}</h2>
          <p className="muted">{t("login.description")}</p>
        </div>
        <label className="field">
          <span className="field-label">{t("login.tokenLabel")}</span>
          <input
            aria-label="admin-token"
            type="password"
            autoComplete="current-password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && token.trim() !== "") onSubmit(token.trim());
            }}
            placeholder={t("login.placeholder")}
          />
        </label>
        <button className="action" disabled={token.trim() === ""} onClick={() => onSubmit(token.trim())}>
          <Icon name="check" />
          {t("login.enter")}
        </button>
        <div className="login-foot">
          <span className="status-line">
            <span className="status-dot" />
            {t("login.local")}
          </span>
          <span className="pill mono">{t("login.endpoints")}</span>
        </div>
      </main>
    </div>
  );
}
