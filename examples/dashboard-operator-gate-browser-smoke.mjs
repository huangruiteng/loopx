#!/usr/bin/env node
// Browser-level smoke for the dashboard planned operator-gate state.

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/dashboard");
const fixtureName = "status.operator-gate.browser-smoke.json";
const approvedFixtureName = "status.operator-gate-approved.browser-smoke.json";
const staleHistoryApprovedFixtureName = "status.operator-gate-approved-stale-history.browser-smoke.json";
const fixturePath = resolve(dashboardDir, "public", fixtureName);
const approvedFixturePath = resolve(dashboardDir, "public", approvedFixtureName);
const staleHistoryApprovedFixturePath = resolve(dashboardDir, "public", staleHistoryApprovedFixtureName);
const playwrightCliOutputDir = resolve(repoRoot, ".playwright-cli");
const port = Number(process.env.LOOPX_DASHBOARD_OPERATOR_GATE_SMOKE_PORT ?? "5192");
const session = `ghog${process.pid}`;
const pwcli = process.env.PWCLI ?? resolve(homedir(), ".codex/skills/playwright/scripts/playwright_cli.sh");

const goalId = "planned-main-control";
const operatorQuestion = "是否同意 `planned-main-control` 先执行 read-only map opt-in？";
const recommendedAction = "先在 LoopX 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run";
const assetNextAction = "Project asset: handle owner todo before approving the gate";
const assetStopCondition = "Project asset stop: record or defer the owner todo before approval";
const userTodoText = "Read owner review worksheet first.";
const agentTodoText = "Run the read-only map dry-run after owner todo resolution.";
const previewCommand = "loopx read-only-map --goal-id planned-main-control --dry-run";
const approvedAction = "operator approved read-only map; project agent can execute the approved dry-run";
const approvedCommand = "loopx read-only-map --goal-id planned-main-control --dry-run --approved";

const operatorGateQuota = {
  compute: 0.5,
  window_hours: 24,
  slot_minutes: 1,
  allowed_slots: 720,
  spent_slots: 0,
  state: "operator_gate",
  reason: "planned goal needs operator opt-in before spending agent turns",
};

const statusFixture = {
  ok: true,
  registry: "./fixtures/registry.json",
  runtime_root: "./fixtures/runtime",
  goal_count: 1,
  run_count: 0,
  contract: {
    ok: true,
    summary: { errors: 0, warnings: 0, checks: 1 },
    errors: [],
    warnings: [],
    checks: ["public-safe operator-gate dashboard fixture"],
  },
  global_registry: {
    available: true,
    ok: true,
    registry: "./fixtures/registry.global.json",
    current_registry: "./fixtures/registry.json",
    current_registry_is_global: false,
    global_goal_count: 1,
    current_goal_count: 1,
    source_registry_count: 1,
    summary: { high: 0, action: 0, info: 0, checks: 1, findings: 0 },
    findings: [],
    checks: ["public-safe operator-gate dashboard fixture"],
  },
  attention_queue: {
    available: true,
    item_count: 1,
    needs_user_or_controller: 1,
    needs_controller: 0,
    needs_codex: 0,
    watching_external_evidence: 0,
    items: [
      {
        goal_id: goalId,
        status: "planned-high-complexity",
        lifecycle_phase: "planned",
        lifecycle_flags: ["planned"],
        waiting_on: "user_or_controller",
        severity: "action",
        recommended_action: recommendedAction,
        project_asset: {
          owner: "user_or_controller",
          gate: "operator_question",
          next_action: assetNextAction,
          stop_condition: assetStopCondition,
          user_todos: {
            open: 1,
            done: 0,
            total: 1,
            next: userTodoText,
          },
          agent_todos: {
            open: 1,
            done: 0,
            total: 1,
            next: agentTodoText,
          },
          quota: operatorGateQuota,
          latest_validation: {
            generated_at: "2026-01-01T00:00:00+00:00",
            classification: "planned-high-complexity",
            summary: "fixture planned controller opt-in",
          },
        },
        operator_question: operatorQuestion,
        agent_command: previewCommand,
        quota: operatorGateQuota,
        source: "registry",
      },
    ],
  },
  run_history: {
    available: true,
    goal_count: 1,
    run_count: 0,
    goals: [
      {
        id: goalId,
        domain: "operator-gate-fixture",
        status: "planned-high-complexity",
        lifecycle_phase: "planned",
        lifecycle_flags: ["planned"],
        registry_member: true,
        legacy_runtime_goal: false,
        adapter_kind: "complex_project_read_only_map_v0",
        adapter_status: "planned",
        authority_registry: {
          declared: false,
          required: false,
          default_entry_count: 0,
          default_entries_checked: 0,
          default_entries_present: 0,
          topic_authority_count: 0,
          deprecated_source_count: 0,
          conflict_risk: "none",
        },
        quota: operatorGateQuota,
        index_exists: false,
        raw_index_records: 0,
        unique_runs: 0,
        latest_runs: [],
      },
    ],
    recent_runs: [],
  },
};

