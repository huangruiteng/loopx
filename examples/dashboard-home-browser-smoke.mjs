#!/usr/bin/env node
// Browser-level smoke for the canonical Chinese-first dashboard home.

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
const fixtureName = "status.home.browser-smoke.json";
const fixturePath = resolve(dashboardDir, "public", fixtureName);
const port = Number(process.env.GOAL_HARNESS_DASHBOARD_HOME_SMOKE_PORT ?? "5194");

const quotaEligible = {
  compute: 1,
  window_hours: 24,
  slot_minutes: 1,
  allowed_slots: 1440,
  spent_slots: 3,
  state: "eligible",
  reason: "fixture eligible quota",
};

const quotaFocusWait = {
  ...quotaEligible,
  spent_slots: 8,
  state: "focus_wait",
  reason: "fixture outcome floor blocks further spend",
  post_handoff_outcome_gap_streak: 3,
};

const goalSpecs = [
  {
    id: "premium-ui-ai-search-rec-migration",
    domain: "platform-migration-fixture",
    status: "state_refreshed",
    waiting_on: "user_or_controller",
    quota: { ...quotaEligible, state: "operator_gate" },
    userTodos: { open: 1, done: 3, total: 4, next: "请确认 ZJXMT 源 topic/table 权威来源。" },
    userTodoItems: [
      { done: false, text: "请确认 ZJXMT 源 topic/table 权威来源；未确认前不做 Nacos 上传或任务重启。" },
      { done: true, text: "已读完核心迁移文档第 8 节，并确认当前结论。" },
      { done: true, text: "已确认 item embedding 不阻塞当前 P0 i2i 路径。" },
      { done: true, text: "已确认 P0 degrade 走统一标准品策略。" },
    ],
    agentTodos: { open: 4, done: 0, total: 4, next: "验证四个 P0 本地迁移场景。" },
    agentTodoItems: [
      { done: false, text: "验证四个 P0 本地迁移场景，输出 scene_1/4/6/7 的本地证据。" },
      { done: false, text: "复查 Nacos 前置条件，确认 upload 前没有 source topic/table 漂移。" },
      { done: false, text: "按安全再生成计划只写私有 tmp_data，不触碰生产配置。" },
      { done: false, text: "把关闭的 P0 阻塞和剩余 gate 写回迁移目标状态。" },
    ],
    latest: {
      generated_at: "2026-01-01T00:00:00+00:00",
      classification: "state_refreshed",
      delivery_batch_scale: "multi_surface",
      health_check: "fixture platform migration state",
      json_exists: true,
      markdown_exists: true,
    },
  },
  {
    id: "tiger-team-maiduidui-regauc",
    domain: "maiduidui-fixture",
    status: "state_refreshed",
    waiting_on: "codex",
    quota: quotaEligible,
    userTodos: { open: 0, done: 1, total: 1, next: null },
    userTodoItems: [
      { done: true, text: "用户已授权埋堆堆控制器主动推进。" },
    ],
    agentTodos: { open: 4, done: 0, total: 4, next: "巡检 active p4/p3 占用并写回 board 与 ledger。" },
    agentTodoItems: [
      { done: false, text: "巡检 active p4/p3 占用，确认最多 2 个 p4、最多 2 个 p3 运行中。" },
      { done: false, text: "检查半年度 0.75 eval availability 和 monometrics_eval.txt 是否出现。" },
      { done: false, text: "如有可启动候选，先验证 prod-compile-clean 再 launch。" },
      { done: false, text: "每次 launch / fail / eval / retire 都写回 board 和 project ledger。" },
    ],
    latest: {
      generated_at: "2026-01-01T00:01:00+00:00",
      classification: "state_refreshed",
      delivery_batch_scale: "implementation",
      health_check: "fixture MDD active-delivery authorization",
      json_exists: true,
      markdown_exists: true,
    },
  },
  {
    id: "agent-harness-side-bypass",
    domain: "side-bypass-fixture",
    status: "state_refreshed",
    waiting_on: "codex",
    quota: quotaFocusWait,
    userTodos: { open: 1, done: 0, total: 1, next: "提供或批准 hard_category held-out / paired eval 范围。" },
    userTodoItems: [
      { done: false, text: "提供或批准 candidate-specific hard_category held-out / paired eval 范围。" },
    ],
    agentTodos: { open: 3, done: 1, total: 4, next: "产出排序器 / 跨域证据，否则不花配额写 blocker。" },
    agentTodoItems: [
      { done: false, text: "产出排序器 / 跨域证据，证明不是单面小步。" },
      { done: false, text: "若证据范围仍不可用，写回具体 blocker 并停止花配额。" },
      { done: false, text: "禁止继续 summary / queue / field 的表层传播。" },
      { done: true, text: "已识别 outcome_floor_recovery 分支并拦住普通 delivery。" },
    ],
    handoffReadiness: {
      ready: true,
      codex_ready: true,
      source: "project_asset",
      quota_state: "focus_wait",
      handoff_status: "post_handoff_run_seen",
      post_handoff_run_seen: true,
      post_handoff_outcome_gap_streak: 3,
      post_handoff_latest_run: {
        generated_at: "2026-01-01T00:02:00+00:00",
        classification: "state_refreshed",
        delivery_batch_scale: "single_surface",
        delivery_outcome: "outcome_gap",
        health_check: "fixture side-bypass outcome gap",
        json_exists: true,
        markdown_exists: true,
      },
    },
    latest: {
      generated_at: "2026-01-01T00:02:00+00:00",
      classification: "state_refreshed",
      delivery_batch_scale: "single_surface",
      delivery_outcome: "outcome_gap",
      health_check: "fixture side-bypass outcome gap",
      json_exists: true,
      markdown_exists: true,
    },
  },
  {
    id: "goal-harness-meta",
    domain: "goal-harness-fixture",
    status: "dashboard_home_chinese_operator_copy_contract",
    waiting_on: "codex",
    quota: { ...quotaEligible, spent_slots: 9 },
    userTodos: { open: 0, done: 1, total: 1, next: null },
    userTodoItems: [
      { done: true, text: "用户确认分享页应以中文控制面为主屏。" },
    ],
    agentTodos: { open: 3, done: 1, total: 4, next: "拆分 dependency blocker 和 current-goal blocker。" },
    agentTodoItems: [
      { done: false, text: "拆分依赖阻塞和当前目标阻塞，避免 meta 可执行回合空转。" },
      { done: false, text: "增加自动 backlog 候选面，让 P1/P2 可持续推进。" },
      { done: false, text: "统一多项目看板的 serve-status --global-registry 命令说明。" },
      { done: true, text: "已硬化 heartbeat prompt，依赖项目 todo 不再吃掉当前 goal turn。" },
    ],
    controlPlane: {
      self_repair: {
        enabled: true,
        allow_health_blocker_repair: true,
        allow_waiting_projection_repair: true,
      },
    },
    orchestration: {
      mode: "multi_subagent",
      spawn_allowed: true,
      max_children: 2,
      allowed_domains: ["docs", "validation"],
    },
    latest: {
      generated_at: "2026-01-01T00:03:00+00:00",
      classification: "dashboard_home_chinese_operator_copy_contract",
      delivery_batch_scale: "multi_surface",
      delivery_outcome: "primary_goal_outcome",
      health_check: "fixture home copy contract",
      json_exists: true,
      markdown_exists: true,
    },
  },
];

