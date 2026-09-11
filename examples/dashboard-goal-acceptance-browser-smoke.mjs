#!/usr/bin/env node
// The UI consumes a real collect_status result from a disposable synthetic Goal.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanupBrowserSmoke, launchBrowser, loadPlaywright, startViteDashboardServer, waitForHttp } from "./dashboard-browser-smoke-support.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const port = Number(process.env.LOOPX_GOAL_ACCEPTANCE_PORT ?? 5291);
const packaged = process.env.LOOPX_GOAL_ACCEPTANCE_PACKAGED === "1";
const python = process.env.LOOPX_PYTHON ?? "python3";
const payload = JSON.parse(execFileSync(python, ["-c", "import runpy,tempfile,json; from pathlib import Path; m=runpy.run_path('tests/control_plane/test_goal_artifact_lifecycle.py'); t=tempfile.TemporaryDirectory(); print(json.dumps(m['collect_fixture'](Path(t.name))))"], { cwd: root, encoding: "utf8" }));
const dashboardDir = resolve(root, "apps/presentation/dashboard");
const server = packaged
  ? spawn(python, ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", resolve(root, "loopx/web")], { stdio: "ignore" })
  : startViteDashboardServer({ dashboardDir, port });
let browser;
try {
  await waitForHttp(`http://127.0.0.1:${port}/`);
  browser = await launchBrowser(loadPlaywright().chromium);
  const output = resolve(root, "output/playwright/goal-acceptance");
  await mkdir(output, { recursive: true });
  for (const [language, viewport] of [["zh-CN", {width: 1440, height: 1000}], ["en", {width: 390, height: 844}]]) {
    const page = await browser.newPage({ viewport });
    await page.addInitScript((locale) => localStorage.setItem("loopx-pw-locale", locale), language);
    await page.route((url) => url.pathname === "/status.json", (route) => route.fulfill({ json: payload }));
    await page.route("**/api/**", (route) => route.fulfill({ status: 404, json: {error: "not available in read-only fixture"} }));
    await page.goto(`http://127.0.0.1:${port}/${packaged ? "chat/" : ""}?statusUrl=/status.json`, {waitUntil: "networkidle"});
    if (viewport.width < 640) {
      const sidebar = page.getByRole("button", {name: language === "en" ? "Open Goal navigation" : "打开 Goal 导航"});
      if (await sidebar.isVisible()) await sidebar.click();
    }
    await page.locator(".personal-goal-link").first().click({timeout: 10000});
    await page.getByRole("button", {name: language === "en" ? "Open Goal details or capability settings" : "打开 Goal 详情或能力配置"}).click();
    await page.getByRole("group", {name: language === "en" ? "Goal settings" : "Goal 设置"}).getByRole("button", {name: /Goal details|Goal 详情/}).click();
    const card = page.locator(".personal-goal-acceptance");
    await card.getByText("Independent verification report", {exact: true}).waitFor();
    assert.match(await card.innerText(), /agent-a/);
    assert.match(await card.innerText(), language === "en" ? /do not prove Goal acceptance/ : /不能证明 Goal 已通过验收/);
    await card.locator("summary").click();
    await card.scrollIntoViewIfNeeded();
    assert.equal(await card.evaluate(el => el.scrollWidth > el.clientWidth + 2), false, "Acceptance content must wrap on mobile");
    await page.screenshot({path: resolve(output, `${packaged ? "packaged" : "development"}-${language}.png`)});
    if (language === "en") {
      delete payload.run_history.goals[0].artifact_lifecycle;
      await page.reload({waitUntil: "networkidle"});
      const navigation = page.getByRole("button", {name: "Open Goal navigation"});
      if (await navigation.isVisible()) await navigation.click();
      await page.locator(".personal-goal-link").first().click();
      await page.getByRole("button", {name: "Open Goal details or capability settings"}).click();
      await page.getByRole("group", {name: "Goal settings"}).getByRole("button", {name: /Goal details/}).click();
      await page.locator(".personal-goal-acceptance").getByText("Acceptance observations are unavailable. Goal completion is unknown.", {exact: true}).waitFor();
      assert.equal(await page.locator(".personal-goal-acceptance .personal-acceptance-observation").count(), 0, "Unavailable source cannot retain prior gap rows");
    }
    await page.close();
  }
  console.log(`goal acceptance browser (${packaged ? "packaged" : "development"}): passed`);
} finally {
  await cleanupBrowserSmoke({ browser, server, fixturePaths: [] });
}
