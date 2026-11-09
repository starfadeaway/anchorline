export type Fact = {
  id: string;
  entity_id: string;
  attribute: string;
  value: string;
  valid_from: string;
  valid_to: string | null;
  confidence: number;
  supersedes_id: string | null;
  fact_type: string;
  conflict_type: string | null;
};

export type ToolCall = { name: string; arguments: string };

export type ChatResp = {
  answer: string;
  stop_reason: string;
  steps: number;
  tool_calls: ToolCall[];
  trace_id: number | null;
};

export type EvalArm = {
  arm: string;
  accuracy: number;
  n: number;
  source: string;
  note?: string;
};

export type SettingsOut = {
  version: string;
  db_ok: boolean;
  reader_model: string;
  judge_model: string;
  embedding_model: string;
  rerank_model: string;
  budgets: number[];
};

export type Msg = { role: "user" | "assistant"; content: string };

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return (await r.json()) as T;
}

const post = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => json<{ status: string; db: boolean }>("/api/health"),
  settings: () => json<SettingsOut>("/api/settings"),
  facts: (limit = 100) => json<Fact[]>(`/api/memory/facts?limit=${limit}`),
  history: (id: string) => json<Fact[]>(`/api/memory/facts/${id}/history`),
  writeFact: (body: { entity_id: string; attribute: string; value: string; valid_from?: string }) =>
    json<{ fact_id: string; supersedes: string | null }>("/api/memory/write", post(body)),
  forget: (body: { entity_id: string; attribute: string; at?: string }) =>
    json<{ fact_id: string }>("/api/memory/forget", post(body)),
  invalidate: (id: string) => json<{ fact_id: string }>(`/api/memory/facts/${id}/invalidate`, post({})),
  patchFact: (id: string, body: { value?: string; confidence?: number }) =>
    json<{ fact_id: string }>(`/api/memory/facts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  chat: (messages: Msg[], maxSteps = 6) =>
    json<ChatResp>("/api/chat", post({ messages, max_steps: maxSteps })),
  evalSummary: () => json<EvalArm[]>("/api/eval/summary"),
};