const approvedStatusFixture = {
  ...statusFixture,
  run_count: 1,
  attention_queue: {
    ...statusFixture.attention_queue,
    needs_user_or_controller: 0,
    needs_codex: 1,
    items: [
      {
        goal_id: goalId,
        status: "operator_gate_approved",
        lifecycle_phase: "mapped",
        lifecycle_flags: ["mapped", "operator_approved"],
        waiting_on: "codex",
        severity: "action",
        recommended_action: approvedAction,
        project_asset: {
          owner: "codex",
          gate: "none",
          next_action: approvedAction,
          stop_condition: "Project asset stop: stop if the approved dry-run command fails",
          agent_todos: {
            open: 1,
            done: 0,
            total: 1,
            next: agentTodoText,
          },
          quota: {
            compute: 0.5,
            window_hours: 24,
            allowed_slots: 12,
            spent_slots: 0,
            state: "eligible",
            reason: "operator gate approved; eligible for the next agent turn",
          },
          latest_validation: {
            generated_at: "2026-01-01T00:01:00+00:00",
            classification: "operator_gate_approved",
            summary: "fixture operator gate approved; agent_command 1/1",
          },
        },
        agent_command: approvedCommand,
        quota: {
          compute: 0.5,
          window_hours: 24,
          allowed_slots: 12,
          spent_slots: 0,
          state: "eligible",
          reason: "operator gate approved; eligible for the next agent turn",
        },
        source: "latest_run",
      },
    ],
  },
  run_history: {
    ...statusFixture.run_history,
    run_count: 1,
    goals: [
      {
        ...statusFixture.run_history.goals[0],
        status: "operator_gate_approved",
        lifecycle_phase: "mapped",
        lifecycle_flags: ["mapped", "operator_approved"],
        index_exists: true,
        raw_index_records: 1,
        unique_runs: 1,
        latest_runs: [
          {
            generated_at: "2026-01-01T00:01:00+00:00",
            goal_id: goalId,
            classification: "operator_gate_approved",
            lifecycle_phase: "mapped",
            lifecycle_flags: ["mapped", "operator_approved"],
            recommended_action: approvedAction,
            health_check: "fixture operator gate approved; agent_command 1/1",
            json_exists: true,
            markdown_exists: true,
            operator_gate: {
              recorded_at: "2026-01-01T00:01:00+00:00",
              gate: "read_only_map_opt_in",
              decision: "approve",
              reason_summary: "approved read-only map dry-run only",
              agent_command: approvedCommand,
            },
          },
        ],
      },
    ],
    recent_runs: [
      {
        generated_at: "2026-01-01T00:01:00+00:00",
        goal_id: goalId,
        classification: "operator_gate_approved",
        lifecycle_phase: "mapped",
        lifecycle_flags: ["mapped", "operator_approved"],
        recommended_action: approvedAction,
        health_check: "fixture operator gate approved; agent_command 1/1",
        json_exists: true,
        markdown_exists: true,
        operator_gate: {
          recorded_at: "2026-01-01T00:01:00+00:00",
          gate: "read_only_map_opt_in",
          decision: "approve",
          reason_summary: "approved read-only map dry-run only",
          agent_command: approvedCommand,
        },
      },
    ],
  },
};

