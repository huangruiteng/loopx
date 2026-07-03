#!/usr/bin/env node
// Browser-level smoke for the ops Promotion Readiness panel.

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/dashboard");
const publicDir = resolve(dashboardDir, "public");
const freshFixtureName = "status.promotion-readiness-fresh.json";
const staleFixtureName = "status.promotion-readiness-stale.json";
const missingFixtureName = "status.promotion-readiness-missing.json";
const freshFixturePath = resolve(publicDir, freshFixtureName);
const staleFixturePath = resolve(publicDir, staleFixtureName);
const missingFixturePath = resolve(publicDir, missingFixtureName);
const port = Number(process.env.LOOPX_DASHBOARD_PROMOTION_READINESS_SMOKE_PORT ?? "5196");

const quotaEligible = {
  compute: 1,
  window_hours: 24,
  slot_minutes: 1,
  allowed_slots: 1440,
  spent_slots: 18,
  state: "eligible",
  reason: "fixture eligible quota",
};

function baseStatusFixture(promotionReadinessSummary) {
  const shouldWarn = Boolean(promotionReadinessSummary?.requires_readiness_run);
  const promotionGate = {
    ok: true,
    registry: "./fixtures/registry.global.json",
    runtime_root: "./fixtures/runtime",
    gate: "promotion_readiness",
    gate_state: shouldWarn ? "warning" : "ready",
    can_promote: !shouldWarn,
    should_warn: shouldWarn,
    non_blocking: true,
    recommended_action: shouldWarn
      ? "python3 examples/canary/canary-promotion-readiness-smoke.py"
      : "promotion readiness is fresh",
    readiness: promotionReadinessSummary,
  };
  if (shouldWarn) {
    promotionGate.warning_message = `promotion-readiness evidence is ${promotionReadinessSummary.freshness_status}; fixture guard`;
  }
  return {
    ok: true,
    registry: "./fixtures/registry.global.json",
    runtime_root: "./fixtures/runtime",
    goal_count: 1,
    run_count: 1,
    status_contract: {
      schema_version: 2,
      minimum_dashboard_schema_version: 2,
      producer: "loopx status",
      reload_hint: "scripts/macos-dashboard-launchagent.sh restart",
    },
    contract: {
      ok: true,
      summary: { errors: 0, warnings: 0, checks: 1 },
      errors: [],
      warnings: [],
      checks: ["public-safe promotion readiness fixture"],
    },
    global_registry: {
      available: true,
      ok: true,
      registry: "./fixtures/registry.global.json",
      current_registry: "./fixtures/registry.global.json",
      current_registry_is_global: true,
      global_goal_count: 1,
      current_goal_count: 1,
      source_registry_count: 1,
      summary: { high: 0, action: 0, info: 0, checks: 1, findings: 0 },
      findings: [],
      checks: ["public-safe promotion readiness fixture"],
    },
    attention_queue: {
      available: true,
      item_count: 1,
      needs_user_or_controller: 0,
      needs_controller: 0,
      needs_codex: 1,
      watching_external_evidence: 0,
      autonomous_backlog_candidates: null,
      items: [
        {
          goal_id: "loopx-meta",
          status: "promotion_readiness_ops_panel_fixture",
          waiting_on: "codex",
          severity: "action",
          recommended_action: "continue fixture product-hardening validation",
          project_asset: {
            owner: "codex",
            gate: "none",
            next_action: "continue fixture product-hardening validation",
            stop_condition: "fixture stop condition",
            user_todos: { open: 0, done: 1, total: 1, next: null },
            agent_todos: { open: 1, done: 0, total: 1, next: "validate promotion readiness panel" },
            quota: quotaEligible,
            latest_validation: {
              generated_at: "2026-01-01T00:00:00+00:00",
              classification: "promotion_readiness_ops_panel_fixture",
              summary: "fixture validation",
            },
          },
          handoff_readiness: {
            ready: true,
            codex_ready: true,
            source: "project_asset",
            quota_state: "eligible",
          },
          quota: quotaEligible,
          user_todos: {
            source_section: "User Todo / Owner Review Reading Queue",
            total_count: 1,
            open_count: 0,
            done_count: 1,
            items: [{ index: 1, done: true, text: "fixture user gate clear", review_materials: [] }],
          },
          agent_todos: {
            source_section: "Agent Todo",
            total_count: 1,
            open_count: 1,
            done_count: 0,
            items: [{ index: 1, done: false, text: "validate promotion readiness panel", review_materials: [] }],
          },
          dependency_blockers: null,
          source: "fixture",
        },
      ],
    },
    run_history: {
      available: true,
      goal_count: 1,
      run_count: 1,
      goals: [
        {
          id: "loopx-meta",
          domain: "loopx-fixture",
          status: "promotion_readiness_ops_panel_fixture",
          lifecycle_phase: "fixture",
          lifecycle_flags: ["fixture"],
          registry_member: true,
          legacy_runtime_goal: false,
          adapter_kind: "dashboard_ops_fixture",
          adapter_status: "connected",
          quota: quotaEligible,
          index_exists: true,
          raw_index_records: 1,
          unique_runs: 1,
          latest_runs: [
            {
              goal_id: "loopx-meta",
              generated_at: "2026-01-01T00:00:00+00:00",
              classification: "promotion_readiness_ops_panel_fixture",
              delivery_batch_scale: "multi_surface",
              delivery_outcome: "primary_goal_outcome",
              health_check: "fixture validation",
              json_exists: true,
              markdown_exists: true,
            },
          ],
        },
      ],
      recent_runs: [
        {
          goal_id: "loopx-meta",
          generated_at: "2026-01-01T00:00:00+00:00",
          classification: "promotion_readiness_ops_panel_fixture",
          delivery_batch_scale: "multi_surface",
          delivery_outcome: "primary_goal_outcome",
          health_check: "fixture validation",
          json_exists: true,
          markdown_exists: true,
        },
      ],
    },
    usage_summary: null,
    event_ledger_summary: null,
    decision_freshness_summary: null,
    promotion_readiness_summary: promotionReadinessSummary,
    promotion_gate: promotionGate,
  };
}

