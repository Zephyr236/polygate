/**
 * Routing simulation view: score breakdowns and eligibility reasons.
 */

import { useState } from "react";

import type { SimulateResponse } from "@/api/types";
import { Panel, ReasonList } from "@/components/widgets";

/** Simulate the router and render each candidate's score components. */
export function Routes({
  onSimulate,
  data,
  pending,
}: {
  onSimulate: (input: { model: string; prompt: string }) => void;
  data: SimulateResponse | undefined;
  pending: boolean;
}) {
  const [model, setModel] = useState("deepseek-v4.1-flash");
  const [prompt, setPrompt] = useState("hello");

  return (
    <div className="main">
      <Panel title="Simulate routing">
        <div style={{ display: "grid", gap: 12 }}>
          <label>
            Model
            <input
              aria-label="simulate-model"
              value={model}
              onChange={(event) => setModel(event.target.value)}
            />
          </label>
          <label>
            Prompt
            <textarea
              aria-label="simulate-prompt"
              rows={3}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
            />
          </label>
          <button className="action" disabled={pending} onClick={() => onSimulate({ model, prompt })}>
            {pending ? "Simulating…" : "Simulate"}
          </button>
        </div>
      </Panel>
      {data ? <CandidateTable data={data} /> : null}
    </div>
  );
}

/** Candidate score table with eligibility reasons. */
function CandidateTable({ data }: { data: SimulateResponse }) {
  return (
    <Panel title="Candidates">
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Priority</th>
            <th>Success</th>
            <th>Speed</th>
            <th>Cost</th>
            <th>Cache</th>
            <th>Total</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {data.ranking.map((row) => (
            <tr key={row.provider_id}>
              <td>{row.provider_id}</td>
              <td>{row.priority}</td>
              <td>{row.success.toFixed(3)}</td>
              <td>{row.speed.toFixed(3)}</td>
              <td>{row.cost.toFixed(3)}</td>
              <td>{row.cache.toFixed(3)}</td>
              <td>{row.total.toFixed(3)}</td>
              <td>
                <ReasonList reasons={reasonsFor(data, row.provider_id)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

/** Eligible reasons for one provider from the simulation payload. */
function reasonsFor(data: SimulateResponse, providerId: string): string[] {
  return data.decisions.find((item) => item.provider_id === providerId)?.reasons ?? [];
}