const staleHistoryApprovedStatusFixture = {
  ...approvedStatusFixture,
  run_history: {
    ...approvedStatusFixture.run_history,
    goals: [
      {
        ...statusFixture.run_history.goals[0],
        status: "operator_gate_deferred",
        lifecycle_phase: "planned",
        lifecycle_flags: ["planned"],
        index_exists: true,
        raw_index_records: 1,
        unique_runs: 1,
        latest_runs: [
          {
            generated_at: "2026-01-01T00:00:00+00:00",
            goal_id: goalId,
            classification: "operator_gate_deferred",
            lifecycle_phase: "planned",
            lifecycle_flags: ["planned"],
            recommended_action: "ask the stale operator gate again",
            health_check: "stale latest run should not drive dashboard action selection",
            json_exists: true,
            markdown_exists: true,
            operator_gate: {
              recorded_at: "2026-01-01T00:00:00+00:00",
              gate: "read_only_map_opt_in",
              decision: "defer",
              operator_question: operatorQuestion,
              reason_summary: "stale defer should not replace the current queue item",
              agent_command: "loopx stale-command --dry-run",
            },
          },
        ],
      },
    ],
    recent_runs: [
      {
        generated_at: "2026-01-01T00:00:00+00:00",
        goal_id: goalId,
        classification: "operator_gate_deferred",
        lifecycle_phase: "planned",
        lifecycle_flags: ["planned"],
        recommended_action: "ask the stale operator gate again",
        health_check: "stale latest run should not drive dashboard action selection",
        json_exists: true,
        markdown_exists: true,
        operator_gate: {
          recorded_at: "2026-01-01T00:00:00+00:00",
          gate: "read_only_map_opt_in",
          decision: "defer",
          operator_question: operatorQuestion,
          reason_summary: "stale defer should not replace the current queue item",
          agent_command: "loopx stale-command --dry-run",
        },
      },
    ],
  },
};

function runPw(args, { allowFailure = false, timeoutMs = 30_000 } = {}) {
  const result = spawnSync("bash", [pwcli, ...args], {
    cwd: repoRoot,
    encoding: "utf-8",
    env: { ...process.env, PLAYWRIGHT_CLI_SESSION: session },
    timeout: timeoutMs,
  });
  if (!allowFailure && (result.status !== 0 || result.error)) {
    throw new Error([
      `playwright-cli ${args.join(" ")} failed with ${result.status}`,
      result.error?.message,
      result.stdout,
      result.stderr,
    ].filter(Boolean).join("\n"));
  }
  return result;
}

function parseRawEvalOutput(stdout) {
  const trimmed = stdout.trim();
  if (!trimmed) {
    return "";
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

function evalRaw(expression, { timeoutMs = 10_000 } = {}) {
  const result = runPw(["--raw", "eval", expression], { timeoutMs });
  return parseRawEvalOutput(result.stdout);
}

function navigateTo(url) {
  const gotoResult = runPw(["goto", url], { allowFailure: true, timeoutMs: 5_000 });
  if (gotoResult.status === 0 && !gotoResult.error) {
    return;
  }
  runPw(["--raw", "eval", `() => {
    window.location.href = ${JSON.stringify(url)};
    return window.location.href;
  }`], { allowFailure: true, timeoutMs: 5_000 });
}

function countText(body, text) {
  return body.split(text).length - 1;
}

function requireTexts(body, texts, label) {
  const missing = texts.filter((text) => !body.includes(text));
  if (missing.length) {
    throw new Error(`Missing ${label} text: ${missing.join(", ")}`);
  }
}

function forbidTexts(body, texts, label) {
  const present = texts.filter((text) => body.includes(text));
  if (present.length) {
    throw new Error(`${label}: ${present.join(", ")}`);
  }
}

function requireExactTextCount(body, text, expected, label) {
  const actual = countText(body, text);
  if (actual !== expected) {
    throw new Error(`${label}: expected ${expected}, got ${actual}.`);
  }
}

function requireTextOrder(body, texts, label) {
  let cursor = -1;
  for (const text of texts) {
    const next = body.indexOf(text, cursor + 1);
    if (next < 0) {
      throw new Error(`Missing ${label} ordered text: ${text}`);
    }
    if (next < cursor) {
      throw new Error(`${label}: expected ${texts.join(" -> ")}`);
    }
    cursor = next;
  }
}

async function readBodyText({ requiredText = "User Actions", timeoutMs = 15_000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let body = "";
  let lastError;
  while (Date.now() < deadline) {
    try {
      body = String(evalRaw("() => document.querySelector('main')?.innerText ?? document.body?.innerText ?? ''", { timeoutMs: 5_000 }));
      if (!requiredText || body.includes(requiredText)) {
        return body;
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveTimeout) => setTimeout(resolveTimeout, 250));
  }
  throw new Error([
    `Timed out waiting for page text: ${requiredText}`,
    lastError?.message,
    body.slice(0, 500),
  ].filter(Boolean).join("\n"));
}

function startBrowserSession() {
  let lastProbe;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    runPw(["open", "about:blank"], { allowFailure: true, timeoutMs: 5_000 });
    lastProbe = runPw(["eval", "() => location.href"], { allowFailure: true, timeoutMs: 10_000 });
    if (lastProbe.status === 0 && !lastProbe.error) {
      return;
    }
  }
  throw new Error([
    "Unable to start Playwright CLI browser session.",
    lastProbe?.error?.message,
    lastProbe?.stdout,
    lastProbe?.stderr,
  ].filter(Boolean).join("\n"));
}

function forceKillBrowserSession() {
  spawnSync("pkill", ["-f", `cliDaemon.js ${session}`], {
    encoding: "utf-8",
    timeout: 5_000,
  });
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

async function removeWithRetry(path) {
  let lastError;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      await rm(path, { recursive: true, force: true });
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolveTimeout) => setTimeout(resolveTimeout, 200));
    }
  }
  throw lastError;
}

