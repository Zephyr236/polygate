/**
 * Chat playground that calls the live router.
 */

import { useState } from "react";

import type { ChatResult } from "@/api/types";
import { Icon } from "@/components/icons";
import { Panel } from "@/components/widgets";
import { useI18n } from "@/i18n";
import { tokens } from "@/utils/format";

/** Prompt form plus the rendered completion. */
export function Playground({
  onChat,
  result,
  pending,
  error,
}: {
  onChat: (input: { model: string; prompt: string; stream: boolean }) => void;
  result: ChatResult | undefined;
  pending: boolean;
  error: string | undefined;
}) {
  const { t } = useI18n();
  const [model, setModel] = useState("deepseek-v4.1-flash");
  const [prompt, setPrompt] = useState(t("playground.promptDefault"));
  const [stream, setStream] = useState(true);

  return (
    <div className="main">
      <div className="split-grid">
        <PromptForm
          labels={{
            title: t("playground.title"),
            model: t("playground.model"),
            prompt: t("playground.prompt"),
            stream: t("playground.stream"),
            send: t("playground.send"),
            running: t("playground.running"),
          }}
          model={model}
          prompt={prompt}
          stream={stream}
          pending={pending}
          error={error}
          onModel={setModel}
          onPrompt={setPrompt}
          onStream={setStream}
          onSend={() => onChat({ model, prompt, stream })}
        />
        {result ? (
          <Completion result={result} />
        ) : (
          <Panel title={t("playground.response")}>
            <div className="empty-state" style={{ minHeight: 180 }}>
              <strong>{t("playground.noTitle")}</strong>
              <span>{t("playground.noBody")}</span>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

/** Editable prompt form with the send action. */
function PromptForm(props: {
  labels: {
    title: string;
    model: string;
    prompt: string;
    stream: string;
    send: string;
    running: string;
  };
  model: string;
  prompt: string;
  stream: boolean;
  pending: boolean;
  error: string | undefined;
  onModel: (value: string) => void;
  onPrompt: (value: string) => void;
  onStream: (value: boolean) => void;
  onSend: () => void;
}) {
  return (
    <Panel title={props.labels.title}>
      <div style={{ display: "grid", gap: 12 }}>
        <label className="field">
          <span className="field-label">{props.labels.model}</span>
          <input
            aria-label="playground-model"
            value={props.model}
            onChange={(e) => props.onModel(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-label">{props.labels.prompt}</span>
          <textarea
            aria-label="playground-prompt"
            rows={4}
            value={props.prompt}
            onChange={(e) => props.onPrompt(e.target.value)}
          />
        </label>
        <label className="switch">
          <input
            aria-label="playground-stream"
            type="checkbox"
            checked={props.stream}
            onChange={(e) => props.onStream(e.target.checked)}
          />
          {props.labels.stream}
        </label>
        <button className="action" disabled={props.pending} onClick={props.onSend}>
          <Icon name="play" size={16} />
          {props.pending ? props.labels.running : props.labels.send}
        </button>
        {props.error ? <div className="error">{props.error}</div> : null}
      </div>
    </Panel>
  );
}

/** Rendered completion with usage details. */
function Completion({ result }: { result: ChatResult }) {
  const { t } = useI18n();
  return (
    <Panel title={t("playground.response")}>
      <pre className="mono" style={{ whiteSpace: "pre-wrap", margin: 0 }} data-testid="playground-output">
        {result.content}
      </pre>
      <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 10 }}>
        {t("playground.provider")} {result.provider || "—"} · {t("playground.promptTokens")}{" "}
        {tokens(result.promptTokens)} · {t("playground.completionTokens")} {tokens(result.completionTokens)} ·{" "}
        {t("playground.cachedTokens")} {tokens(result.cachedTokens)}
      </div>
    </Panel>
  );
}
