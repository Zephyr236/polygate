/**
 * Password gate: first-run setup, login and session entry.
 */

import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { fetchAuthStatus, loginPassword, setupPassword } from "../api/client";
import { Icon } from "../components/icons";
import { useI18n, type Translate } from "../i18n";

/** Brand header used by the login card. */
function LoginBrand({ tagline }: { tagline: string }) {
  return (
    <div className="brand">
      <div className="brand-mark">PG</div>
      <div>
        <h1>polygate</h1>
        <p>{tagline}</p>
      </div>
    </div>
  );
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="login-shell">
      <main className="login-card">{children}</main>
    </div>
  );
}

function StatusCard({ error, onRetry }: { error: string; onRetry: () => void }) {
  const { t } = useI18n();
  return (
    <Shell>
      <LoginBrand tagline={t("app.tagline")} />
      <div>
        <h2>{t("login.title")}</h2>
        <p className="muted">{error || t("login.checking")}</p>
        {error ? (
          <button className="ghost" onClick={onRetry}>
            <Icon name="refresh" size={16} />
            {t("login.retry")}
          </button>
        ) : null}
      </div>
    </Shell>
  );
}

function passwordProblem(password: string, confirm: string, setup: boolean, t: Translate): string {
  if (setup && password !== confirm) return t("login.passwordMismatch");
  if (password.length < 8) return t("login.passwordTooShort");
  return "";
}

async function requestToken(setup: boolean, password: string): Promise<string> {
  const result = setup ? await setupPassword(password) : await loginPassword(password);
  return result.token;
}

function PasswordFields({
  setup,
  password,
  confirm,
  onPassword,
  onConfirm,
}: {
  setup: boolean;
  password: string;
  confirm: string;
  onPassword: (value: string) => void;
  onConfirm: (value: string) => void;
}) {
  const { t } = useI18n();
  return (
    <>
      <label className="field">
        <span className="field-label">{t("login.passwordLabel")}</span>
        <input
          aria-label="admin-password"
          type="password"
          autoComplete={setup ? "new-password" : "current-password"}
          value={password}
          onChange={(event) => onPassword(event.target.value)}
          placeholder={t("login.passwordLabel")}
        />
      </label>
      {setup ? (
        <label className="field">
          <span className="field-label">{t("login.confirmLabel")}</span>
          <input
            aria-label="admin-password-confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => onConfirm(event.target.value)}
            placeholder={t("login.confirmLabel")}
          />
        </label>
      ) : null}
    </>
  );
}

function PasswordFeedback({ invalid, error }: { invalid: boolean; error: string }) {
  const { t } = useI18n();
  if (!invalid && !error) return null;
  return <span className="error">{error || t("login.invalid")}</span>;
}

function PasswordSubmit({ setup, busy, empty }: { setup: boolean; busy: boolean; empty: boolean }) {
  const { t } = useI18n();
  return (
    <button className="action" type="submit" disabled={busy || empty}>
      <Icon name="check" />
      {busy ? "…" : setup ? t("login.setupButton") : t("login.loginButton")}
    </button>
  );
}

function PasswordCard({
  configured,
  invalid,
  onSubmit,
}: {
  configured: boolean;
  invalid: boolean;
  onSubmit: (token: string) => void;
}) {
  const { t } = useI18n();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const setup = !configured;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const problem = passwordProblem(password, confirm, setup, t);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError("");
    try {
      onSubmit(await requestToken(setup, password));
    } catch {
      setError(t("login.invalid"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Shell>
      <form onSubmit={(event) => void submit(event)} style={{ display: "contents" }}>
        <LoginBrand tagline={t("app.tagline")} />
        <div>
          <h2>{setup ? t("login.setupTitle") : t("login.title")}</h2>
          <p className="muted">{setup ? t("login.setupDescription") : t("login.description")}</p>
        </div>
        <PasswordFields
          setup={setup}
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
        />
        <PasswordFeedback invalid={invalid} error={error} />
        <PasswordSubmit setup={setup} busy={busy} empty={password.length === 0} />
        <div className="login-foot">
          <span className="status-line">
            <span className="status-dot" />
            {t("login.local")}
          </span>
          <span className="pill mono">{t("login.endpoints")}</span>
        </div>
      </form>
    </Shell>
  );
}

/** Login form storing the admin session token. */
export function TokenGate({
  onSubmit,
  invalid = false,
  initialConfigured,
}: {
  onSubmit: (token: string) => void;
  invalid?: boolean;
  initialConfigured?: boolean;
}) {
  const { t } = useI18n();
  const [configured, setConfigured] = useState<boolean | undefined>(initialConfigured);
  const [error, setError] = useState("");

  const loadStatus = async () => {
    try {
      setConfigured((await fetchAuthStatus()).configured);
      setError("");
    } catch {
      setError(t("login.statusFailed"));
    }
  };

  useEffect(() => {
    // The async response, not the effect body, owns the state update.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (initialConfigured === undefined) void loadStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialConfigured]);

  if (configured === undefined) {
    return (
      <StatusCard
        error={error}
        onRetry={() => {
          setError("");
          void loadStatus();
        }}
      />
    );
  }
  return <PasswordCard configured={configured} invalid={invalid} onSubmit={onSubmit} />;
}