async function main() {
  if (!existsSync(pwcli)) {
    throw new Error(`Playwright CLI wrapper not found: ${pwcli}`);
  }

  await writeFile(fixturePath, JSON.stringify(statusFixture, null, 2) + "\n", "utf-8");
  await writeFile(approvedFixturePath, JSON.stringify(approvedStatusFixture, null, 2) + "\n", "utf-8");
  await writeFile(staleHistoryApprovedFixturePath, JSON.stringify(staleHistoryApprovedStatusFixture, null, 2) + "\n", "utf-8");

  const server = spawn("npm", ["run", "dev", "--", "--port", String(port), "--strictPort"], {
    cwd: dashboardDir,
    env: process.env,
    stdio: "ignore",
  });

  try {
    const baseUrl = `http://127.0.0.1:${port}`;
    await waitForDashboard(baseUrl);
    startBrowserSession();
    runPw(["resize", "1280", "900"], { allowFailure: true, timeoutMs: 5_000 });
    navigateTo(`${baseUrl}/?statusUrl=/${fixtureName}&goalId=${goalId}&actionKind=all`);
    let body = await readBodyText({ requiredText: "Copy" });
    requireTexts(body, [
      "Todo Focus",
      "User Todo",
      "Agent Priority Todo",
      "1 actions",
      "Project",
      goalId,
      "Controller",
      "Review controller opt-in",
      "Needs approval",
      "User / Controller",
      "Operator question",
      "是否同意 `planned-main-control` 先执行 read-only map opt-in？",
      "先做用户待办",
      "Read owner review worksheet first.",
      "Project asset stop: record or defer the owner todo before approval",
      "Agent command ready after approval",
      "Quota 0.5",
      "Agent todo",
      "Run the read-only map dry-run after owner todo resolution.",
      "Validation",
      "planned-high-complexity",
      "fixture planned controller opt-in",
      "Copy",
    ], "pending dashboard");
    forbidTexts(body, [
      "No user-facing action is active.",
      "Let Codex continue",
      "Codex can continue",
      "Codex can act",
      "continue_from_refreshed_state",
      "continue_codex_action",
      "Operator Review Packet",
      "Copy Review Packet",
      "Copy Handoff",
      "Suggested decision",
      "同意先做 read-only map dry-run；不授权写入或主控接管。",
    ], "Operator-gated goal leaked into confusing UI");
    requireExactTextCount(body, "Review controller opt-in", 2, "All-actions controller action plus selected-detail count");
    requireExactTextCount(body, "Copy", 1, "All-actions review-packet copy count");
    requireTextOrder(body, ["Todo Focus", "User Actions"], "Todo focus should lead user action cards");
    requireTextOrder(body, ["Project", goalId, "Review controller opt-in"], "All-actions project-first card identity");
    if (body.indexOf("Operator question") > body.indexOf("Agent command ready after approval")) {
      throw new Error("Operator question should appear before the after-approval agent command hint.");
    }

    navigateTo(`${baseUrl}/?statusUrl=/${fixtureName}&goalId=${goalId}&actionKind=controller`);
    body = await readBodyText({ requiredText: "Copy" });
    requireTexts(body, [
      "Todo Focus",
      "User Todo",
      "Agent Priority Todo",
      "1 actions",
      "Project",
      goalId,
      "Controller",
      "Review controller opt-in",
      "Needs approval",
      "Operator question",
      "是否同意 `planned-main-control` 先执行 read-only map opt-in？",
      "Read owner review worksheet first.",
      "Agent todo",
      "Run the read-only map dry-run after owner todo resolution.",
      "Validation",
      "planned-high-complexity",
      "Copy",
    ], "focused controller dashboard");
    forbidTexts(body, [
      "No user-facing action is active.",
      "Operator Review Packet",
      "Let Codex continue",
      "Codex can continue",
      "Copy Review Packet",
      "Copy Handoff",
      "Suggested decision",
      "同意先做 read-only map dry-run；不授权写入或主控接管。",
    ], "Focused controller view rendered confusing stale UI");
    requireExactTextCount(body, "Review controller opt-in", 2, "Focused controller action plus selected-detail count");
    requireExactTextCount(body, "Copy", 1, "Focused controller review-packet copy count");
    requireTextOrder(body, ["Todo Focus", "User Actions"], "Focused todo focus should lead user action cards");
    requireTextOrder(body, ["Project", goalId, "Review controller opt-in"], "Focused controller project-first card identity");

    navigateTo(`${baseUrl}/?statusUrl=/${approvedFixtureName}&goalId=${goalId}&actionKind=all`);
    body = await readBodyText({ requiredText: "Copy" });
    requireTexts(body, [
      "1 actions",
      "Project",
      goalId,
      "Codex",
      "Run approved agent command",
      "Approved handoff",
      "Approved agent command",
      "approved command",
      "approve",
      "Copy Handoff",
    ], "approved dashboard");
    forbidTexts(body, [
      "Review controller opt-in",
      "Needs approval",
      "Operator question",
      "Agent command ready after approval",
      "Operator gate dry-run draft",
      "Operator Review Packet",
      "Copy Review Packet",
    ], "Approved operator gate still looks user-gated");
    requireExactTextCount(body, "Run approved agent command", 2, "Approved Codex-ready action plus selected-detail count");
    requireExactTextCount(body, "Copy", 1, "Approved review-packet copy count");
    requireExactTextCount(body, "Copy Handoff", 1, "Approved handoff copy count");
    requireTextOrder(body, ["Project", goalId, "Run approved agent command"], "Approved project-first card identity");

    navigateTo(`${baseUrl}/?statusUrl=/${staleHistoryApprovedFixtureName}&goalId=${goalId}&actionKind=all`);
    body = await readBodyText({ requiredText: "Copy" });
    requireTexts(body, [
      "1 actions",
      "Project",
      goalId,
      "Codex",
      "Run approved agent command",
      "Approved handoff",
      "Approved agent command",
      "approved command",
      "Copy Handoff",
    ], "current queue over stale history dashboard");
    forbidTexts(body, [
      "Review controller opt-in",
      "Needs approval",
      "Agent command ready after approval",
      "Operator gate dry-run draft",
      "Operator Review Packet",
      "Copy Review Packet",
    ], "Current queue approved action was replaced by stale run-history gate");
    requireExactTextCount(body, "Run approved agent command", 2, "Current queue approved action plus selected-detail count over stale history");
    requireExactTextCount(body, "Copy", 1, "Current queue approved packet copy count over stale history");
    requireExactTextCount(body, "Copy Handoff", 1, "Current queue approved handoff copy count over stale history");
    requireTextOrder(body, ["Project", goalId, "Run approved agent command"], "Current queue approved project-first card identity");
    console.log("dashboard-operator-gate-browser-smoke ok");
  } finally {
    server.kill("SIGTERM");
    await rm(fixturePath, { force: true });
    await rm(approvedFixturePath, { force: true });
    await rm(staleHistoryApprovedFixturePath, { force: true });
    runPw(["close"], { allowFailure: true, timeoutMs: 5_000 });
    runPw(["kill-all"], { allowFailure: true, timeoutMs: 5_000 });
    forceKillBrowserSession();
    await removeWithRetry(playwrightCliOutputDir);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
