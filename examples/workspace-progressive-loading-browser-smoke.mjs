#!/usr/bin/env node
// A delayed or failed Goal must not hide the Workspace or its ready peers.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanupBrowserSmoke, launchBrowser, loadPlaywright, waitForHttp } from "./dashboard-browser-smoke-support.mjs";
const root = fileURLToPath(new URL("../", import.meta.url));
process.env.LOOPX_PLAYWRIGHT_PACKAGE ??= resolve(root, "apps/presentation/dashboard/node_modules/playwright");
const require = createRequire(import.meta.url);
const port = Number(process.env.LOOPX_PROGRESSIVE_PORT ?? "5204");
const origin = `http://127.0.0.1:${port}`;
const directory = { ok: true, schema_version: "loopx_workspace_directory_v1", registry_revision: "r1",
  goals: ["slow", "ready", "retry", "archived"].map((id) => ({ id, display_name: `${id} project`, activation_state: id === "archived" ? "stopped" : "active", registry_member: true })) };
function snapshot(id) {
  const payload = structuredClone(require(resolve(root, "examples/status.example.json")));
  payload.run_history.goals = [{ ...payload.run_history.goals[0], id, display_name: `${id} project`, activation_state: id === "archived" ? "stopped" : "active", registry_member: true }];
  for (const item of payload.attention_queue.items) item.goal_id = id;
  payload.workspace_registry_revision = directory.registry_revision;
  return payload;
}
const server = spawn(process.env.LOOPX_PYTHON_BIN ?? "python3", ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", resolve(root, "loopx/web")], { stdio: "ignore" });
let browser;
let releaseSlow;
const slowGate = new Promise((done) => { releaseSlow = done; });
try {
  await waitForHttp(`${origin}/chat/`);
  browser = process.env.LOOPX_PROGRESSIVE_ENGINE === "webkit"
    ? await loadPlaywright().webkit.launch({ headless: true })
    : process.platform === "win32" ? await loadPlaywright().chromium.launch({ headless: true })
    : await launchBrowser(loadPlaywright().chromium);
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let readyFailures = 1;
  let retryFails = true;
  let revisionMismatch = false;
  let active = 0;
  let peak = 0;
  const requested = [];
  await page.route("**/status.json*", async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("view") === "workspace-directory") {
      return route.fulfill({ json: directory });
    }
    const id = url.searchParams.get("goal_id");
    assert.ok(id, "supported server must not receive an aggregate status request");
    requested.push(id); active++; peak = Math.max(peak, active);
    if (id === "slow") await slowGate;
    active--;
    if (id === "ready" && readyFailures-- > 0) return route.fulfill({ status: 503, json: { ok: false } });
    return route.fulfill(id === "retry" && retryFails ? { status: 503, json: { ok: false } } : { json: revisionMismatch && id === "retry" ? { ...snapshot(id), workspace_registry_revision: "changed" } : snapshot(id) });
  });
  await page.route("**/api/**", (route) => route.fulfill({ status: 503, json: { ok: false } }));
  const start = Date.now();
  await page.goto(`${origin}/chat/?statusUrl=${encodeURIComponent(`${origin}/status.json`)}`);
  await page.locator('.personal-goal-link').filter({ hasText: "ready project" }).waitFor();
  const directoryMs = Date.now() - start;
  await page.locator('.personal-goal-link').filter({ hasText: "ready project" }).click();
  await page.waitForFunction(() => !document.querySelector('[data-testid="goal-status-loading"]'));
  assert.equal(await page.locator('.personal-goal-link').filter({ hasText: "slow project" }).innerText().then((s) => /加载|Loading/.test(s)), true);
  await page.locator('.personal-goal-link').filter({ hasText: "retry project" }).click();
  await page.getByTestId("goal-status-loading").getByRole("button").waitFor();
  assert.ok(requested.includes("retry"), "a blocked first Goal must not block the queue");
  assert.equal(requested.filter((id) => id === "retry").length, 3, "ordinary 5xx retains three attempts");
  const out = resolve(root, "output/playwright/workspace-progressive");
  await mkdir(out, { recursive: true });
  await page.screenshot({ path: resolve(out, "partial-desktop.png") });
  releaseSlow();
  await page.waitForFunction(() => [...document.querySelectorAll('.personal-goal-link')].find((el) => el.textContent.includes('slow project'))?.textContent.match(/加载|Loading/) === null);
  retryFails = false;
  revisionMismatch = true;
  const previousRequests = requested.length;
  await page.getByTestId("goal-status-loading").getByRole("button").click();
  while (requested.length === previousRequests) await new Promise((done) => setTimeout(done, 10));
  await page.getByTestId("goal-status-loading").getByRole("button").waitFor();
  revisionMismatch = false;
  await page.getByTestId("goal-status-loading").getByRole("button").click();
  await page.getByTestId("goal-status-loading").waitFor({ state: "hidden" });
  assert.ok(requested.filter((id) => id === "ready").length >= 2, "a transient service error should recover automatically");
  assert.ok(!requested.includes("archived"), "stopped history must not compete with the active first screen");
  await page.locator(".personal-stopped-goals summary").click();
  await Promise.all([
    page.waitForResponse((response) => response.url().includes("goal_id=archived")),
    page.locator('.personal-goal-link').filter({ hasText: "archived project" }).click(),
  ]);
  await page.getByTestId("goal-status-loading").waitFor({ state: "hidden" });
  assert.ok(requested.includes("archived"), "selected stopped Goal loads on demand");
  assert.ok(peak <= 2, `bounded fanout exceeded: ${peak}`);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: resolve(out, "ready-mobile.png") });
  assert.deepEqual(errors, []);
  for (const locale of ["zh-CN", "en"]) {
    const accessPage = await browser.newPage({ viewport: { width: 1440, height: 960 } });
    await accessPage.addInitScript((value) => localStorage.setItem("loopx-pw-locale", value), locale);
    accessPage.on("pageerror", (error) => errors.push(error.message));
    const accessDirectory = { ...directory, goals: ["ready", "access"].map((id) => ({
      id, display_name: `${id} project`, activation_state: "active", registry_member: true,
    })) };
    const counts = { ready: 0, access: 0 };
    let denied = true;
    await accessPage.route("**/status.json*", (route) => {
      const url = new URL(route.request().url());
      if (url.searchParams.has("view")) return route.fulfill({ json: accessDirectory });
      const id = url.searchParams.get("goal_id");
      assert.ok(id in counts);
      counts[id]++;
      return route.fulfill(id === "access" && denied
        ? { status: 500, json: { ok: false, error_code: "workspace_status_access_denied" } }
        : { json: snapshot(id) });
    });
    await accessPage.route("**/api/**", (route) => route.fulfill({ status: 503, json: { ok: false } }));
    await accessPage.goto(`${origin}/chat/?statusUrl=${encodeURIComponent(origin + "/status.json")}`);
    await accessPage.locator(".personal-goal-link").filter({ hasText: "ready project" }).click();
    await accessPage.getByTestId("goal-status-loading").waitFor({ state: "hidden" });
    await accessPage.locator(".personal-goal-link").filter({ hasText: "access project" }).click();
    const panel = accessPage.getByTestId("goal-status-loading");
    await panel.getByRole("button").waitFor();
    assert.match(await panel.innerText(), locale === "en" ? /account running that source/ : /来源运行账户/);
    await accessPage.screenshot({ path: resolve(out, `access-${locale}-desktop.png`) });
    await accessPage.setViewportSize({ width: 390, height: 844 });
    await accessPage.screenshot({ path: resolve(out, `access-${locale}-mobile.png`) });
    // Outwait the first backoff: terminal access failures must not retry themselves.
    await accessPage.waitForTimeout(1_200);
    assert.deepEqual(counts, { ready: 1, access: 1 });
    denied = false;
    await panel.getByRole("button").click();
    await panel.waitFor({ state: "hidden" });
    assert.deepEqual(counts, { ready: 1, access: 2 }, "manual retry preserves successful peers at the same revision");
    await accessPage.close();
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ ok: true, directory_ms: directoryMs, peak_concurrent_requests: peak, checks: ["directory-before-slow-goal", "ready-peer-usable", "queue-progress", "isolated-failure", "registry-revision-fence", "retry", "service-restart-recovery", "lazy-stopped-goals", "access-no-auto-retry", "access-manual-recovery-preserves-peers", "bilingual-access", "mobile", "no-render-errors"] }));
} finally {
  releaseSlow();
  await cleanupBrowserSmoke({ browser, server, fixturePaths: [] });
}