const freshPromotionReadinessSummary = {
  available: true,
  source: "run_history",
  goal_id: "loopx-meta",
  generated_at: "2026-01-01T00:00:00+00:00",
  classification: "canary_promotion_readiness_smoke_group",
  delivery_batch_scale: "multi_surface",
  delivery_outcome: "primary_goal_outcome",
  recommended_action: "fixture fresh promotion readiness",
  json_exists: true,
  markdown_exists: true,
  freshness_window_hours: 24,
  freshness_status: "fresh",
  is_fresh: true,
  requires_readiness_run: false,
  age_seconds: 900,
  age_hours: 0.25,
  sample_run_count: 1,
  proxy_note: "fresh promotion readiness fixture",
};

const stalePromotionReadinessSummary = {
  ...freshPromotionReadinessSummary,
  freshness_status: "stale",
  is_fresh: false,
  requires_readiness_run: true,
  age_seconds: 91_800,
  age_hours: 25.5,
  proxy_note: "stale promotion readiness fixture",
};

const missingPromotionReadinessSummary = {
  available: false,
  source: "run_history",
  reason: "no canary promotion readiness run found in sampled history",
  freshness_window_hours: 24,
  freshness_status: "missing",
  is_fresh: false,
  requires_readiness_run: true,
  age_seconds: null,
  age_hours: null,
  sample_run_count: 0,
  proxy_note: "missing promotion readiness fixture",
};

