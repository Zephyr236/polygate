/**
 * Token gate and root application shell.
 */

import { useState } from "react";

/** Login form storing the admin bearer token. */
export function TokenGate({ onSubmit }: { onSubmit: (token: string) => void }) {
  const [token, setToken] = useState("");
  return (
    <div className="main" style={{ maxWidth: 420, margin: "80px auto" }}>
      <div className="card">
        <h3>Admin token</h3>
        <input
          aria-label="admin-token"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Bearer token from ADMIN_TOKEN"
        />
        <div style={{ marginTop: 12 }}>
          <button className="action" disabled={token.trim() === ""} onClick={() => onSubmit(token.trim())}>
            Enter
          </button>
        </div>
      </div>
    </div>
  );
}
