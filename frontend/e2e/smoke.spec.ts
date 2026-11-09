import { expect, test } from "@playwright/test";

/**
 * 冒烟 e2e：覆盖主要页面渲染与关键交互。
 * 依赖后端 API（127.0.0.1:8000）与 MySQL；CI 里不跑（见 .github/workflows/ci.yml）。
 */

test("聊天页：标题、模型切换、输入框", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByText("ANCHORLINE")).toBeVisible();
  await expect(page.getByRole("button", { name: /发\s*送/ })).toBeVisible();
  await expect(page.locator(".composer textarea")).toBeVisible();
  // antd Segmented 的 radio input 是隐藏的，断言可见的 label 文本
  await expect(page.locator(".ant-segmented-item-label").filter({ hasText: "DeepSeek" })).toBeVisible();
});

test("记忆页：容量提示、环形图、分组", async ({ page }) => {
  await page.goto("/memory");
  await expect(page.getByText("记忆容量", { exact: false }).first()).toBeVisible();
  await expect(page.locator(".donut-wrap").first()).toBeVisible();
  await expect(page.locator(".ant-collapse").first()).toBeVisible();
});

test("评测页：臂对比 + LoreKeeper 桥接 Tab", async ({ page }) => {
  await page.goto("/eval");
  await expect(page.getByRole("tab", { name: "臂对比" })).toBeVisible();
  await page.getByRole("tab", { name: "LoreKeeper 桥接" }).click();
  await expect(page.getByText("LoreKeeper 数据集桥接", { exact: false })).toBeVisible();
});

test("审核页：待裁决 / 裁决历史", async ({ page }) => {
  await page.goto("/review");
  await expect(page.getByRole("tab", { name: /待裁决/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: /裁决历史/ })).toBeVisible();
});

test("监控页：统计卡片", async ({ page }) => {
  await page.goto("/monitor");
  await expect(page.getByText("系统监控")).toBeVisible();
  await expect(page.getByText("会话数", { exact: false })).toBeVisible();
});

test("设置页：主题色与日夜切换", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByText("夜间")).toBeVisible();
  await expect(page.getByText("恢复默认")).toBeVisible();
});
