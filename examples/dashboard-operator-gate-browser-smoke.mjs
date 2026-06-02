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
const fixturePath = resolve(dashboardDir, "public", fixtureName);
const playwrightCliOutputDir = resolve(repoRoot, ".playwright-cli");
const port = Number(process.env.GOAL_HARNESS_DASHBOARD_OPERATOR_GATE_SMOKE_PORT ?? "5192");
const session = `ghog${process.pid}`;
const pwcli = process.env.PWCLI ?? resolve(homedir(), ".codex/skills/playwright/scripts/playwright_cli.sh");

const goalId = "planned-main-control";
const operatorQuestion = "是否同意 `planned-main-control` 先执行 read-only map opt-in？";
const recommendedAction = "先在 Goal Harness 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run";
const previewCommand = "goal-harness read-only-map --goal-id planned-main-control --dry-run";

const operatorGateQuota = {
  compute: 0.5,
  window_hours: 24,
  allowed_slots: 12,
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

function runPw(args, { allowFailure = false } = {}) {
  const result = spawnSync("bash", [pwcli, ...args], {
    cwd: repoRoot,
    encoding: "utf-8",
    env: { ...process.env, PLAYWRIGHT_CLI_SESSION: session },
  });
  if (!allowFailure && result.status !== 0) {
    throw new Error([
      `playwright-cli ${args.join(" ")} failed with ${result.status}`,
      result.stdout,
      result.stderr,
    ].filter(Boolean).join("\n"));
  }
  return result;
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

  const server = spawn("npm", ["run", "dev", "--", "--port", String(port), "--strictPort"], {
    cwd: dashboardDir,
    env: process.env,
    stdio: "ignore",
  });

  try {
    const baseUrl = `http://127.0.0.1:${port}`;
    await waitForDashboard(baseUrl);
    runPw(["open", `${baseUrl}/?statusUrl=/${fixtureName}&goalId=${goalId}&actionKind=all`]);
    runPw(["resize", "1280", "900"]);
    runPw([
      "run-code",
      String.raw`async (page) => {
        await page.waitForLoadState("networkidle");
        await page.getByText("User Actions").waitFor();
        const body = await page.locator("body").innerText();
        const required = [
          "1 actions",
          "Controller",
          "Review controller opt-in",
          "Needs approval",
          "User / Controller",
          "Operator question",
          "是否同意 \`planned-main-control\` 先执行 read-only map opt-in？",
          "Agent command ready after approval",
          "Quota 0.5",
          "等待人或控制器决策",
          "0/12 slots",
          "Suggested decision",
          "同意先做 read-only map dry-run；不授权写入或主控接管。",
          "Copy Review Packet",
        ];
        const missing = required.filter((text) => !body.includes(text));
        if (missing.length) {
          throw new Error("Missing dashboard text: " + missing.join(", "));
        }
        const forbidden = [
          "0 actions",
          "No user-facing action is active.",
          "Let Codex continue",
          "Codex can continue",
          "Codex can act",
          "continue_from_refreshed_state",
          "continue_codex_action",
        ];
        const present = forbidden.filter((text) => body.includes(text));
        if (present.length) {
          throw new Error("Operator-gated goal leaked into Codex-ready UI: " + present.join(", "));
        }
        if (body.indexOf("Operator question") > body.indexOf("Agent command ready after approval")) {
          throw new Error("Operator question should appear before the after-approval agent command hint.");
        }
        return {
          ok: true,
          operatorQuestionVisible: body.includes("Operator question"),
          codexCopyAbsent: !body.includes("Let Codex continue"),
        };
      }`,
    ]);
    console.log("dashboard-operator-gate-browser-smoke ok");
  } finally {
    server.kill("SIGTERM");
    await rm(fixturePath, { force: true });
    runPw(["close"], { allowFailure: true });
    await removeWithRetry(playwrightCliOutputDir);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
