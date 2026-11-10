import { expect, test } from "@playwright/test";

/**
 * 聊天页端到端：发送消息 + SSE 打字机。
 * 用 route 拦截 /api/chat/stream 返回固定 SSE，不依赖真实模型 key（CI 可跑）。
 */

const SSE = [
  'event: token\ndata: {"text":"你好"}\n\n',
  'event: token\ndata: {"text":"，世界"}\n\n',
  'event: final\ndata: {"answer":"你好，世界","stop_reason":"done","steps":0,"trace_id":null,"session_id":null,"tool_calls":[],"meta":{"model":"deepseek","duration_ms":12,"total_tokens":8,"tool_errors":0,"run_id":""}}\n\n',
].join("");

test("聊天页：发送消息后逐块渲染（SSE 打字机）", async ({ page }) => {
  await page.route("**/api/chat/stream", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: SSE,
    }),
  );

  await page.goto("/chat");
  const box = page.locator(".composer textarea");
  await box.fill("测试一条消息");
  await page.getByRole("button", { name: /发\s*送/ }).click();

  // 用户消息立即出现
  await expect(page.getByText("测试一条消息")).toBeVisible();
  // 助手消息由 token 事件拼出
  await expect(page.getByText("你好，世界")).toBeVisible();
});

test("聊天页：流失败时回退 /chat 并报错不崩", async ({ page }) => {
  await page.route("**/api/chat/stream", (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"boom"}' }),
  );
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "回退成功",
        stop_reason: "done",
        steps: 0,
        tool_calls: [],
        trace_id: null,
        session_id: null,
      }),
    }),
  );

  await page.goto("/chat");
  await page.locator(".composer textarea").fill("触发回退");
  await page.getByRole("button", { name: /发\s*送/ }).click();
  await expect(page.getByText("回退成功")).toBeVisible();
});