function projectAssetFor(spec) {
  return {
    owner: spec.waiting_on,
    gate: spec.userTodos.open > 0 ? "user_todo" : "none",
    next_action: spec.agentTodos.next ?? "continue from current fixture state",
    stop_condition: "fixture stop condition",
    user_todos: spec.userTodos,
    agent_todos: spec.agentTodos,
    quota: spec.quota,
    control_plane: spec.controlPlane,
    orchestration: spec.orchestration,
    latest_validation: {
      generated_at: spec.latest.generated_at,
      classification: spec.latest.classification,
      summary: spec.latest.health_check,
    },
  };
}

function todoGroupFor(spec, role) {
  const summary = role === "user" ? spec.userTodos : spec.agentTodos;
  const rawItems = role === "user" ? spec.userTodoItems : spec.agentTodoItems;
  return {
    source_section: role === "user" ? "User Todo / Owner Review Reading Queue" : "Agent Todo",
    total_count: summary.total,
    open_count: summary.open,
    done_count: summary.done,
    items: (rawItems ?? []).map((item, index) => ({
      index: index + 1,
      done: item.done,
      text: item.text,
      review_materials: [],
    })),
  };
}

const statusFixture = {
  ok: true,
  registry: "./fixtures/registry.global.json",
  runtime_root: "./fixtures/runtime",
  goal_count: goalSpecs.length,
  run_count: goalSpecs.length,
  status_contract: {
    schema_version: 2,
    minimum_dashboard_schema_version: 2,
    producer: "goal-harness status",
    reload_hint: "scripts/macos-dashboard-launchagent.sh restart",
  },
  contract: {
    ok: true,
    summary: { errors: 0, warnings: 0, checks: 1 },
    errors: [],
    warnings: [],
    checks: ["public-safe dashboard home fixture"],
  },
  global_registry: {
    available: true,
    ok: true,
    registry: "./fixtures/registry.global.json",
    current_registry: "./fixtures/registry.global.json",
    current_registry_is_global: true,
    global_goal_count: goalSpecs.length,
    current_goal_count: goalSpecs.length,
    source_registry_count: 4,
    summary: { high: 0, action: 0, info: 0, checks: 1, findings: 0 },
    findings: [],
    checks: ["public-safe dashboard home fixture"],
  },
  attention_queue: {
    available: true,
    item_count: goalSpecs.length,
    needs_user_or_controller: 1,
    needs_controller: 0,
    needs_codex: 3,
    watching_external_evidence: 0,
    autonomous_backlog_candidates: {
      source: "attention_queue.agent_todos",
      open_count: 2,
      items: [
        {
          goal_id: "goal-harness-meta",
          status: "dashboard_home_chinese_operator_copy_contract",
          waiting_on: "codex",
          quota_state: "eligible",
          priority: "P1",
          todo_index: 2,
          text: "增加自动 backlog 候选面，让 P1/P2 可持续推进。",
          source: "agent_todos",
        },
        {
          goal_id: "tiger-team-maiduidui-regauc",
          status: "state_refreshed",
          waiting_on: "codex",
          quota_state: "eligible",
          priority: "P2",
          todo_index: 1,
          text: "巡检 active p4/p3 占用，确认最多 2 个 p4、最多 2 个 p3 运行中。",
          source: "agent_todos",
        },
      ],
    },
    items: goalSpecs.map((spec) => {
      const sideBypass = goalSpecs.find((goal) => goal.id === "agent-harness-side-bypass");
      const sideBypassUserTodo = sideBypass?.userTodoItems?.find((todo) => !todo.done);
      return {
        goal_id: spec.id,
        status: spec.status,
        waiting_on: spec.waiting_on,
        severity: "action",
        recommended_action: spec.agentTodos.next ?? "continue from current fixture state",
        project_asset: projectAssetFor(spec),
        handoff_readiness: spec.handoffReadiness,
        quota: spec.quota,
        control_plane: spec.controlPlane,
        user_todos: todoGroupFor(spec, "user"),
        agent_todos: todoGroupFor(spec, "agent"),
        dependency_blockers: spec.id === "goal-harness-meta" && sideBypassUserTodo
          ? {
              source: "attention_queue.user_todos",
              open_count: 1,
              items: [{
                goal_id: "agent-harness-side-bypass",
                status: "state_refreshed",
                waiting_on: "codex",
                severity: "action",
                index: 1,
                text: sideBypassUserTodo.text,
                source: "user_todos",
              }],
            }
          : null,
        source: "fixture",
      };
    }),
  },
  run_history: {
    available: true,
    goal_count: goalSpecs.length,
    run_count: goalSpecs.length,
    goals: goalSpecs.map((spec) => ({
      id: spec.id,
      domain: spec.domain,
      status: spec.status,
      lifecycle_phase: "fixture",
      lifecycle_flags: ["fixture"],
      registry_member: true,
      legacy_runtime_goal: false,
      adapter_kind: "dashboard_home_fixture",
      adapter_status: "connected",
      quota: spec.quota,
      control_plane: spec.controlPlane,
      spawn_policy: spec.orchestration,
      index_exists: true,
      raw_index_records: 1,
      unique_runs: 1,
      latest_runs: [{ ...spec.latest, goal_id: spec.id }],
    })),
    recent_runs: goalSpecs.map((spec) => ({ ...spec.latest, goal_id: spec.id })),
  },
  usage_summary: {
    available: true,
    source: "run_history",
    sample_run_count: 4,
    proxy_note: "public-safe dashboard home fixture",
    totals: {
      runs_24h: 8,
      runs_7d: 8,
      quota_spend_slots_24h: 6,
      quota_spend_slots_7d: 6,
      automation_run_count_24h: 5,
      automation_run_count_7d: 5,
      progress_signal_run_count_24h: 4,
      progress_signal_run_count_7d: 4,
    },
    goals: goalSpecs.map((spec, index) => ({
      goal_id: spec.id,
      runs_24h: 2,
      runs_7d: 2,
      quota_spend_slots_24h: index,
      quota_spend_slots_7d: index,
      automation_run_count_24h: 1,
      automation_run_count_7d: 1,
      progress_signal_run_count_24h: 1,
      progress_signal_run_count_7d: 1,
      project_share_24h: 0.25,
    })),
  },
  decision_freshness_summary: {
    available: true,
    source: "run_history",
    sample_run_count: 4,
    window_days: 7,
    proxy_note: "public-safe dashboard home fixture",
    summary: {
      decision_count: 1,
      stale_count: 1,
      rebase_required_count: 1,
      fresh_count: 0,
    },
    items: [
      {
        goal_id: "goal-harness-meta",
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
  },
};

function loadPlaywright() {
  const candidates = [
    process.env.GOAL_HARNESS_PLAYWRIGHT_PACKAGE,
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

  throw new Error("Playwright package not found; install playwright or set GOAL_HARNESS_PLAYWRIGHT_PACKAGE");
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
    process.env.GOAL_HARNESS_NODE_BIN,
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

async function main() {
  const { chromium } = loadPlaywright();
  await writeFile(fixturePath, JSON.stringify(statusFixture, null, 2) + "\n", "utf-8");

  const server = startDashboardServer();
  let browser;
  try {
    const baseUrl = `http://127.0.0.1:${port}`;
    await waitForDashboard(baseUrl);
    browser = await launchBrowser(chromium);
    const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.goto(`${baseUrl}/?statusUrl=/${fixtureName}`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="share-overview"]', { timeout: 10_000 });

    const body = await page.locator("body").innerText();
    const required = [
      "把多项目 Agent 工作变成可管理的 Todo、证据和配额",
      "平台迁移",
      "请确认 ZJXMT 源 topic/table 权威来源",
      "埋堆堆打平",
      "最多 2 个 p4 运行中",
      "最多 2 个 p3 运行中",
      "Agent Harness 旁路",
      "暂缓不花配额",
      "排序器 / 跨域证据",
      "Goal Harness Meta",
      "配额守卫",
      "状态写回",
      "Top-4 Todo",
      "可自动推进候选",
      "待用户",
      "待 Agent",
      "已完成",
      "依赖阻塞",
      "决策需 rebase",
      "审批或转交前先重读",
      "这不是仓库回滚",
      "验证四个 P0 本地迁移场景",
      "拆分依赖阻塞和当前目标阻塞",
    ];
    const missing = required.filter((text) => !body.includes(text));
    if (missing.length) {
      throw new Error(`Missing dashboard home text: ${missing.join(", ")}`);
    }

    const forbidden = [
      "[plugin:vite:oxc]",
      "Transform failed",
      "active p4 <= 2",
      "single_surface",
      "quota_slot_spent",
      "focus_wait",
      "状态服务契约过旧",
    ];
    const present = forbidden.filter((text) => body.includes(text));
    if (present.length) {
      throw new Error(`Dashboard home leaked raw machine/debug text: ${present.join(", ")}`);
    }

    const url = new URL(page.url());
    if (url.searchParams.get("view")) {
      throw new Error(`Canonical home should not keep a view search param: ${page.url()}`);
    }

    await page.goto(`${baseUrl}/?view=ops&goalId=goal-harness-meta&statusUrl=/${fixtureName}`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="control-plane-settings-panel"]', { timeout: 10_000 });
    const settingsText = await page.locator('[data-testid="control-plane-settings-panel"]').innerText();
    const requiredSettings = [
      "Control Plane Settings",
      "Quota 1",
      "self_repair on",
      "health=on",
      "waiting_projection=on",
      "Heartbeat install",
      "observed",
      "multi_subagent",
      "max_children=2",
      "domains=docs,validation",
    ];
    const missingSettings = requiredSettings.filter((text) => !settingsText.includes(text));
    if (missingSettings.length) {
      throw new Error(`Missing control-plane settings text: ${missingSettings.join(", ")}`);
    }
    await page.locator('[data-testid="control-plane-quota-compute"]').fill("1.5");
    const updatedSettingsText = await page.locator('[data-testid="control-plane-settings-panel"]').innerText();
    if (!updatedSettingsText.includes("dirty")) {
      throw new Error("Control-plane settings draft did not enter dirty state after editing quota.");
    }
    const settingsCommand = await page.locator('[data-testid="control-plane-settings-command-preview"]').innerText();
    const requiredCommandParts = [
      "configure-goal",
      "--goal-id goal-harness-meta",
      "--quota-compute 1.5",
      "--quota-window-hours 24",
      "--self-repair-enabled",
      "--self-repair-health",
      "--self-repair-waiting-projection",
      "--orchestration-mode multi_subagent",
      "--spawn-allowed",
      "--max-children 2",
      "--allowed-domain docs",
      "--allowed-domain validation",
    ];
    const missingCommandParts = requiredCommandParts.filter((text) => !settingsCommand.includes(text));
    if (missingCommandParts.length) {
      throw new Error(`Missing control-plane settings command text: ${missingCommandParts.join(", ")}`);
    }
    if (settingsCommand.includes("--execute")) {
      throw new Error("Control-plane command preview must stay dry-run by default.");
    }

    if (pageErrors.length) {
      throw new Error(`Dashboard page errors: ${pageErrors.join(" | ")}`);
    }

    console.log("dashboard-home-browser-smoke ok");
  } finally {
    if (browser) {
      await browser.close();
    }
    server.kill("SIGTERM");
    await rm(fixturePath, { force: true });
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
