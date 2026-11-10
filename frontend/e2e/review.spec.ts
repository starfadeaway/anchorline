import { expect, test } from "@playwright/test";

/**
 * 审核裁决端到端：选择保留 → 填原因 → 裁决 → 请求体正确。
 * 拦截 review/conflicts 与 decisions，不依赖 DB 里真有冲突；POST 也拦截并断言 payload。
 */

const CONFLICTS = [
  {
    entity_id: "user:e2e",
    facts: [
      { id: "f1", attribute: "5k_pb", value: "23:50", valid_from: "2023-05-30T00:00:00", confidence: 1 },
      { id: "f2", attribute: "5k_pb", value: "25:50", valid_from: "2023-01-01T00:00:00", confidence: 0.9 },
    ],
  },
];

test("审核页：选保留 + 原因 → 裁决请求体正确", async ({ page }) => {
  let decisionBody: Record<string, unknown> | null = null;

  await page.route("**/api/review/conflicts", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(CONFLICTS) }),
  );
  await page.route("**/api/review/decisions", async (route) => {
    if (route.request().method() === "POST") {
      decisionBody = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "d1",
          entity_id: "user:e2e",
          attribute: "5k_pb",
          kept_fact_id: "f1",
          invalidated_fact_ids: ["f2"],
          reason: "e2e",
          operator: "human",
          created_at: new Date().toISOString(),
        }),
      });
    } else {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    }
  });

  await page.goto("/review");
  // 冲突组渲染
  await expect(page.getByText("user:e2e")).toBeVisible();
  // 选第一行保留
  await page.locator(".ant-radio-input").first().check();
  await page.getByPlaceholder("裁决原因（可选）").fill("e2e reason");
  await page.getByRole("button", { name: /裁决：保留选中/ }).click();

  // 等请求发出并断言 payload
  await expect.poll(() => decisionBody).not.toBeNull();
  expect(decisionBody?.kept_fact_id).toBe("f1");
  expect(decisionBody?.invalidated_fact_ids).toEqual(["f2"]);
  expect(decisionBody?.reason).toBe("e2e reason");
});
