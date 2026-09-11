#!/usr/bin/env node
// Regression smoke for local/SSH status-source request ordering.

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  cleanupBrowserSmoke,
  launchBrowser,
  loadPlaywright,
  startViteDashboardServer,
  waitForHttp,
} from "./dashboard-browser-smoke-support.mjs";

const require = createRequire(import.meta.url);
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/presentation/dashboard");
const outputDir = resolve(repoRoot, "output/playwright/status-source-switch");
const port = Number(process.env.LOOPX_STATUS_SOURCE_SWITCH_PORT ?? "5197");
const packaged = process.env.LOOPX_STATUS_SOURCE_SWITCH_PACKAGED === "1";

function startServer() {
  if (packaged) {
    return spawn(process.env.LOOPX_PYTHON_BIN || "python3", [
      "-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", resolve(repoRoot, "loopx/web"),
    ], {
      cwd: repoRoot,
      env: { ...process.env },
      stdio: "ignore",
    });
  }
  return startViteDashboardServer({ dashboardDir, port });
}

function statusPayload(goalId, displayName) {
  const payload = structuredClone(require(resolve(repoRoot, "examples/status.example.json")));
  const goal = payload.run_history.goals[0];
  goal.id = goalId;
  goal.display_name = displayName;
  for (const item of payload.attention_queue.items ?? []) {
    item.goal_id = goalId;
    for (const todo of item.agent_todos?.items ?? []) todo.goal_id = goalId;
    for (const todo of item.user_todos?.items ?? []) todo.goal_id = goalId;
  }
  return payload;
}

function deferred() {
  let resolvePromise;
  const promise = new Promise((resolveDeferred) => { resolvePromise = resolveDeferred; });
  return { promise, resolve: resolvePromise };
}

async function selectedSourceLabel(select) {
  return select.locator(".personal-select-value").innerText();
}

async function selectSource(page, select, label) {
  await select.click();
  await page.getByRole("listbox", { name: "选择控制面来源" }).getByRole("option", { name: label, exact: true }).click();
}

