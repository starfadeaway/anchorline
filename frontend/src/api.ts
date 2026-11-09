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
  session_id: string | null;
  meta?: {
    model?: string;
    duration_ms?: number | null;
    total_tokens?: number | null;
    tool_errors?: number;
    run_id?: string;
  };
};

export type ChatSession = {
  id: string;
  title: string;
  topic?: string | null;
  created_at: string;
  message_count: number;
};

export type SessionMessage = {
  id: number;
  role: string;
  content: string;
  created_at: string;
};

export type TraceRow = {
  id: number;
  query: string;
  layers: string;
  used_tokens: number;
  resolution: string | null;
  injected_fact_ids: string | null;
  created_at: string;
  steps?: number;
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
  minimax_model: string;
  minimax_base_url: string;
  chat_models: string[];
};

export type Capacity = {
  limit: number;
  total_current: number;
  entities: { entity_id: string; current: number; stale: number }[];
};

export type Msg = { role: "user" | "assistant"; content: string; created_at?: string };

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

/** 前端导出 Markdown（浏览器下载）。 */
export function downloadMarkdown(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  health: () => json<{ status: string; db: boolean }>("/api/health", undefined, 10_000),
  settings: () => json<SettingsOut>("/api/settings", undefined, 10_000),
  facts: (limit = 200) => json<Fact[]>(`/api/memory/facts?limit=${limit}`),
  history: (id: string) => json<Fact[]>(`/api/memory/facts/${id}/history`),
  writeFact: (body: { entity_id: string; attribute: string; value: string; valid_from?: string }) =>
    json<{ fact_id: string; supersedes: string | null; archived?: number }>("/api/memory/write", post(body)),
  capacity: () => json<Capacity>("/api/memory/capacity"),
  forget: (body: { entity_id: string; attribute: string; at?: string }) =>
    json<{ fact_id: string }>("/api/memory/forget", post(body)),
  invalidate: (id: string) => json<{ fact_id: string }>(`/api/memory/facts/${id}/invalidate`, post({})),
  patchFact: (id: string, body: { value?: string; confidence?: number }) =>
    json<{ fact_id: string }>(`/api/memory/facts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  chat: (messages: Msg[], opts?: { model?: string; sessionId?: string | null }) =>
    json<ChatResp>(
      "/api/chat",
      post({
        messages,
        max_steps: 6,
        model: opts?.model ?? "deepseek",
        session_id: opts?.sessionId ?? null,
      }),
      240_000,
    ),
  listSessions: () => json<ChatSession[]>("/api/sessions"),
  createSession: () => json<{ id: string }>("/api/sessions", post({})),
  sessionMessages: (id: string) => json<SessionMessage[]>(`/api/sessions/${id}/messages`),
  deleteFact: (id: string) => json<{ deleted: string }>(`/api/memory/facts/${id}`, { method: "DELETE" }),
  purgeStaleFacts: () => json<{ deleted: number }>("/api/memory/facts", { method: "DELETE" }),
  reviewConflicts: () =>
    json<{ entity_id: string; facts: { id: string; attribute: string; value: string; valid_from: string; confidence: number }[] }[]>(
      "/api/review/conflicts",
    ),
  sessionTraces: (id: string) => json<TraceRow[]>(`/api/sessions/${id}/traces`),
  deleteSession: (id: string) => json<{ deleted: string }>(`/api/sessions/${id}`, { method: "DELETE" }),
  evalSummary: () => json<EvalArm[]>("/api/eval/summary"),
};
