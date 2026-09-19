import { resolve } from "node:path";

import { outputDir } from "./fixture.mjs";
import { openWorkspacePage } from "./scenario-context.mjs";

export const loopxModeScenario = {
  id: "loopx-mode",
  async run({ browser, collectCoverage, url }) {
    const context = await openWorkspacePage(browser, url, { collectCoverage });
    const { api, page } = context;
    let releaseSnapshot;
    const heldSnapshot = new Promise(resolve => { releaseSnapshot = resolve; });
    let firstSnapshot = true;
    await page.route("**/api/chat/sessions/*/loopx", async route => {
      if (firstSnapshot && route.request().method() === "GET") {
        firstSnapshot = false;
        await heldSnapshot;
      }
      await route.fallback();
    });
    const snapshotRequested = page.waitForRequest(request => request.url().endsWith("/loopx"));
    try {
      await page.locator(".personal-goal-link", { hasText: "Product Release" }).click();
      await page.getByRole("navigation", { name: "Goal 视图" })
        .getByRole("button", { name: "对话", exact: true }).click();

      const enable = page.getByRole("button", { name: "开启 LoopX 模式", exact: true });
      await enable.waitFor({ state: "visible" });
      await snapshotRequested;
      await enable.click();
      releaseSnapshot();

      const settings = page.locator(".goal-loopx-mode-settings");
      await settings.waitFor({ state: "visible" });
      await settings.getByLabel("已注册的协调身份").selectOption("lead");
      await settings.getByLabel("协调员总 token 额度").fill("100000");
      const executionConfig = settings.getByLabel("成员执行绑定文件（Goal 配置）");
      if (await executionConfig.inputValue() !== ".loopx/config/delegations.json") {
        throw new Error("LoopX mode did not read the Goal-owned execution configuration");
      }
      if (await executionConfig.isEditable()) {
        throw new Error("LoopX mode must not edit the Goal-owned execution configuration");
      }
      await settings.getByRole("button", { name: "保存设置", exact: true }).click();
      await settings.waitFor({ state: "detached" });

      const request = api.loopxModeRequests.at(-1);
      if (request?.operation !== "configure"
        || request.settings?.agent_id !== "lead"
        || request.settings?.token_budget !== 100000
        || Object.hasOwn(request.settings ?? {}, "execution_config")) {
        throw new Error(`LoopX mode settings did not round-trip through the real frontend API: ${JSON.stringify(request)}`);
      }
      if (api.turnRequests.length) throw new Error("Configuring LoopX mode started work without explicit activation");
      await page.getByText("普通对话", { exact: true }).waitFor({ state: "visible" });
      await page.screenshot({ path: resolve(outputDir, "goal-loopx-mode-configured.png"), fullPage: false, animations: "disabled" });

      return {
        coverageEntries: await context.close(),
        note: "One enable click during a pending snapshot opens settings, reads Goal-owned bindings without resending them, and does not start work while configuring.",
      };
    } catch (error) {
      releaseSnapshot();
      await context.close();
      throw error;
    }
  },
};