function loadPlaywright() {
  const candidates = [
    process.env.LOOPX_PLAYWRIGHT_PACKAGE,
    resolve(homedir(), ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"),
  ].filter(Boolean);

  try {
    return require("playwright");
  } catch {
    // Try explicit or bundled local packages below.
  }

  for (const candidate of candidates) {
    if (!candidate || !existsSync(candidate)) {
      continue;
    }
    try {
      return require(candidate);
    } catch {
      // Keep looking.
    }
  }

  throw new Error("Playwright package not found; install playwright or set LOOPX_PLAYWRIGHT_PACKAGE");
}

async function launchBrowser(chromium) {
  try {
    return await chromium.launch({ channel: "chrome", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

async function waitForDashboard(url) {
  const deadline = Date.now() + 20_000;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveTimeout) => setTimeout(resolveTimeout, 250));
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
}

function startDashboardServer() {
  const viteBin = resolve(dashboardDir, "node_modules/vite/bin/vite.js");
  if (!existsSync(viteBin)) {
    throw new Error(`Vite package not installed: ${viteBin}`);
  }
  const nodeBin = [
    process.env.LOOPX_NODE_BIN,
    "/opt/homebrew/bin/node",
    "/usr/local/bin/node",
    process.execPath,
  ].find((candidate) => candidate && existsSync(candidate));
  return spawn(nodeBin, [viteBin, "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
    cwd: dashboardDir,
    env: {
      ...process.env,
      PATH: ["/opt/homebrew/bin", "/usr/local/bin", process.env.PATH].filter(Boolean).join(":"),
    },
    stdio: "ignore",
  });
}

function assertIncludes(body, expected, label) {
  const missing = expected.filter((text) => !body.includes(text));
  if (missing.length) {
    throw new Error(`Missing ${label} text: ${missing.join(", ")}`);
  }
}

function assertExcludes(body, forbidden, label) {
  const present = forbidden.filter((text) => body.includes(text));
  if (present.length) {
    throw new Error(`Unexpected ${label} text: ${present.join(", ")}`);
  }
}

async function assertPromotionPage(page, baseUrl, fixtureName, expected, forbidden) {
  const statusUrl = encodeURIComponent(`${baseUrl}/${fixtureName}`);
  await page.goto(`${baseUrl}/?view=ops&statusUrl=${statusUrl}`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=Promotion readiness", { timeout: 10_000 });
  const body = await page.locator("body").innerText();
  assertIncludes(body, expected, fixtureName);
  assertExcludes(body, forbidden, fixtureName);
}

async function main() {
  const { chromium } = loadPlaywright();
  await writeFile(freshFixturePath, JSON.stringify(baseStatusFixture(freshPromotionReadinessSummary), null, 2) + "\n", "utf-8");
  await writeFile(staleFixturePath, JSON.stringify(baseStatusFixture(stalePromotionReadinessSummary), null, 2) + "\n", "utf-8");
  await writeFile(
    missingFixturePath,
    JSON.stringify(baseStatusFixture(missingPromotionReadinessSummary), null, 2) + "\n",
    "utf-8",
  );

  const server = startDashboardServer();
  let browser;
  try {
    const baseUrl = `http://127.0.0.1:${port}`;
    await waitForDashboard(baseUrl);
    browser = await launchBrowser(chromium);
    const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await assertPromotionPage(
      page,
      baseUrl,
      freshFixtureName,
      [
        "Goal Operations",
        "Promotion readiness",
        "Promotion gate",
        "fresh",
        "ready",
        "promote ok",
        "CAN PROMOTE",
        "yes",
        "FRESHNESS",
        "AGE",
        "SAMPLES",
        "0.25h",
        "goal=loopx-meta",
        "window=24h · artifacts=true/true",
        "append-only run history",
        "source of truth",
        "fresh promotion readiness fixture",
      ],
      ["rerun needed", "stale promotion readiness fixture", "missing promotion readiness fixture", "[plugin:vite:oxc]", "Transform failed"],
    );

    await assertPromotionPage(
      page,
      baseUrl,
      staleFixtureName,
      [
        "Goal Operations",
        "Promotion readiness",
        "Promotion gate",
        "stale",
        "rerun needed",
        "check first",
        "CAN PROMOTE",
        "no",
        "should_warn=true",
        "python3 examples/canary/canary-promotion-readiness-smoke.py",
        "promotion-readiness evidence is stale; fixture guard",
        "25.5h",
        "goal=loopx-meta",
        "window=24h · artifacts=true/true",
        "stale promotion readiness fixture",
      ],
      ["fresh promotion readiness fixture", "missing promotion readiness fixture", "[plugin:vite:oxc]", "Transform failed"],
    );

    await assertPromotionPage(
      page,
      baseUrl,
      missingFixtureName,
      [
        "Goal Operations",
        "Promotion readiness",
        "Promotion gate",
        "missing",
        "rerun needed",
        "check first",
        "CAN PROMOTE",
        "no",
        "should_warn=true",
        "promotion-readiness evidence is missing; fixture guard",
        "n/a",
        "goal=none",
        "no canary promotion readiness run found in sampled history",
        "missing promotion readiness fixture",
      ],
      ["fresh promotion readiness fixture", "stale promotion readiness fixture", "[plugin:vite:oxc]", "Transform failed"],
    );

    if (pageErrors.length) {
      throw new Error(`Dashboard page errors: ${pageErrors.join(" | ")}`);
    }

    console.log("dashboard-promotion-readiness-browser-smoke ok");
  } finally {
    if (browser) {
      await browser.close();
    }
    server.kill("SIGTERM");
    await rm(freshFixturePath, { force: true });
    await rm(staleFixturePath, { force: true });
    await rm(missingFixturePath, { force: true });
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
