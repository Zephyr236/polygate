/**
 * Chat playground that calls the live router.
 */

import { useState } from "react";

import type { ChatResult } from "@/api/types";
import { Icon } from "@/components/icons";
import { Panel } from "@/components/widgets";
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
  const [model, setModel] = useState("deepseek-v4.1-flash");
  const [prompt, setPrompt] = useState("Reply with exactly: PONG");
  const [stream, setStream] = useState(true);

  return (
    <div className="main">
      <div className="split-grid">
        <PromptForm
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
          <Panel title="Response">
            <div className="empty-state" style={{ minHeight: 180 }}>
              <strong>No response yet</strong>
              <span>Send a prompt to exercise the live router and inspect usage.</span>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

/** Editable prompt form with the send action. */
function PromptForm(props: {
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
    <Panel title="Playground">
      <div style={{ display: "grid", gap: 12 }}>
        <label className="field">
          <span className="field-label">Model</span>
          <input
            aria-label="playground-model"
            value={props.model}
            onChange={(e) => props.onModel(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-label">Prompt</span>
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
          Stream responses
        </label>
        <button className="action" disabled={props.pending} onClick={props.onSend}>
          <Icon name="play" size={16} />
          {props.pending ? "Running…" : "Send"}
        </button>
        {props.error ? <div className="error">{props.error}</div> : null}
      </div>
    </Panel>
  );
}

/** Rendered completion with usage details. */
function Completion({ result }: { result: ChatResult }) {
  return (
    <Panel title="Response">
      <pre className="mono" style={{ whiteSpace: "pre-wrap", margin: 0 }} data-testid="playground-output">
        {result.content}
      </pre>
      <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 10 }}>
        provider {result.provider || "—"} · prompt {tokens(result.promptTokens)} · completion{" "}
        {tokens(result.completionTokens)} · cached {tokens(result.cachedTokens)}
      </div>
    </Panel>
  );
}
