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

/** 统一的接口错误：status=0 表示网络/超时。 */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function json<T>(url: string, init?: RequestInit, timeoutMs = 120_000): Promise<T> {
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { ...init, signal: ctrl.signal });
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      let detail = text;
      try {
        const parsed = JSON.parse(text) as { detail?: string };
        if (parsed.detail) detail = parsed.detail;
      } catch {
        /* 非 JSON 错误体，保留原文 */
      }
      throw new ApiError(r.status, detail || `HTTP ${r.status}`);
    }
    return (await r.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if ((e as Error).name === "AbortError") throw new ApiError(0, "请求超时，请重试");
    throw new ApiError(0, (e as Error).message || "网络错误");
  } finally {
    window.clearTimeout(timer);
  }
}

const post = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => json<{ status: string; db: boolean }>("/api/health", undefined, 10_000),
  settings: () => json<SettingsOut>("/api/settings", undefined, 10_000),
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
    json<ChatResp>("/api/chat", post({ messages, max_steps: maxSteps }), 240_000),
  evalSummary: () => json<EvalArm[]>("/api/eval/summary"),
};