async function main() {
  const { chromium } = loadPlaywright();
  await mkdir(outputDir, { recursive: true });
  const server = startServer();
  let browser;
  try {
    const appUrl = `http://127.0.0.1:${port}/${packaged ? "chat/" : ""}`;
    await waitForHttp(appUrl);
    browser = await launchBrowser(chromium);
    const page = await browser.newPage({ viewport: { width: 1512, height: 982 } });
    const state = {
      ensureGates: new Map(),
      ensureStartedByHost: new Map(),
      pauseWrites: [],
      statusGates: new Map(),
      statusRequestsByPort: new Map(),
      statusStartedByPort: new Map(),
    };
    const payloads = new Map([
      ["local", statusPayload("local-goal", "Local Goal Only")],
      ["8766", statusPayload("local-goal", "Local Goal Only")],
      ["8876", statusPayload("remote-a-goal", "Remote A Goal Only")],
      ["8976", statusPayload("remote-b-goal", "Remote B Goal Only")],
    ]);

    await page.addInitScript(() => {
      localStorage.setItem("loopx-status-source-catalog-v1", JSON.stringify({
        schemaVersion: 1,
        sources: [
          { kind: "ssh_tunnel", label: "Remote-A", statusUrl: "http://127.0.0.1:8876/status.json" },
          { kind: "ssh_tunnel", label: "Remote-B", statusUrl: "http://127.0.0.1:8976/status.json" },
        ],
      }));
    });
    await page.route(`http://127.0.0.1:${port}/ssh-hosts`, (route) => route.fulfill({
      contentType: "application/json",
      json: { ok: true, schema_version: "ssh_host_catalog_v0", hosts: [{ alias: "Remote-A" }, { alias: "Remote-B" }] },
      status: 200,
    }));
    await page.route(`http://127.0.0.1:${port}/api/ssh-source/ensure`, async (route) => {
      const body = route.request().postDataJSON();
      const host = String(body.host_alias ?? "");
      state.ensureStartedByHost.get(host)?.();
      await state.ensureGates.get(host);
      await route.fulfill({
        contentType: "application/json",
        json: { managed_by_loopx: true, ok: true, remote_started: true, status_url: `http://127.0.0.1:${body.local_port}/status.json`, tunnel_required: true },
        status: 200,
      });
    });
    await page.route(`http://127.0.0.1:${port}/api/ssh-source/pause`, async (route) => {
      const body = route.request().postDataJSON();
      state.pauseWrites.push(body);
      await route.fulfill({
        contentType: "application/json",
        json: { already_paused: false, ok: true, status_url: `http://127.0.0.1:${body.local_port}/status.json`, stopped: true },
        status: 200,
      });
    });
    const installStatusRoute = async (url, key) => {
      await page.route(`${url}*`, async (route) => {
        state.statusRequestsByPort.set(key, (state.statusRequestsByPort.get(key) ?? 0) + 1);
        state.statusStartedByPort.get(key)?.();
        await state.statusGates.get(key);
        await route.fulfill({ contentType: "application/json", json: payloads.get(key), status: 200 });
      });
    };
    await installStatusRoute(`http://127.0.0.1:${port}/status.json`, "local");
    await installStatusRoute("http://127.0.0.1:8766/status.json", "8766");
    await installStatusRoute("http://127.0.0.1:8876/status.json", "8876");
    await installStatusRoute("http://127.0.0.1:8976/status.json", "8976");

    await page.goto(appUrl, { waitUntil: "networkidle" });
    await page.getByText("Local Goal Only", { exact: true }).first().waitFor({ state: "visible", timeout: 10_000 });
    if ((state.statusRequestsByPort.get("local") ?? 0) === 0) throw new Error("The bare Dashboard did not request its same-origin /status.json source");
    if ((state.statusRequestsByPort.get("8766") ?? 0) !== 0) throw new Error("The bare Dashboard bypassed the Vite proxy and requested browser-local port 8766");
    const sourceSelect = page.getByRole("combobox", { name: "选择控制面来源" });

    const remoteAStatusGate = deferred();
    const remoteAStatusStarted = deferred();
    state.statusGates.set("8876", remoteAStatusGate.promise);
    state.statusStartedByPort.set("8876", remoteAStatusStarted.resolve);
    await selectSource(page, sourceSelect, "Remote-A");
    await remoteAStatusStarted.promise;
    await selectSource(page, sourceSelect, "Remote-B");
    await page.getByText("Remote B Goal Only", { exact: true }).first().waitFor({ state: "visible", timeout: 10_000 });
    const remoteAResponse = page.waitForResponse(
      (response) => response.url().startsWith("http://127.0.0.1:8876/status.json"),
    );
    remoteAStatusGate.resolve();
    await remoteAResponse;
    await page.evaluate(() => new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame))));
    if (await selectedSourceLabel(sourceSelect) !== "Remote-B") throw new Error("A stale status response moved the source selector away from Remote B");
    if (await page.getByText("Remote A Goal Only", { exact: true }).count()) throw new Error("A stale Remote A payload replaced Remote B goals");
    if (!new URL(page.url()).searchParams.get("statusUrl")?.includes("8976")) throw new Error(`The route did not retain Remote B: ${page.url()}`);

    state.statusGates.delete("8876");
    state.statusRequestsByPort.set("8876", 0);
    const remoteAEnsureGate = deferred();
    const remoteAEnsureStarted = deferred();
    state.ensureGates.set("Remote-A", remoteAEnsureGate.promise);
    state.ensureStartedByHost.set("Remote-A", remoteAEnsureStarted.resolve);
    await selectSource(page, sourceSelect, "Remote-A");
    await remoteAEnsureStarted.promise;
    await selectSource(page, sourceSelect, "本机");
    await page.getByText("Local Goal Only", { exact: true }).first().waitFor({ state: "visible", timeout: 10_000 });
    const remoteAEnsureResponse = page.waitForResponse((response) => response.url().endsWith("/api/ssh-source/ensure"));
    remoteAEnsureGate.resolve();
    await remoteAEnsureResponse;
    await page.evaluate(() => new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame))));
    if (await selectedSourceLabel(sourceSelect) !== "本机") throw new Error("A late SSH ensure completion overrode the newer local selection");
    if ((state.statusRequestsByPort.get("8876") ?? 0) !== 0) throw new Error("A superseded SSH selection still started its status request");
    if (await page.getByText("Remote A Goal Only", { exact: true }).count()) throw new Error("A superseded SSH selection replaced local goals");

    await selectSource(page, sourceSelect, "Remote-B");
    await page.getByText("Remote B Goal Only", { exact: true }).first().waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("button", { name: "暂停远端来源 Remote-B" }).click();
    await page.getByText("Local Goal Only", { exact: true }).first().waitFor({ state: "visible", timeout: 10_000 });
    if (await selectedSourceLabel(sourceSelect) !== "本机") throw new Error("Pausing an active SSH source did not return to the local control plane");
    if (JSON.stringify(state.pauseWrites) !== JSON.stringify([{ host_alias: "Remote-B", local_port: 8976 }])) throw new Error(`Pause did not target the exact managed tunnel: ${JSON.stringify(state.pauseWrites)}`);
    const persistedSources = JSON.parse(await page.evaluate(() => localStorage.getItem("loopx-status-source-catalog-v1"))).sources;
    if (!persistedSources.some((source) => source.hostAlias === "Remote-B")) throw new Error("Pausing removed the reusable SSH source from the catalog");
    await page.screenshot({ path: resolve(outputDir, "local-after-races.png"), fullPage: false, animations: "disabled" });
    console.log(`status source switch browser smoke (${packaged ? "packaged" : "development"}): ok`);
  } finally {
    await cleanupBrowserSmoke({ browser, fixturePaths: [], server });
  }
}

await main();
