/**
 * Token gate and root application shell.
 */

import { useState } from "react";

import { Icon } from "../components/icons";

/** Login form storing the admin bearer token. */
export function TokenGate({ onSubmit }: { onSubmit: (token: string) => void }) {
  const [token, setToken] = useState("");
  return (
    <div className="login-shell">
      <main className="login-card">
        <div className="brand">
          <div className="brand-mark">PG</div>
          <div>
            <h1>polygate</h1>
            <p>multi-provider routing gateway</p>
          </div>
        </div>
        <div>
          <h2>Admin console</h2>
          <p className="muted">
            Authenticate with the bearer token from <span className="mono">ADMIN_TOKEN</span>. It stays in
            this browser only.
          </p>
        </div>
        <label className="field">
          <span className="field-label">Admin token</span>
          <input
            aria-label="admin-token"
            type="password"
            autoComplete="current-password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && token.trim() !== "") onSubmit(token.trim());
            }}
            placeholder="Bearer token from ADMIN_TOKEN"
          />
        </label>
        <button className="action" disabled={token.trim() === ""} onClick={() => onSubmit(token.trim())}>
          <Icon name="check" />
          Enter
        </button>
        <div className="login-foot">
          <span className="status-line">
            <span className="status-dot" />
            local gateway
          </span>
          <span className="pill mono">/v1 · /admin</span>
        </div>
      </main>
    </div>
  );
}
