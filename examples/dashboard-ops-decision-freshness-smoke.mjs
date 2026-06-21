#!/usr/bin/env node
// Browser-level smoke for the ops Decision Freshness panel.

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
const oldContractFixtureName = "status.ops-decision-freshness-old-contract.json";
const emptyFixtureName = "status.ops-decision-freshness-empty.json";
const staleFixtureName = "status.ops-decision-freshness-stale.json";
const oldContractFixturePath = resolve(publicDir, oldContractFixtureName);
const emptyFixturePath = resolve(publicDir, emptyFixtureName);
const staleFixturePath = resolve(publicDir, staleFixtureName);
const port = Number(process.env.LOOPX_DASHBOARD_OPS_FRESHNESS_SMOKE_PORT ?? "5195");

const quotaEligible = {
  compute: 1,
  window_hours: 24,
  slot_minutes: 1,
  allowed_slots: 1440,
  spent_slots: 9,
  state: "eligible",
  reason: "fixture eligible quota",
};

function baseStatusFixture(decisionFreshnessSummary) {
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
      checks: ["public-safe ops decision freshness fixture"],
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
      checks: ["public-safe ops decision freshness fixture"],
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
          status: "decision_freshness_ops_panel_fixture",
          waiting_on: "codex",
          severity: "action",
          recommended_action: "continue fixture product-hardening validation",
          project_asset: {
            owner: "codex",
            gate: "none",
            next_action: "continue fixture product-hardening validation",
            stop_condition: "fixture stop condition",
            user_todos: { open: 0, done: 1, total: 1, next: null },
            agent_todos: { open: 1, done: 0, total: 1, next: "validate decision freshness panel" },
            quota: quotaEligible,
            latest_validation: {
              generated_at: "2026-01-01T00:00:00+00:00",
              classification: "decision_freshness_ops_panel_fixture",
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
            items: [{ index: 1, done: false, text: "validate decision freshness panel", review_materials: [] }],
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
          status: "decision_freshness_ops_panel_fixture",
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
              classification: "decision_freshness_ops_panel_fixture",
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
          classification: "decision_freshness_ops_panel_fixture",
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
    decision_freshness_summary: decisionFreshnessSummary,
  };
}

const emptyDecisionFreshnessSummary = {
  available: true,
  source: "run_history",
  sample_run_count: 1,
  window_days: 7,
  proxy_note: "live zero-item fixture",
  summary: {
    decision_count: 0,
    stale_count: 0,
    rebase_required_count: 0,
    fresh_count: 0,
  },
  items: [],
};

const staleDecisionFreshnessSummary = {
  available: true,
  source: "run_history",
  sample_run_count: 2,
  window_days: 7,
  proxy_note: "stale decision fixture",
  summary: {
    decision_count: 1,
    stale_count: 1,
    rebase_required_count: 1,
    fresh_count: 0,
  },
  items: [
    {
      goal_id: "loopx-meta",
      decision_kind: "operator_gate",
      decision_at: "2025-12-24T00:00:00+00:00",
      classification: "operator_gate_approved",
      age_days: 8.4,
      stale_by_age: true,
      newer_event_count_7d: 2,
      newer_event_classes_7d: {
        accounting: 0,
        decision: 0,
        evidence: 1,
        state: 1,
        work: 0,
      },
      freshness_state: "stale_rebase_required",
      requires_decision_point_rebase: true,
      reason: "fixture stale operator gate",
    },
  ],
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

async function assertOpsPage(page, baseUrl, fixtureName, expected, forbidden) {
  const statusUrl = encodeURIComponent(`${baseUrl}/${fixtureName}`);
  await page.goto(`${baseUrl}/?view=ops&statusUrl=${statusUrl}`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=决策 freshness", { timeout: 10_000 });
  const body = await page.locator("body").innerText();
  assertIncludes(body, expected, fixtureName);
  assertExcludes(body, forbidden, fixtureName);
}

async function main() {
  const { chromium } = loadPlaywright();
  const oldContractFixture = baseStatusFixture(emptyDecisionFreshnessSummary);
  delete oldContractFixture.status_contract;
  await writeFile(oldContractFixturePath, JSON.stringify(oldContractFixture, null, 2) + "\n", "utf-8");
  await writeFile(emptyFixturePath, JSON.stringify(baseStatusFixture(emptyDecisionFreshnessSummary), null, 2) + "\n", "utf-8");
  await writeFile(staleFixturePath, JSON.stringify(baseStatusFixture(staleDecisionFreshnessSummary), null, 2) + "\n", "utf-8");

  const server = startDashboardServer();
  let browser;
  try {
    const baseUrl = `http://127.0.0.1:${port}`;
    await waitForDashboard(baseUrl);
    browser = await launchBrowser(chromium);
    const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await assertOpsPage(
      page,
      baseUrl,
      oldContractFixtureName,
      [
        "Goal Operations",
        "状态服务契约过旧",
        "schema v0",
        "127.0.0.1:8766",
        "scripts/macos-dashboard-launchagent.sh restart",
      ],
      ["[plugin:vite:oxc]", "Transform failed"],
    );

    await assertOpsPage(
      page,
      baseUrl,
      emptyFixtureName,
      [
        "Goal Operations",
        "决策 freshness",
        "rebase 0",
        "DECISIONS",
        "STALE",
        "REBASE",
        "FRESH",
        "当前样本里没有需要 rebase 的 checkpointed decision",
        "live zero-item fixture",
        "exact replay 仍回到 append-only run history",
      ],
      ["状态服务契约过旧", "loopx-meta\ngate", "已过期，需 rebase", "[plugin:vite:oxc]", "Transform failed"],
    );

    await assertOpsPage(
      page,
      baseUrl,
      staleFixtureName,
      [
        "Goal Operations",
        "决策 freshness",
        "rebase 1",
        "loopx-meta",
        "gate",
        "已过期，需 rebase",
        "stale decision fixture",
        "exact replay 仍回到 append-only run history",
      ],
      ["状态服务契约过旧", "当前样本里没有需要 rebase 的 checkpointed decision", "[plugin:vite:oxc]", "Transform failed"],
    );

    if (pageErrors.length) {
      throw new Error(`Dashboard page errors: ${pageErrors.join(" | ")}`);
    }

    console.log("dashboard-ops-decision-freshness-smoke ok");
  } finally {
    if (browser) {
      await browser.close();
    }
    server.kill("SIGTERM");
    await rm(oldContractFixturePath, { force: true });
    await rm(emptyFixturePath, { force: true });
    await rm(staleFixturePath, { force: true });
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
