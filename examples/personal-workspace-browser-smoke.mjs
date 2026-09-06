#!/usr/bin/env node
// Focused browser smoke for the personal Agent workspace first screen and interactions.

import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  launchBrowser,
  loadPlaywright,
  startViteDashboardServer,
  waitForHttp,
} from "./dashboard-browser-smoke-support.mjs";

const require = createRequire(import.meta.url);
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/presentation/dashboard");
const outputDir = resolve(repoRoot, "output/playwright/personal-workspace");
const port = Number(process.env.LOOPX_PERSONAL_WORKSPACE_PORT ?? "5196");
const packaged = process.env.LOOPX_PERSONAL_WORKSPACE_PACKAGED === "1";

const periodicReportProjection = {
  schema_version: "periodic_report_workspace_projection_v0",
  goal_id: "product-release",
  agent_id: "codex",
  generation_id: "generation-workspace-smoke",
  generated_at: "2026-09-01T10:00:00Z",
  title: "Product Release milestone report",
  summary: "A verified incremental report shown with the Goal's other durable outputs.",
  content_sha256: `sha256:${"7".repeat(64)}`,
  period_window: { start_at: "2026-08-25T10:00:00Z", end_at: "2026-09-01T10:00:00Z" },
  interaction: { attention_kind: "progress", interaction: "inform", delivery: "surface", form: "milestone_report", writable: false },
  delta: {
    added_count: 1,
    changed_count: 1,
    item_count: 2,
    items: [
      { fact_id: "fact-added", source_ref: "todo:release-ready", title: "Release candidate verified", summary: "The candidate passed the bounded verification suite.", status: "done", content_kind: "outcome", change_kind: "added" },
      { fact_id: "fact-changed", source_ref: "todo:rollout", title: "Rollout plan updated", summary: "The next rollout step now carries an explicit readback gate.", status: "open", content_kind: "next_action", change_kind: "changed", previous_status: "blocked" },
    ],
  },
  publication: { publication_id: "publication-workspace-smoke", delivered_at: "2026-09-01T10:05:00Z", predecessor_publication_id: "publication-workspace-previous", cursor_id: "cursor-workspace-smoke" },
  truth_contract: { published_cursor_is_source_of_truth: true, generation_receipt_is_delivery_receipt: false, projection_is_writable: false, browser_write_api: false },
};

function periodicReportCapability({ effectiveConfiguration, machineCurrent } = {}) {
  return {
    capability_id: "periodic_report",
    display_name: "Periodic reports",
    description: "Turn validated Goal progress into a reviewable report draft.",
    available_scopes: ["machine", "goal"],
    availability: "supported_explicit_override",
    machine_namespace: "periodic_report",
    goal_feature_id: "periodic_report",
    effective_value_policy: "goal_override_over_live_machine_default",
    default: {
      schema_version: "periodic_report_machine_defaults_v0",
      enabled: false,
      inheritance: "live_machine_default",
      timezone: "UTC",
    },
    ...(machineCurrent ? { machine_current: machineCurrent } : {}),
    ...(effectiveConfiguration ? { effective_configuration: effectiveConfiguration } : {}),
    configuration_editor: {
      schema_version: "capability_configuration_editor_v0",
      editable: true,
      supported_scopes: ["machine", "goal"],
      writable_scopes: ["machine", "goal"],
      fields: [
        { key: "enabled", label: "Enabled", description: "", input_kind: "boolean", required: false },
        { key: "profile_preset", label: "Profile preset", description: "", input_kind: "text", required: false },
        { key: "route_ref", label: "Goal Channel route", description: "", input_kind: "text", required: false },
        { key: "timezone", label: "Timezone", description: "", input_kind: "text", required: true },
      ],
    },
  };
}

function multiSubagentCapability({ current } = {}) {
  const fallback = {
    enabled: false,
    max_children: 4,
    allowed_domains: [],
  };
  const effective = current ?? fallback;
  return {
    capability_id: "multi_subagent",
    display_name: "Adaptive child capacity",
    description: "Bound child-agent capacity and eligible responsibility domains.",
    available_scopes: ["goal"],
    availability: "supported_opt_in",
    goal_feature_id: "multi_subagent",
    default: fallback,
    ...(current ? { current } : {}),
    effective_configuration: {
      schema_version: "capability_configuration_resolution_v0",
      capability_id: "multi_subagent",
      source: current ? "goal_override" : "capability_default",
      configuration: effective,
      inherited: false,
      goal_override_present: Boolean(current),
      machine_default_present: false,
      effective_revision: current ? "sha256:subagent-current" : "sha256:subagent-default",
    },
    configuration_editor: {
      schema_version: "capability_configuration_editor_v0",
      editable: true,
      supported_scopes: ["goal"],
      writable_scopes: ["goal"],
      fields: [
        { key: "enabled", label: "Enabled", description: "", input_kind: "boolean", required: false },
        { key: "max_children", label: "Maximum children", description: "", input_kind: "number", required: false, minimum: 1, maximum: 32 },
        { key: "allowed_domains", label: "Allowed responsibility domains", description: "", input_kind: "string_list", required: false },
      ],
    },
  };
}

function goalCapability({
  availability = "supported_opt_in",
  capabilityId,
  displayName,
  fields = [{ key: "enabled", label: "Enabled", description: "", input_kind: "boolean", required: false }],
  readOnlyReason,
}) {
  const editable = fields.length > 0;
  return {
    capability_id: capabilityId,
    display_name: displayName,
    description: `${displayName} Goal policy.`,
    available_scopes: ["goal"],
    goal_feature_id: capabilityId,
    availability,
    default: editable ? Object.fromEntries(fields.flatMap((field) => field.key === "enabled" ? [[field.key, false]] : [])) : {},
    configuration_editor: {
      schema_version: "capability_configuration_editor_v0",
      editable,
      supported_scopes: ["goal"],
      writable_scopes: editable ? ["goal"] : [],
      fields,
      ...(readOnlyReason ? { read_only_reason: readOnlyReason } : {}),
    },
  };
}

function goalCapabilityCatalog(multiSubagentConfiguration) {
  return [
    periodicReportCapability(),
    goalCapability({
      capabilityId: "change_quality_qualification",
      displayName: "Change quality qualification",
      fields: [
        { key: "enabled", label: "Enabled", description: "", input_kind: "boolean", required: false },
        { key: "safe_fix", label: "Allow one bounded safe-fix pass", description: "", input_kind: "boolean", required: false },
        { key: "strict_receipt", label: "Require an exact-diff receipt", description: "", input_kind: "boolean", required: false },
      ],
    }),
    goalCapability({ capabilityId: "explore_graph", displayName: "Explore Graph" }),
    goalCapability({
      capabilityId: "explore_harness",
      displayName: "Explore Harness",
      fields: [
        { key: "enabled", label: "Enabled", description: "", input_kind: "boolean", required: false },
        { key: "profile", label: "Planner profile", description: "", input_kind: "select", required: false, options: ["generic"] },
      ],
    }),
    goalCapability({ capabilityId: "lark_kanban_heartbeat_sync", displayName: "Lark Kanban heartbeat sync" }),
    goalCapability({
      capabilityId: "lark_event_inbox",
      displayName: "Lark event inbox",
      fields: [],
      readOnlyReason: "Requires a local-private provider binding.",
    }),
    goalCapability({
      availability: "supported_explicit_opt_in",
      capabilityId: "peer_task_coordination",
      displayName: "Registered-peer task coordination",
      fields: [{ key: "coordinator_agent_id", label: "Coordinator Agent", description: "", input_kind: "text", required: false }],
    }),
    multiSubagentCapability({ current: multiSubagentConfiguration }),
    goalCapability({ availability: "experimental_opt_in", capabilityId: "local_authority_shadow", displayName: "Local authority shadow" }),
    goalCapability({
      availability: "experimental_opt_in",
      capabilityId: "reward_memory",
      displayName: "Reward Memory experiment",
      fields: [],
      readOnlyReason: "Requires a reviewed local-private provider binding.",
    }),
  ];
}

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

async function visibleElementCount(locator) {
  return locator.evaluateAll((elements) => elements.filter((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  }).length);
}

async function waitForInputValue(locator, expected, timeoutMs = 5_000) {
  const deadline = Date.now() + timeoutMs;
  let actual = await locator.inputValue();
  while (actual !== expected && Date.now() < deadline) {
    await new Promise((resolveWait) => setTimeout(resolveWait, 50));
    actual = await locator.inputValue();
  }
  if (actual !== expected) {
    throw new Error(`Timed out waiting for input value ${expected}; received ${actual}`);
  }
}

function capturedStatusGeneration(state) {
  if (!state.captureNextStatusGeneration) return state.goalActivationStates;
  if (!state.capturedStatusGeneration) {
    state.capturedStatusGeneration = new Map(state.goalActivationStates);
  }
  return state.capturedStatusGeneration;
}

function filterStatusFixtureToScope(fixture, statusGeneration, scope) {
  const activationForGoal = (goalId) => statusGeneration.get(goalId) ?? "active";
  const matchesScope = (goalId) => activationForGoal(goalId) === scope;
  fixture.attention_queue.items = fixture.attention_queue.items.filter((item) => matchesScope(item.goal_id));
  fixture.attention_queue.item_count = fixture.attention_queue.items.length;
  if (fixture.todo_index?.items) {
    fixture.todo_index.items = fixture.todo_index.items.filter((item) => matchesScope(item.goal_id));
    fixture.todo_index.total_count = fixture.todo_index.items.length;
  }
  if (fixture.usage_summary?.goals) {
    fixture.usage_summary.goals = fixture.usage_summary.goals.filter((item) => matchesScope(item.goal_id));
  }
  if (fixture.event_ledger_summary?.goals) {
    fixture.event_ledger_summary.goals = fixture.event_ledger_summary.goals.filter((item) => matchesScope(item.goal_id));
  }
  if (fixture.decision_freshness_summary?.items) {
    fixture.decision_freshness_summary.items = fixture.decision_freshness_summary.items.filter((item) => matchesScope(item.goal_id));
  }
  if (fixture.agent_management_projection?.agents) {
    fixture.agent_management_projection.agents = fixture.agent_management_projection.agents.filter((agent) =>
      (agent.goal_ids ?? []).some(matchesScope) || matchesScope(agent.current_todo?.goal_id));
  }
  if (fixture.goal_channel_notification_projection?.goals) {
    fixture.goal_channel_notification_projection.goals = fixture.goal_channel_notification_projection.goals.filter((item) => matchesScope(item.goal_id));
  }
}

async function installApi(page, { goalSubagentConfigurationEnabled = true } = {}) {
  let turnCounter = 0;
  const runtime = page.__loopxRuntime ??= { actionProposals: new Map(), goalSubagentConfigurations: new Map(), larkConnections: [], messages: new Map(), sessions: new Map(), turnMessages: new Map() };
  const actionProposals = runtime.actionProposals;
  const sessions = runtime.sessions;
  const messages = runtime.messages;
  const turnMessages = runtime.turnMessages;
  const actionKinds = new Map(Array.from(actionProposals.values(), (proposal) => [proposal.proposal_id, proposal.action_kind]));
  const state = {
    actionApplies: [],
    actionCancels: [],
    actionPreviews: [],
    durableResources: new Set(),
    durableWriteCount: 0,
    failNextLifecycleApply: false,
    failNextGoalSubagentResponse: false,
    failNextLifecyclePreview: false,
    failNextActionPreview: false,
    failNextStatusRequest: false,
    freezeGoalSubagentStatusProjection: false,
    goalSubagentConfigurationEnabled,
    goalActivationStates: new Map([
      ["product-release", "active"],
      ["research-monitor", "active"],
      ["legacy-benchmark", "stopped"],
      ["archived-notes", "stopped"],
    ]),
    goalSubagentPreviews: [],
    goalSubagentWrites: [],
    interrupts: [],
    goalConfigurationRequests: [],
    machineConfigurationRequests: [],
    larkWrites: [],
    actionTransitions: [],
    allowNextHeartbeatApply: false,
    nextLifecycleApplyDelayMs: 0,
    nextLifecyclePreviewDelayMs: 0,
    nextActionPreviewDelayMs: 0,
    nextStatusDelayMs: 0,
    nextFullStatusDelayMs: 0,
    failNextFullStatus: false,
    captureNextStatusGeneration: false,
    capturedStatusGeneration: null,
    activationChangeAfterCapturedActive: null,
    statusRequestCount: 0,
    turnRequests: [],
    get larkConnections() { return runtime.larkConnections; },
    get goalSubagentConfigurations() { return runtime.goalSubagentConfigurations; },
  };
  await page.route(`http://127.0.0.1:${port}/status.json*`, async (route) => {
    state.statusRequestCount += 1;
    const fixture = structuredClone(require(resolve(repoRoot, "examples/status.example.json")));
    const defaultSubagentConfiguration = { mode: "default", spawn_allowed: false, max_children: 0, allowed_domains: [] };
    const projectedSubagentConfiguration = (goalId, fallback) => state.freezeGoalSubagentStatusProjection
      ? fallback ?? defaultSubagentConfiguration
      : runtime.goalSubagentConfigurations.get(goalId) ?? fallback ?? defaultSubagentConfiguration;
    const statusGeneration = capturedStatusGeneration(state);
    fixture.local_dashboard_api = {
      ...(fixture.local_dashboard_api ?? {}),
      periodic_report_index_url: "/periodic-report-workspace",
      periodic_report_detail_url: "/periodic-report-workspace-projection",
    };
    const directoryFixtures = [
      { id: "product-release", display_name: "Product Release" },
      { id: "research-monitor", display_name: "Research Monitor" },
      { id: "progress-projection", display_name: "Progress Projection" },
      { id: "legacy-benchmark", display_name: "Legacy Benchmark" },
      { id: "archived-notes", display_name: "Archived Notes" },
    ];
    for (const directoryGoal of directoryFixtures) {
      const activation_state = statusGeneration.get(directoryGoal.id) ?? "active";
      const existingGoal = fixture.run_history.goals.find((goal) => goal.id === directoryGoal.id);
      if (existingGoal) {
        existingGoal.activation_state = activation_state;
        if (state.goalSubagentConfigurationEnabled) {
          existingGoal.spawn_policy = projectedSubagentConfiguration(directoryGoal.id, existingGoal.spawn_policy);
        } else {
          delete existingGoal.spawn_policy;
        }
        continue;
      }
      fixture.run_history.goals.push({
        ...directoryGoal, activation_state,
        status: "active-read-only", registry_member: true,
        legacy_runtime_goal: false, adapter_kind: "generic_project_goal_v0", adapter_status: "connected",
        lifecycle_phase: "registered", lifecycle_flags: ["registered"],
        ...(state.goalSubagentConfigurationEnabled
          ? { spawn_policy: projectedSubagentConfiguration(directoryGoal.id) }
          : {}),
        quota: { compute: 1, window_hours: 24, slot_minutes: 1, allowed_slots: 1440, spent_slots: 0, state: activation_state === "stopped" ? "paused" : "waiting" },
        index_exists: false, raw_index_records: 0, unique_runs: 0, latest_runs: [],
      });
    }
    for (const fixtureGoal of fixture.run_history.goals) {
      if (state.goalSubagentConfigurationEnabled) {
        fixtureGoal.spawn_policy = projectedSubagentConfiguration(fixtureGoal.id, fixtureGoal.spawn_policy);
      } else {
        delete fixtureGoal.spawn_policy;
      }
    }
    if (!fixture.run_history.goals.some((goal) => goal.id === "stale-browser-goal")) {
      fixture.run_history.goals.push({
        id: "stale-browser-goal", status: "monitoring", registry_member: false,
        legacy_runtime_goal: false, adapter_kind: null, adapter_status: null,
        index_exists: false, raw_index_records: 0, unique_runs: 0, latest_runs: [],
      });
    }
    const first = fixture.attention_queue?.items?.[0];
    if (first) {
      first.waiting_on = "user_or_controller";
      first.user_todos = {
        items: [{ done: false, goal_id: first.goal_id, index: 0, role: "user", text: "确认本轮独立审查范围", todo_id: "todo-browser-user-gate" }],
        open_count: 1,
        source_section: "User Todo",
        total_count: 1,
      };
      const domainTodos = (first.project_asset?.agent_todos?.items ?? first.agent_todos?.items ?? [])
        .filter((todo) => !todo.done)
        .slice(0, 2);
      for (const [index, todo] of domainTodos.entries()) {
        todo.task_class = "advancement_task";
        todo.task_domain = index === 0 ? "code" : "validation";
        const indexedTodo = fixture.todo_index?.items?.find((item) => item.todo_id === todo.todo_id);
        if (indexedTodo) {
          indexedTodo.role = "agent";
          indexedTodo.task_class = todo.task_class;
          indexedTodo.task_domain = todo.task_domain;
        } else if (fixture.todo_index?.items) {
          fixture.todo_index.items.push({ ...todo, goal_id: first.goal_id, role: "agent", source: "browser-smoke" });
        }
      }
    }
    if (!fixture.attention_queue.items.some((item) => item.goal_id === "progress-projection")) {
      const idlessLongTitle = `Idless long Todo ${"projection identity ".repeat(16)}keeps one card`;
      const currentTodo = {
        done: false,
        index: 4,
        role: "agent",
        status: "open",
        task_class: "advancement_task",
        text: "Current Todo",
        title: "Current Todo",
        todo_id: "todo-progress-current",
      };
      fixture.attention_queue.items.push({
        agent_todos: {
          advancement_done_count: 42,
          done_count: 6,
          deferred_count: 2,
          items: [
            currentTodo,
            { done: false, index: 5, role: "agent", status: "open", task_class: "advancement_task", text: idlessLongTitle, title: idlessLongTitle },
            { done: false, index: 7, role: "agent", status: "open", task_class: "advancement_task", text: "Full queue follow-up", title: "Full queue follow-up", todo_id: "todo-progress-full" },
            { done: true, index: 8, role: "agent", status: "deferred", resume_when: "todo_done:todo-progress-full", task_class: "advancement_task", text: "Deferred queue task", title: "Deferred queue task", todo_id: "todo-progress-deferred" },
            { done: true, index: 1, role: "agent", status: "done", task_class: "advancement_task", text: "Completed A", title: "Completed A", todo_id: "todo-progress-a" },
            { done: true, index: 2, role: "agent", status: "done", task_class: "advancement_task", text: "Completed B", title: "Completed B", todo_id: "todo-progress-b" },
            { done: true, index: 3, role: "agent", status: "done", task_class: "advancement_task", text: "Completed C", title: "Completed C", todo_id: "todo-progress-c" },
            { done: true, index: 6, role: "agent", status: "done", task_class: "continuous_monitor", text: "Completed Monitor", title: "Completed Monitor", todo_id: "todo-progress-monitor" },
          ],
          deferred_items: [
            { done: true, index: 8, role: "agent", status: "deferred", resume_when: "todo_done:todo-progress-full", task_class: "advancement_task", text: "Deferred queue task", title: "Deferred queue task", todo_id: "todo-progress-deferred" },
            { done: true, index: 9, role: "agent", status: "deferred", task_class: "advancement_task", text: "Deferred follow-up outside preview", title: "Deferred follow-up outside preview", todo_id: "todo-progress-deferred-extra" },
          ],
          open_count: 3,
          source_section: "Agent Todo",
          total_count: 9,
        },
        goal_id: "progress-projection",
        project_asset: {
          agent_todos: {
            advancement_done_count: 42,
            done: 6,
            deferred_count: 2,
            items: [
              currentTodo,
              { done: false, index: 5, role: "agent", status: "open", task_class: "advancement_task", text: idlessLongTitle.slice(0, 220), title: idlessLongTitle.slice(0, 220) },
            ],
            open: 3,
            recent_completed_advancement_items: [
              { done: true, index: 1, role: "agent", status: "done", task_class: "advancement_task", text: "Completed A", title: "Completed A", todo_id: "todo-progress-a" },
              { done: true, index: 2, role: "agent", status: "done", task_class: "advancement_task", text: "Completed B", title: "Completed B", todo_id: "todo-progress-b" },
              { done: true, index: 3, role: "agent", status: "done", task_class: "advancement_task", text: "Completed C", title: "Completed C", todo_id: "todo-progress-c" },
            ],
            total: 9,
          },
          gate: "none",
          next_action: "Current Todo",
          owner: "example-agent",
          stop_condition: "All synthetic Todos complete",
        },
        recommended_action: "Older Todo",
        severity: "info",
        status: "active",
        waiting_on: "codex",
      });
      fixture.agent_management_projection.agents.push({
        agent_id: "example-agent",
        current_todo: {
          action_kind: "synthetic_progress_projection",
          goal_id: "progress-projection",
          priority: "P0",
          role: "agent",
          status: "open",
          task_class: "advancement_task",
          title: "Current Todo",
          todo_id: "todo-progress-current",
        },
        goal_ids: ["progress-projection"],
        last_activity_at: "2026-08-24T14:53:12+08:00",
        next_action: "Continue projected todo todo-progress-current.",
        state: "running",
      });
    }
    if (!fixture.run_history.goals.some((goal) => goal.id === "multi-agent-projection")) {
      fixture.run_history.goals.push({
        id: "multi-agent-projection", display_name: "Multi Agent Projection", activation_state: "active",
        status: "active-read-only", registry_member: true, legacy_runtime_goal: false,
        adapter_kind: "generic_project_goal_v0", adapter_status: "connected",
        lifecycle_phase: "registered", lifecycle_flags: ["registered"],
        quota: { compute: 1, window_hours: 24, slot_minutes: 1, allowed_slots: 1440, spent_slots: 0, state: "eligible" },
        index_exists: false, raw_index_records: 0, unique_runs: 0, latest_runs: [],
      });
      fixture.attention_queue.items.push({
        agent_todos: { items: [], open_count: 2, source_section: "Agent Todo", total_count: 2 },
        goal_id: "multi-agent-projection",
        project_asset: {
          agent_todos: { items: [], open: 2, done: 0, total: 2 },
          gate: "none", next_action: "Continue the latest work lane", owner: "LoopX", stop_condition: "Both lanes complete",
        },
        recommended_action: "Continue the latest work lane", severity: "info", status: "active", waiting_on: "codex",
      });
      fixture.agent_management_projection.agents.push(
        {
          agent_id: "codex-older-lane",
          current_todo: { claimed_by: "codex-older-lane", goal_id: "multi-agent-projection", role: "agent", status: "open", task_class: "advancement_task", title: "Older lane work", todo_id: "todo-older-lane" },
          goal_ids: ["multi-agent-projection"], last_activity_at: "2026-08-24T10:00:00+08:00", next_action: "Continue projected todo todo-older-lane.", state: "running",
        },
        {
          agent_id: "codex-latest-lane",
          current_todo: { claimed_by: "codex-latest-lane", goal_id: "multi-agent-projection", role: "agent", status: "open", task_class: "advancement_task", title: "Latest lane work", todo_id: "todo-latest-lane" },
          goal_ids: ["multi-agent-projection"], last_activity_at: "2026-08-24T15:00:00+08:00", next_action: "Continue projected todo todo-latest-lane.", state: "running",
        },
      );
    }
    const goalActivationScope = new URL(route.request().url()).searchParams.get("goal_activation");
    const isActiveScope = goalActivationScope === "active";
    const activeGoalCount = fixture.run_history.goals.filter((goal) => goal.activation_state !== "stopped").length;
    const stoppedGoalCount = fixture.run_history.goals.length - activeGoalCount;
    const registryRevision = [...statusGeneration.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([goalId, activationState]) => `${goalId}:${activationState}`)
      .join("|");
    const delayMs = state.nextStatusDelayMs;
    state.nextStatusDelayMs = 0;
    if (delayMs > 0) await new Promise((resolveWait) => setTimeout(resolveWait, delayMs));
    if (state.failNextStatusRequest) {
      state.failNextStatusRequest = false;
      await route.fulfill({ contentType: "application/json", json: { error: "temporary status failure" }, status: 503 });
      return;
    }
    if (isActiveScope) {
      fixture.goal_projection = {
        schema_version: "loopx_goal_projection_scope_v0",
        scope: "active",
        complete: false,
        projected_goal_count: activeGoalCount,
        registry_goal_count: fixture.run_history.goals.length,
        registry_revision: registryRevision,
      };
      fixture.run_history.goals = fixture.run_history.goals.filter((goal) => goal.activation_state !== "stopped");
      filterStatusFixtureToScope(fixture, statusGeneration, "active");
      // Freeze only the first half of the active-first read. The stopped
      // request must observe the registry after the intervening lifecycle
      // change so this fixture exercises the cross-snapshot revision fence.
      state.captureNextStatusGeneration = false;
      state.capturedStatusGeneration = null;
      if (state.activationChangeAfterCapturedActive) {
        const { goalId, activationState } = state.activationChangeAfterCapturedActive;
        state.goalActivationStates.set(goalId, activationState);
        state.activationChangeAfterCapturedActive = null;
      }
    } else if (goalActivationScope === "stopped") {
      const fullDelayMs = state.nextFullStatusDelayMs;
      state.nextFullStatusDelayMs = 0;
      if (fullDelayMs > 0) await new Promise((resolveWait) => setTimeout(resolveWait, fullDelayMs));
      if (state.failNextFullStatus) {
        state.failNextFullStatus = false;
        await route.fulfill({ contentType: "application/json", json: { error: "stopped goals unavailable" }, status: 503 });
        return;
      }
      fixture.goal_projection = {
        schema_version: "loopx_goal_projection_scope_v0",
        scope: "stopped",
        complete: false,
        projected_goal_count: stoppedGoalCount,
        registry_goal_count: fixture.run_history.goals.length,
        registry_revision: registryRevision,
      };
      fixture.run_history.goals = fixture.run_history.goals.filter((goal) => goal.activation_state === "stopped");
      filterStatusFixtureToScope(fixture, statusGeneration, "stopped");
    } else {
      fixture.goal_projection = {
        schema_version: "loopx_goal_projection_scope_v0",
        scope: "all",
        complete: true,
        projected_goal_count: fixture.run_history.goals.length,
        registry_goal_count: fixture.run_history.goals.length,
        registry_revision: registryRevision,
      };
    }
    await route.fulfill({ contentType: "application/json", json: fixture, status: 200 });
  });
  await page.route("**/periodic-report-workspace?*", async (route) => {
    const requestUrl = new URL(route.request().url());
    const goalId = requestUrl.searchParams.get("goal_id");
    if (requestUrl.searchParams.get("limit") !== "100" || requestUrl.searchParams.get("offset") !== "0") {
      throw new Error("Periodic-report index request did not negotiate a bounded window");
    }
    const items = goalId === periodicReportProjection.goal_id ? [{
      goal_id: periodicReportProjection.goal_id,
      agent_id: periodicReportProjection.agent_id,
      generation_id: periodicReportProjection.generation_id,
      publication_id: periodicReportProjection.publication.publication_id,
      delivered_at: periodicReportProjection.publication.delivered_at,
      predecessor_publication_id: periodicReportProjection.publication.predecessor_publication_id,
      detail_ref: {
        goal_id: periodicReportProjection.goal_id,
        agent_id: periodicReportProjection.agent_id,
        generation_id: periodicReportProjection.generation_id,
        content_sha256: periodicReportProjection.content_sha256,
      },
    }] : [];
    await route.fulfill({
      contentType: "application/json",
      json: {
        ok: true,
        periodic_reports: {
          schema_version: "periodic_report_workspace_index_v0",
          count: items.length,
          returned_count: items.length,
          total_count: items.length,
          limit: 100,
          offset: 0,
          truncated: false,
          items,
        },
      },
      status: 200,
    });
  });
  await page.route("**/periodic-report-workspace-projection?*", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { ok: true, projection: periodicReportProjection }, status: 200 });
  });
  await page.route(`http://127.0.0.1:${port}/api/ssh-source/ensure`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: { ok: true, status_url: "http://127.0.0.1:8876/status.json", tunnel_required: true, remote_started: true },
      status: 200,
    });
  });
  await page.route(`http://127.0.0.1:${port}/ssh-hosts`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ok: true,
        schema_version: "ssh_host_catalog_v0",
        hosts: [{ alias: "remote-lab" }, { alias: "remote-build" }],
      },
      status: 200,
    });
  });
  await page.route("http://127.0.0.1:8876/status.json", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: require(resolve(repoRoot, "examples/status.example.json")),
      status: 200,
    });
  });
  await page.route("http://127.0.0.1:8976/status.json", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: require(resolve(repoRoot, "examples/status.example.json")),
      status: 200,
    });
  });
  await page.route("http://127.0.0.1:8877/status.json", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: require(resolve(repoRoot, "examples/status.example.json")),
      status: 200,
    });
  });
  await page.route("**/api/chat/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === "/api/chat/completed-todos") {
      const total = url.searchParams.get("goal_id") === "progress-projection" ? 4087 : 0;
      const offset = Number(url.searchParams.get("cursor") || 0);
      const items = Array.from({ length: Math.min(40, total - offset) }, (_, position) => {
        const index = offset + position;
        return { todo_id: `todo_history_${index}`, text: index < 3 ? `Completed ${String.fromCharCode(65 + index)}` : `Completed historical Task ${index + 1}`, claimed_by: "example-agent", evidence: null, priority: null, task_class: "advancement_task" };
      });
      await route.fulfill({ json: { ok: true, total, items, next_cursor: offset + 40 < total ? String(offset + 40) : null } });
      return;
    }
    const periodicConfiguration = {
      schema_version: "periodic_report_machine_defaults_v0",
      enabled: true,
      inheritance: "live_machine_default",
      profile_preset: "weekly-progress",
      route_ref: "report-route",
      timezone: "Asia/Shanghai",
    };
    const machineConfigurationBase = {
      ok: true,
      available_namespaces: ["periodic_report"],
      namespace_catalog: {
        schema_version: "machine_configuration_catalog_v0",
        namespaces: [{
          namespace: "periodic_report",
          title: "Periodic reports",
          description: "Governed report defaults.",
          schema_versions: ["periodic_report_machine_defaults_v0"],
          configuration_template: periodicConfiguration,
          template_status: "ready",
        }],
      },
      capability_catalog: {
        schema_version: "capability_configuration_catalog_v0",
        capabilities: goalCapabilityCatalog().map((capability) => capability.capability_id === "periodic_report"
          ? periodicReportCapability({ machineCurrent: periodicConfiguration })
          : capability),
      },
      changed_namespaces: [],
      machine_configuration: {
        schema_version: "loopx_machine_configuration_v0",
        namespaces: { periodic_report: periodicConfiguration },
      },
    };
    if (url.pathname === "/api/chat/machine-configuration" && request.method() === "GET") {
      await route.fulfill({ contentType: "application/json", json: {
        ...machineConfigurationBase,
        schema_version: "machine_configuration_inspection_v0",
        status: "configured",
        revision: "sha256:machine-current",
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/machine-configuration/preview" && request.method() === "POST") {
      const body = request.postDataJSON();
      state.machineConfigurationRequests.push({ phase: "preview", ...body });
      await route.fulfill({ contentType: "application/json", json: {
        ...machineConfigurationBase,
        schema_version: "machine_configuration_update_plan_v0",
        status: "preview",
        action: "update",
        current_revision: "sha256:machine-current",
        desired_revision: "sha256:machine-desired",
        plan_revision: "sha256:machine-plan",
        writes_required: 1,
        changed_namespaces: [body.namespace],
        machine_configuration: {
          schema_version: "loopx_machine_configuration_v0",
          namespaces: { periodic_report: body.namespace_configuration },
        },
      }, status: 201 });
      return;
    }
    if (url.pathname === "/api/chat/machine-configuration/apply" && request.method() === "POST") {
      const body = request.postDataJSON();
      state.machineConfigurationRequests.push({ phase: "apply", ...body });
      await route.fulfill({ contentType: "application/json", json: {
        ...machineConfigurationBase,
        schema_version: "machine_configuration_transaction_v0",
        status: "applied",
        plan_revision: body.expected_plan_revision,
        transaction_id: "machine-transaction",
        readback_verified: true,
        rollback_available: true,
        applied_revision: "sha256:machine-desired",
        prior_revision: "sha256:machine-current",
        changed_namespaces: [body.namespace],
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/goal-configuration" && request.method() === "GET") {
      const goalId = url.searchParams.get("goal_id");
      const spawnPolicy = runtime.goalSubagentConfigurations.get(goalId);
      const multiSubagentConfiguration = spawnPolicy ? {
        enabled: spawnPolicy.mode === "multi_subagent" && spawnPolicy.spawn_allowed === true,
        max_children: spawnPolicy.max_children || null,
        allowed_domains: spawnPolicy.allowed_domains ?? [],
      } : undefined;
      await route.fulfill({ contentType: "application/json", json: {
        ok: true,
        schema_version: "goal_configuration_inspection_v0",
        status: "configured",
        goal_id: goalId,
        revision: "sha256:goal-current",
        available_capabilities: [
          "periodic_report",
          "change_quality_qualification",
          "explore_graph",
          "explore_harness",
          "lark_kanban_heartbeat_sync",
          "lark_event_inbox",
          "peer_task_coordination",
          "multi_subagent",
          "local_authority_shadow",
          "reward_memory",
        ],
        capability_catalog: {
          schema_version: "capability_configuration_catalog_v0",
          capabilities: goalCapabilityCatalog(multiSubagentConfiguration).map((capability) => capability.capability_id === "periodic_report" ? periodicReportCapability({
              machineCurrent: periodicConfiguration,
              effectiveConfiguration: {
                schema_version: "capability_configuration_resolution_v0",
                capability_id: "periodic_report",
                source: "machine_default",
                configuration: periodicConfiguration,
                inherited: true,
                goal_override_present: false,
                machine_default_present: true,
                effective_revision: "sha256:periodic-effective",
              },
            }) : capability),
        },
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/goal-configuration/preview" && request.method() === "POST") {
      const body = request.postDataJSON();
      state.goalConfigurationRequests.push({ phase: "preview", ...body });
      await route.fulfill({ contentType: "application/json", json: {
        ok: true, schema_version: "goal_configuration_update_plan_v0", status: "preview",
        action: body.capability_id === "multi_subagent" && runtime.goalSubagentConfigurations.has(body.goal_id) ? "update" : "create", current_revision: "absent", desired_revision: "sha256:desired",
        base_revision: "sha256:goal-current", plan_revision: `sha256:goal-plan-${body.capability_id}`, writes_required: 1,
        goal_id: body.goal_id, capability_id: body.capability_id,
        changed_fields: [body.capability_id], goal_configuration: body.configuration,
        capability_catalog: { schema_version: "capability_configuration_catalog_v0", capabilities: [] },
      }, status: 201 });
      return;
    }
    if (url.pathname === "/api/chat/goal-configuration/apply" && request.method() === "POST") {
      const body = request.postDataJSON();
      state.goalConfigurationRequests.push({ phase: "apply", ...body });
      if (body.capability_id === "multi_subagent") {
        runtime.goalSubagentConfigurations.set(body.goal_id, body.configuration.enabled ? {
          mode: "multi_subagent",
          spawn_allowed: true,
          max_children: body.configuration.max_children,
          allowed_domains: body.configuration.allowed_domains,
        } : {
          mode: "default",
          spawn_allowed: false,
          max_children: 0,
          allowed_domains: [],
        });
        await route.fulfill({ contentType: "application/json", json: {
          ok: true, schema_version: "goal_configuration_transaction_v0", status: "applied",
          goal_id: body.goal_id, capability_id: body.capability_id,
          plan_revision: body.expected_plan_revision, applied_revision: "sha256:goal-applied",
          readback_verified: true, changed_fields: [body.capability_id], goal_configuration: body.configuration,
          capability_catalog: { schema_version: "capability_configuration_catalog_v0", capabilities: [] },
        }, status: 200 });
        return;
      }
      await route.fulfill({ contentType: "application/json", json: {
        ok: false, schema_version: "goal_configuration_transaction_v0", status: "partial_write",
        goal_id: body.goal_id, capability_id: body.capability_id,
        plan_revision: body.expected_plan_revision, applied_revision: "sha256:goal-applied",
        source_written: true, shared_sync_pending: true, readback_verified: true,
        changed_fields: ["periodic_report"], goal_configuration: body.configuration,
        capability_catalog: { schema_version: "capability_configuration_catalog_v0", capabilities: [] },
        error: "shared projection did not synchronize",
        recommended_action: `rerun loopx sync-global --goal-id ${body.goal_id}`,
      }, status: 207 });
      return;
    }
    const resumedEvents = url.pathname.match(/^\/api\/chat\/sessions\/([^/]+)\/turns\/([^/]+)\/events$/);
    if (resumedEvents && request.method() === "GET") {
      const sessionId = resumedEvents[1];
      const turnId = resumedEvents[2];
      const answer = "已沿用当前 Goal 与 Agent Session。接下来会先核对状态，再继续推进。";
      await new Promise((resolveWait) => setTimeout(resolveWait, /(中断控制|刷新恢复)/u.test(turnMessages.get(turnId) ?? "") ? 5000 : 1200));
      const activeSession = sessions.get(sessionId);
      if (!activeSession || activeSession.active_turn_id !== turnId) {
        await route.fulfill({ contentType: "text/event-stream", body: "", status: 200 });
        return;
      }
      const visible = messages.get(sessionId) ?? [];
      if (!visible.some((message) => message.message_id === `${turnId}-assistant`)) {
        visible.push({ message_id: `${turnId}-assistant`, turn_id: turnId, role: "assistant", text: answer, created_at: "2026-08-13T01:00:02Z" });
      }
      messages.set(sessionId, visible);
      const event = (id, kind, payload) => `id: ${id}\nevent: ${kind}\ndata: ${JSON.stringify({ event_id: id, sequence: Number(id), kind, created_at: "2026-08-13T01:00:02Z", payload })}\n\n`;
      await route.fulfill({ contentType: "text/event-stream", body: event("1", "assistant.delta", { text: answer }) + event("2", "turn.completed", { response: { schema_version: "loopx_chat_agent_response_v0", message: answer, proposals: [], gate: null } }), status: 200 });
      sessions.set(sessionId, { ...activeSession, active_turn_id: null, status: "ready", updated_at: "2026-08-13T01:00:02Z" });
      return;
    }
    if (url.pathname === "/api/chat/goals/contexts") {
      const fixture = require(resolve(repoRoot, "examples/status.example.json"));
      await route.fulfill({ contentType: "application/json", json: {
        ok: true,
        schema_version: "loopx_chat_goal_contexts_v0",
        goals: (fixture.run_history?.goals ?? []).map((goal) => ({
          goal_id: goal.id,
          repository: { branch: "codex/lark-goal-topic-binding", identity: "git:github.com/loopx-ai/loopx", label: "loopx-ai/loopx", read_only: true },
        })),
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/lark/apps") {
      await route.fulfill({ contentType: "application/json", json: {
        ok: true,
        schema_version: "loopx_lark_apps_v0",
        apps: [{ active: true, app_ref: "mew", brand: "feishu", label: "LoopX Mew", ready: true, reply_ready: true }],
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/lark/chats") {
      await route.fulfill({ contentType: "application/json", json: {
        ok: true,
        schema_version: "loopx_lark_group_chats_v0",
        chats: [{ chat_id: "oc_browser_fixture", chat_name: "Product group" }],
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/lark/connections" && request.method() === "GET") {
      await route.fulfill({ contentType: "application/json", json: {
        ok: true,
        schema_version: "loopx_lark_goal_topic_connections_v0",
        connections: runtime.larkConnections,
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/lark/connections" && request.method() === "POST") {
      const body = request.postDataJSON();
      const connectionId = `lark-${body.goal_id}-${body.agent_id ?? "default"}`;
      if (body.execute) {
        const fixture = require(resolve(repoRoot, "examples/status.example.json"));
        const goal = (fixture.run_history?.goals ?? []).find((item) => item.id === body.goal_id);
        runtime.larkConnections = runtime.larkConnections.filter((item) => item.connection_id !== connectionId);
        runtime.larkConnections.push({
          agent_id: body.agent_id ?? null,
          connection_id: connectionId,
          app_label: "LoopX Mew", app_ref: body.app_ref, chat_name: body.chat_name, enabled: true,
          capture_scope: body.capture_scope,
          event_count: 0, health_error_code: "lark_event_delivery_unverified",
          goal_id: body.goal_id, goal_title: goal?.id ?? body.goal_id, incoming_mode: body.incoming_mode,
          ingress_mode: body.ingress_mode,
          last_event_reason: null, last_event_status: null, listener_error_code: null, listener_status: "listening", replied_count: 0,
          reply_mode: "topic_reply", target_ref: "product-group", topic_name: goal?.id ?? body.goal_id,
          topic_setup_required: false, reply_ready: false,
        });
        state.larkWrites.push({ ...body });
      }
      await route.fulfill({ contentType: "application/json", json: {
        ok: true,
        status: body.execute ? "connected" : "preview_ready",
        public_summary: body.execute ? "connected" : "previewed",
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/lark/connections" && request.method() === "DELETE") {
      const connectionId = url.searchParams.get("connection_id");
      runtime.larkConnections = runtime.larkConnections.filter((item) => item.connection_id !== connectionId);
      await route.fulfill({ contentType: "application/json", json: { ok: true, status: "disconnected" }, status: 200 });
      return;
    }
    if (["/api/chat/goal-subagents/dry-run", "/api/chat/goal-subagents/apply"].includes(url.pathname) && request.method() === "POST") {
      if (state.failNextGoalSubagentResponse) {
        state.failNextGoalSubagentResponse = false;
        await route.fulfill({ body: "", contentType: "text/plain", status: 502 });
        return;
      }
      const body = request.postDataJSON();
      const apply = url.pathname.endsWith("/apply");
      const before = runtime.goalSubagentConfigurations.get(body.goal_id)
        ?? { mode: "default", spawn_allowed: false, max_children: 0, allowed_domains: [] };
      const after = body.enabled
        ? { mode: "multi_subagent", spawn_allowed: true, max_children: body.max_children, allowed_domains: body.allowed_domains }
        : { mode: "default", spawn_allowed: false, max_children: 0 };
      const changed = JSON.stringify(before) !== JSON.stringify(after);
      const previewId = `goal-subagents-${body.goal_id}-${JSON.stringify(after)}`;
      if (apply && body.preview_id !== previewId) {
        await route.fulfill({ contentType: "application/json", json: { ok: false, error: "stale Goal sub-agent preview", error_code: "stale_goal_subagent_preview" }, status: 409 });
        return;
      }
      if (apply && changed) {
        runtime.goalSubagentConfigurations.set(body.goal_id, after);
        state.goalSubagentWrites.push({ ...body });
        state.durableWriteCount += 1;
      } else if (!apply) {
        state.goalSubagentPreviews.push({ ...body, preview_id: previewId });
      }
      await route.fulfill({ contentType: "application/json", json: {
        ok: true,
        dry_run: !apply,
        execute: apply,
        written: apply && changed,
        changed,
        goal_id: body.goal_id,
        changed_fields: changed ? ["orchestration"] : [],
        before: { orchestration: before },
        after: { orchestration: after },
        preview_id: previewId,
        feature_summary: { multi_subagent: body.enabled ? "enabled" : "off" },
        global_sync: {
          required: changed,
          executed: apply && changed,
          readback: { status: apply && changed ? "verified" : changed ? "not_executed" : "not_required", verified: apply && changed },
        },
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/capabilities") {
      await route.fulfill({ contentType: "application/json", json: {
        ok: true, schema_version: "loopx_chat_capabilities_v1", agent_backend: "multi_adapter",
        sandbox: "read-only", approval_policy: "never", todo_write: "preview_locked",
        ...(state.goalSubagentConfigurationEnabled ? { goal_subagent_configuration: "preview_locked" } : {}),
        goal_id: null, streaming: true, resume: true, interrupt: true, typed_actions: true,
        action_kinds: ["goal.create", "goal.lifecycle", "agent.bind", "heartbeat.bind", "monitor.create", "run.correct"],
        adapters: [
          { agent_id: "codex", display_name: "Codex", adapter_kind: "codex_app_server", available: true, streaming: true, resume: true, interrupt: true },
          { agent_id: "claude-code", display_name: "Claude Code", adapter_kind: "claude_code_cli", available: true, streaming: true, resume: true, interrupt: true },
          { agent_id: "offline-agent", display_name: "Offline Agent", adapter_kind: "acp", available: false, streaming: false, resume: false, interrupt: false },
        ],
      }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/sessions" && request.method() === "GET") {
      const requestedGoal = url.searchParams.get("goal_id");
      const requestedAgent = url.searchParams.get("agent_id");
      const requestedChannel = url.searchParams.get("channel_id");
      const matched = [...sessions.values()].filter((session) =>
        (!requestedGoal || session.goal_id === requestedGoal)
        && (!requestedAgent || session.agent_id === requestedAgent)
        && (!requestedChannel || session.channel_id === requestedChannel)
      );
      await route.fulfill({ contentType: "application/json", json: { ok: true, schema_version: "loopx_chat_session_list_v1", sessions: matched }, status: 200 });
      return;
    }
    if (url.pathname === "/api/chat/sessions" && request.method() === "POST") {
      const body = request.postDataJSON();
      const session_id = `session-${body.context_kind}-${body.goal_id}-${body.agent_id}`;
      const existing = body.mode === "resume_latest" ? sessions.get(session_id) : null;
      const session = existing ?? { session_id, goal_id: body.goal_id, agent_id: body.agent_id, adapter_kind: body.agent_id, channel_id: body.context_kind === "manager" ? "manager" : `goal.${body.goal_id}`, status: "ready", active_turn_id: null, last_error_code: null, created_at: "2026-08-13T01:00:00Z", updated_at: "2026-08-13T01:00:00Z", last_activity_at: "2026-08-13T01:00:00Z", resumable: true };
      sessions.set(session_id, session);
      messages.set(session_id, messages.get(session_id) ?? []);
      await route.fulfill({ contentType: "application/json", json: { ok: true, agent_id: body.agent_id, goal_id: body.goal_id, resumed: body.mode === "resume_latest", session_id }, status: 201 });
      return;
    }
    const snapshot = url.pathname.match(/^\/api\/chat\/sessions\/([^/]+)$/);
    if (snapshot && request.method() === "GET") {
      const session = sessions.get(snapshot[1]);
      await route.fulfill({ contentType: "application/json", json: { ok: true, schema_version: "loopx_chat_store_v1", session, messages: messages.get(snapshot[1]) ?? [], active_turn: null }, status: session ? 200 : 404 });
      return;
    }
    const turns = url.pathname.match(/^\/api\/chat\/sessions\/([^/]+)\/turns$/);
    if (turns && request.method() === "POST") {
      const body = request.postDataJSON();
      const turn_id = `turn-${Date.now()}`;
      turnMessages.set(turn_id, body.message);
      const current = sessions.get(turns[1]);
      if (current) sessions.set(turns[1], { ...current, active_turn_id: turn_id, status: "busy", updated_at: "2026-08-13T01:00:01Z" });
      messages.get(turns[1])?.push({ message_id: `${turn_id}-user`, turn_id, role: "user", text: body.message, created_at: "2026-08-13T01:00:01Z" });
      state.turnRequests.push({ message: body.message, sessionId: turns[1], turnId: turn_id });
      await route.fulfill({ contentType: "application/json", json: { ok: true, session_id: turns[1], turn_id, created: true, status: "running", events_url: `/events/${turns[1]}/${turn_id}` }, status: 202 });
      return;
    }
    const interrupt = url.pathname.match(/^\/api\/chat\/sessions\/([^/]+)\/turns\/([^/]+)\/interrupt$/);
    if (interrupt && request.method() === "POST") {
      const current = sessions.get(interrupt[1]);
      if (current) sessions.set(interrupt[1], { ...current, active_turn_id: null, status: "ready", updated_at: "2026-08-13T01:00:02Z" });
      state.interrupts.push({ sessionId: interrupt[1], turnId: interrupt[2] });
      await route.fulfill({ contentType: "application/json", json: { ok: true, session_id: interrupt[1], turn_id: interrupt[2], status: "interrupted" }, status: 200 });
      return;
    }
    await route.fulfill({ contentType: "application/json", json: { ok: true }, status: 200 });
  });
  await page.route("**/events/**", async (route) => {
    const parts = new URL(route.request().url()).pathname.split("/").filter(Boolean);
    const sessionId = parts[1];
    const turnId = parts[2];
    const operatorMessage = turnMessages.get(turnId) ?? "";
    const protectedAction = operatorMessage === "请合并 PR #123"
      ? { operation: "merge", target: "PR #123", summary: "准备 PR #123 的受保护合并预览。" }
      : operatorMessage === "请合并我刚才说的那个"
        ? { operation: "merge", target: "PR #999", summary: "模型错误补出了用户没有提供的目标。" }
      : null;
    const answer = operatorMessage === "请只回复：合并后真实回复已收到"
      ? "合并后真实回复已收到"
      : operatorMessage === "请分析：合并 PR #123 后会有什么风险"
        ? "主要风险是检查未完成或目标分支发生变化；这里只做分析，不会创建合并预览。"
          : operatorMessage === "请合并"
            ? "请告诉我要合并的具体 PR 或 MR；在目标明确前不会创建执行预览。"
          : operatorMessage === "请合并我刚才说的那个"
            ? "这个指代不够明确，请提供具体 PR 或 MR。"
          : protectedAction
            ? "我识别到一个明确的合并请求。LoopX 会先展示受保护操作预览，不会直接执行。"
            : "已沿用当前 Goal 与 Agent Session。接下来会先核对状态，再继续推进。";
    await new Promise((resolveWait) => setTimeout(resolveWait, /(中断控制|刷新恢复)/u.test(operatorMessage) ? 5000 : 1200));
    const activeSession = sessions.get(sessionId);
    if (!activeSession || activeSession.active_turn_id !== turnId) {
      await route.fulfill({ contentType: "text/event-stream", body: "", status: 200 });
      return;
    }
    if (sessionId && messages.has(sessionId)) {
      const visible = messages.get(sessionId);
      if (!visible.some((message) => message.message_id === `${turnId}-assistant`)) {
        visible.push({ message_id: `${turnId}-assistant`, turn_id: turnId, role: "assistant", text: answer, created_at: "2026-08-13T01:00:02Z" });
      }
    }
    const event = (id, kind, payload) => `id: ${id}\nevent: ${kind}\ndata: ${JSON.stringify({ event_id: id, sequence: Number(id), kind, created_at: "2026-08-13T01:00:02Z", payload })}\n\n`;
    await route.fulfill({ contentType: "text/event-stream", body: event("1", "assistant.delta", { text: answer }) + event("2", "turn.completed", { response: { schema_version: "loopx_chat_agent_response_v0", message: answer, proposals: [], protected_action: protectedAction, gate: null } }), status: 200 });
    const current = sessions.get(sessionId);
    if (current?.active_turn_id === turnId) sessions.set(sessionId, { ...current, active_turn_id: null, status: "ready", updated_at: "2026-08-13T01:00:02Z" });
  });
  await page.route("**/api/actions?**", async (route) => {
    const url = new URL(route.request().url());
    const goalId = url.searchParams.get("goal_id");
    const contextKind = url.searchParams.get("context_kind");
    const proposals = Array.from(actionProposals.values()).filter((proposal) => {
      if (proposal.status === "cancelled") return false;
      if (goalId && (proposal.context?.goal_id ?? proposal.normalized_parameters?.goal_id) !== goalId) return false;
      return !contextKind || proposal.context?.kind === contextKind;
    });
    await route.fulfill({ contentType: "application/json", json: { ok: true, schema_version: "loopx_chat_action_list_v1", proposals }, status: 200 });
  });
  await page.route("**/api/actions/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === "/api/actions/preview") {
      const body = request.postDataJSON();
      const actionDelayMs = state.nextActionPreviewDelayMs;
      state.nextActionPreviewDelayMs = 0;
      const lifecycleDelayMs = body.action_kind === "goal.lifecycle" ? state.nextLifecyclePreviewDelayMs : 0;
      state.nextLifecyclePreviewDelayMs = 0;
      const previewDelayMs = Math.max(actionDelayMs, lifecycleDelayMs);
      if (previewDelayMs > 0) await new Promise((resolveWait) => setTimeout(resolveWait, previewDelayMs));
      if (state.failNextActionPreview) {
        state.failNextActionPreview = false;
        await route.fulfill({
          contentType: "application/json",
          json: { error: "Action preview temporarily unavailable", error_code: "preview_unavailable", ok: false },
          status: 503,
        });
        return;
      }
      if (body.action_kind === "goal.lifecycle" && state.failNextLifecyclePreview) {
        state.failNextLifecyclePreview = false;
        await route.fulfill({
          contentType: "application/json",
          json: { error: "Lifecycle preview temporarily unavailable", error_code: "preview_unavailable", ok: false },
          status: 503,
        });
        return;
      }
      const proposal_id = `proposal-${body.idempotency_key}`;
      actionKinds.set(proposal_id, body.action_kind);
      state.actionPreviews.push({ ...body, proposalId: proposal_id });
      const proposal = {
        schema_version: "loopx_chat_action_proposal_v1", proposal_id, action_kind: body.action_kind,
        summary: body.summary, normalized_parameters: body.normalized_parameters, context: body.context,
        expected_state_fingerprint: "fixture-r1", permission_classification: "durable_write",
        validation_evidence: ["fixture validation"], available_transitions: ["apply", "cancel"],
        status: "preview_ready", receipt: null, stale: null, created_at: "2026-08-13T01:00:00Z", updated_at: "2026-08-13T01:00:00Z",
      };
      actionProposals.set(proposal_id, proposal);
      await route.fulfill({ contentType: "application/json", json: { ok: true, proposal }, status: 201 });
      return;
    }
    const apply = url.pathname.match(/^\/api\/actions\/(.+)\/apply$/);
    if (apply) {
      state.actionApplies.push(apply[1]);
      if (actionKinds.get(apply[1]) === "heartbeat.bind" && !state.allowNextHeartbeatApply) {
        await route.fulfill({ contentType: "application/json", json: { ok: false, schema_version: "loopx_chat_action_gate_v1", error: "Host activation required", error_code: "protected_action", gate: { kind: "host_activation_required", summary: "需要 Codex App 宿主创建 Heartbeat 自动化。", next_action: "确认宿主自动化后重新验证。" }, write_attempted: false }, status: 409 });
        return;
      }
      if (actionKinds.get(apply[1]) === "heartbeat.bind") state.allowNextHeartbeatApply = false;
      const actionKind = actionKinds.get(apply[1]) ?? "goal.create";
      const preview = state.actionPreviews.find((item) => item.proposalId === apply[1]);
      const lifecycleDelayMs = actionKind === "goal.lifecycle" ? state.nextLifecycleApplyDelayMs : 0;
      state.nextLifecycleApplyDelayMs = 0;
      if (lifecycleDelayMs > 0) await new Promise((resolveWait) => setTimeout(resolveWait, lifecycleDelayMs));
      if (actionKind === "goal.lifecycle" && state.failNextLifecycleApply) {
        state.failNextLifecycleApply = false;
        await route.fulfill({
          contentType: "application/json",
          json: {
            error: "Lifecycle gate changed before apply",
            error_code: "protected_action",
            gate: { kind: "goal_lifecycle_gate", summary: "Goal 状态已变化，请重新确认。" },
            ok: false,
            write_attempted: false,
          },
          status: 409,
        });
        return;
      }
      let acceptedTurn = null;
      if (actionKind === "run.correct" && preview) {
        const sessionId = preview.normalized_parameters.session_id;
        const turnId = `turn-${++turnCounter}`;
        acceptedTurn = { session_id: sessionId, turn_id: turnId, status: "queued", created: true };
        turnMessages.set(turnId, preview.normalized_parameters.message);
        state.turnRequests.push({ message: preview.normalized_parameters.message, sessionId, turnId });
        const active = sessions.get(sessionId) ?? {
          session_id: sessionId,
          goal_id: preview.normalized_parameters.goal_id,
          agent_id: "codex",
          adapter_kind: "codex",
          channel_id: `goal.${preview.normalized_parameters.goal_id}`,
          active_turn_id: null,
          status: "ready",
          resumable: true,
        };
        sessions.set(sessionId, { ...active, active_turn_id: turnId, status: "busy" });
        const sessionMessages = messages.get(sessionId) ?? [];
        sessionMessages.push({ message_id: `${turnId}-user`, turn_id: turnId, role: "user", text: preview.normalized_parameters.message, created_at: "2026-08-13T01:00:01Z" });
        messages.set(sessionId, sessionMessages);
      }
      if (actionKind === "goal.lifecycle" && preview) {
        state.goalActivationStates.set(
          preview.normalized_parameters.goal_id,
          preview.normalized_parameters.operation === "stop" ? "stopped" : "active",
        );
      }
      const resourceKey = `${actionKind}:${apply[1]}`;
      if (!state.durableResources.has(resourceKey)) {
        state.durableResources.add(resourceKey);
        state.durableWriteCount += 1;
      }
      const proposal = {
        schema_version: "loopx_chat_action_proposal_v1", proposal_id: apply[1], action_kind: actionKind,
        summary: "已应用", normalized_parameters: preview?.normalized_parameters ?? {}, context: preview?.context ?? {}, expected_state_fingerprint: "fixture-r1",
        permission_classification: "durable_write", validation_evidence: [], available_transitions: ["apply", "cancel"],
        status: "applied", receipt: { projection_verified: true, receipt_id: "fixture-receipt" }, stale: null, created_at: "2026-08-13T01:00:00Z", updated_at: "2026-08-13T01:00:01Z",
      };
      actionProposals.set(apply[1], proposal);
      await route.fulfill({ contentType: "application/json", json: { ok: true, proposal, turn: acceptedTurn }, status: acceptedTurn ? 202 : 200 });
      return;
    }
    const cancel = url.pathname.match(/^\/api\/actions\/(.+)\/cancel$/);
    if (cancel) {
      state.actionCancels.push(cancel[1]);
      const proposal = {
        schema_version: "loopx_chat_action_proposal_v1", proposal_id: cancel[1], action_kind: actionKinds.get(cancel[1]) ?? "goal.create",
        summary: "已取消", normalized_parameters: {}, context: {}, expected_state_fingerprint: "fixture-r1",
        permission_classification: "durable_write", validation_evidence: [], available_transitions: ["apply", "cancel"],
        status: "cancelled", receipt: null, stale: null, created_at: "2026-08-13T01:00:00Z", updated_at: "2026-08-13T01:00:01Z",
      };
      actionProposals.set(cancel[1], proposal);
      await route.fulfill({ contentType: "application/json", json: { ok: true, proposal }, status: 200 });
      return;
    }
    const transition = url.pathname.match(/^\/api\/actions\/(.+)\/(defer|reject|regenerate)$/);
    if (transition) {
      const existing = actionProposals.get(transition[1]);
      const nextId = transition[2] === "regenerate" ? `${transition[1]}-regenerated` : transition[1];
      const proposal = {
        ...(existing ?? {}),
        schema_version: "loopx_chat_action_proposal_v1",
        proposal_id: nextId,
        action_kind: existing?.action_kind ?? actionKinds.get(transition[1]) ?? "goal.create",
        summary: existing?.summary ?? "已更新决定",
        normalized_parameters: existing?.normalized_parameters ?? {},
        context: existing?.context ?? {},
        expected_state_fingerprint: "fixture-r1",
        permission_classification: "durable_write",
        validation_evidence: [],
        available_transitions: ["apply", "cancel"],
        status: transition[2] === "defer" ? "deferred" : transition[2] === "reject" ? "rejected" : "preview_ready",
        receipt: null,
        stale: null,
        created_at: existing?.created_at ?? "2026-08-13T01:00:00Z",
        updated_at: "2026-08-13T01:00:01Z",
      };
      actionProposals.set(nextId, proposal);
      state.actionTransitions.push({ proposalId: transition[1], transition: transition[2] });
      await route.fulfill({ contentType: "application/json", json: { ok: true, proposal }, status: 200 });
      return;
    }
    await route.fulfill({ contentType: "application/json", json: { ok: true }, status: 200 });
  });
  return state;
}

async function main() {
  const { chromium } = loadPlaywright();
  await mkdir(outputDir, { recursive: true });
  const results = new Map(Array.from({ length: 24 }, (_, index) => [index + 1, { status: "UNTESTED", note: "" }]));
  const observations = [];
  const pass = (criterion, note) => results.set(criterion, { status: "PASS", note });
  const fail = (criterion, note) => results.set(criterion, { status: "FAIL", note });
  const server = startServer();
  let browser;
  try {
    const url = `http://127.0.0.1:${port}/${packaged ? "chat/" : ""}?statusUrl=/status.json`;
    await waitForHttp(url);
    browser = await launchBrowser(chromium);
    const capabilityOffPage = await browser.newPage({ viewport: { width: 1512, height: 982 } });
    await installApi(capabilityOffPage, { goalSubagentConfigurationEnabled: false });
    await capabilityOffPage.goto(url, { waitUntil: "networkidle" });
    await capabilityOffPage.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 15_000 });
    await capabilityOffPage.locator(".personal-goal-link").first().click();
    await capabilityOffPage.getByRole("button", { name: "打开 Goal 详情或能力配置" }).click();
    await capabilityOffPage.getByRole("group", { name: "Goal 设置" }).getByRole("button", { name: /Goal 详情/ }).click();
    await capabilityOffPage.locator(".personal-drawer-header").waitFor({ state: "visible" });
    if (await capabilityOffPage.locator(".personal-goal-subagents").count()) {
      throw new Error("Capability-off Dashboard exposed Goal sub-agent controls");
    }
    await capabilityOffPage.close();
    const page = await browser.newPage({ viewport: { width: 1512, height: 982 } });
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") pageErrors.push(message.text());
    });
    const api = await installApi(page);
    await page.goto(url, { waitUntil: "networkidle" });
    try {
      await page.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 15_000 });
    } catch (error) {
      throw new Error(`${error.message}; url=${page.url()}; errors=${pageErrors.join(" | ")}; body=${(await page.locator("body").innerText()).slice(0, 1000)}`);
    }
    const body = await page.locator("body").innerText();
    for (const text of ["LoopX 管家", "需要你", "执行中", "观察中", "已安排", "历史", "GOALS", "Codex"]) {
      if (!body.includes(text)) {
        await page.screenshot({ path: resolve(outputDir, "desktop-first-screen-failed.png"), fullPage: false, animations: "disabled" });
        throw new Error(`First screen missing ${text}; body=${body.slice(0, 2000)}`);
      }
    }
    if (await page.locator(".personal-home-lane").count() !== 4) throw new Error("Manager home did not render four active lanes");
    if (body.includes("接下来")) throw new Error("Manager home still exposes the ambiguous 接下来 label");
    if (body.includes("stale-browser-goal")) throw new Error("An unregistered historical Goal remained interactive");
    if (!(await page.locator(".personal-home-history").first().isVisible())) throw new Error("Completed Goals are not available through the collapsed history section");
    const needsYouCount = await page.getByTestId("personal-home-lane-needs_you").locator(".personal-home-goal-card").count();
    const greeting = await page.locator(".personal-manager-greeting").innerText();
    if (!greeting.includes(`你有 ${needsYouCount} 项需要处理`)) {
      throw new Error(`Manager greeting count disagrees with the needs-you lane: count=${needsYouCount}; greeting=${greeting}`);
    }
    if (await page.locator(".personal-manager-channels").count()) throw new Error("Sidebar still exposes state lanes as duplicate navigation channels");
    if (await page.locator(".personal-digest-stats button").count()) throw new Error("Away digest still behaves like hidden channel navigation");
    if (body.includes("Agent 设置")) throw new Error("Sidebar still exposes the read-only Agent settings dead end");
    if (await page.locator(".personal-global-rail").count()) throw new Error("Old icon rail is visible");
    if ((await page.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 5) throw new Error("Active Goal directory did not exclude stopped Goals");
    const stoppedDirectory = page.locator(".personal-stopped-goals");
    // Real pointer gestures against the shipped sidebar, not synthetic drag events.
    const activeRows = page.locator('.personal-goal-list:not(.is-stopped) .personal-goal-row');
    const readOrder = () => activeRows.evaluateAll(rows => rows.map(row => row.dataset.reorderGoal));
    const initialOrder = await readOrder();
    const firstLink = activeRows.nth(0).locator('.personal-goal-link');
    const start = await firstLink.boundingBox();
    const end = await activeRows.nth(2).boundingBox();
    const beforeDragUrl = page.url();
    await page.mouse.move(start.x + 40, start.y + start.height / 2);
    await page.mouse.down();
    await page.mouse.move(end.x + 40, end.y + end.height - 4, { steps: 12 });
    await page.locator('.is-drop-after').waitFor();
    await page.mouse.up();
    const expectedOrder = [initialOrder[1], initialOrder[2], initialOrder[0], ...initialOrder.slice(3)];
    if (JSON.stringify(await readOrder()) !== JSON.stringify(expectedOrder)) throw new Error('Pointer Goal reorder failed');
    if (page.url() !== beforeDragUrl) throw new Error('Dragging accidentally selected a Goal');
    await page.reload({ waitUntil: 'networkidle' });
    if (JSON.stringify(await readOrder()) !== JSON.stringify(expectedOrder)) throw new Error('Goal order did not survive reload');
    // Escape cancels rather than committing a partially completed gesture.
    const cancelStart = await activeRows.first().locator('.personal-goal-link').boundingBox();
    const cancelEnd = await activeRows.nth(2).boundingBox();
    await activeRows.first().locator('.personal-goal-link').focus();
    await page.mouse.move(cancelStart.x + 40, cancelStart.y + 20);
    await page.mouse.down();
    await page.mouse.move(cancelEnd.x + 40, cancelEnd.y + cancelEnd.height - 4, { steps: 8 });
    await page.keyboard.press('Escape');
    await page.mouse.up();
    if (JSON.stringify(await readOrder()) !== JSON.stringify(expectedOrder)) throw new Error('Cancelled drag changed order');
    await page.getByRole('button', { name: '调整 Goal 顺序', exact: true }).click();
    const up = activeRows.nth(2).getByRole('button', { name: /^上移 / });
    await up.focus();
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    if (JSON.stringify(await readOrder()) !== JSON.stringify(initialOrder)) throw new Error('Keyboard Goal reorder failed or lost focus');
    if (!(await activeRows.first().getByRole('button', { name: /^上移 / }).isDisabled())) throw new Error('First Goal can move beyond list boundary');
    await page.screenshot({ path: resolve(outputDir, 'goal-reorder-controls.png'), fullPage: false, animations: 'disabled' });
    await page.getByRole('button', { name: '调整 Goal 顺序', exact: true }).click();
    await page.screenshot({ path: resolve(outputDir, 'goal-reorder-default.png'), fullPage: false, animations: 'disabled' });
    if (!(await stoppedDirectory.isVisible()) || await stoppedDirectory.getAttribute("open") !== null) throw new Error("Stopped Goals are not available in a collapsed directory section");
    await page.waitForFunction(() => document.querySelectorAll(".personal-stopped-goals .personal-goal-row").length === 2, null, { timeout: 3_000 });
    await stoppedDirectory.locator("summary").click();
    await page.locator(".personal-goal-link").filter({ hasText: "Legacy Benchmark" }).click();
    await page.waitForFunction(() => new URL(window.location.href).searchParams.get("goalId") === "legacy-benchmark");
    const stoppedGoalBody = await page.locator(".personal-channel").innerText();
    if (!stoppedGoalBody.includes("Legacy Benchmark") || !stoppedGoalBody.includes("历史、Todo 和证据仍保留")) {
      throw new Error(`Stopped Goal lost its archive context after merge: ${stoppedGoalBody.slice(0, 1200)}`);
    }
    await page.locator(".personal-goal-link").filter({ hasText: "Product Release" }).click();
    await stoppedDirectory.locator("summary").click();
    const writesBeforeLifecyclePreview = api.durableWriteCount;
    const statusRequestsBeforeStop = api.statusRequestCount;
    api.nextLifecyclePreviewDelayMs = 900;
    api.nextLifecycleApplyDelayMs = 900;
    api.nextStatusDelayMs = 900;
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).click();
    await page.waitForFunction(
      () => document.querySelectorAll(".personal-goal-list:not(.is-stopped) .personal-goal-row").length === 4,
      null,
      { timeout: 600 },
    );
    const pendingStop = page.locator('.personal-stopped-goals .personal-goal-lifecycle[aria-label="恢复 Product Release"]');
    if (await pendingStop.getAttribute("aria-busy") !== "true") throw new Error("Pending Goal stop does not expose accessible progress");
    await page.waitForTimeout(1_000);
    const stopPreview = api.actionPreviews.findLast((preview) => preview.action_kind === "goal.lifecycle" && preview.normalized_parameters.operation === "stop");
    if (!stopPreview || stopPreview.normalized_parameters.goal_id !== "product-release") throw new Error("Goal stop did not create the expected typed preview");
    if (api.durableWriteCount !== writesBeforeLifecyclePreview) throw new Error("Goal stop wrote durable state before its typed apply completed");
    if (await page.getByText("确认执行", { exact: true }).count()) throw new Error("Goal stop still opened a redundant confirmation drawer");
    if ((await page.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 4) throw new Error("Optimistic Goal stop did not update the active sidebar immediately");
    await page.waitForTimeout(2_000);
    if (api.statusRequestCount <= statusRequestsBeforeStop) throw new Error("Successful Goal stop did not start background full-status reconciliation");
    if ((await page.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 4) throw new Error("Full-status reconciliation reverted a successful Goal stop");
    await stoppedDirectory.locator("summary").click();
    await page.getByRole("button", { name: "恢复 Product Release", exact: true }).click();
    await page.getByText("确认执行", { exact: true }).waitFor({ state: "visible" });
    const resumePreview = api.actionPreviews.findLast((preview) => preview.action_kind === "goal.lifecycle" && preview.normalized_parameters.operation === "resume");
    if (!resumePreview || resumePreview.normalized_parameters.goal_id !== "product-release") throw new Error("Goal resume did not create the expected typed preview");
    if (api.durableWriteCount !== writesBeforeLifecyclePreview + 1) throw new Error("Goal resume preview wrote state before owner confirmation");
    api.nextLifecycleApplyDelayMs = 900;
    await page.getByRole("button", { name: "恢复 Goal", exact: true }).click();
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).waitFor({ state: "attached", timeout: 600 });
    await page.waitForTimeout(1_100);
    if ((await page.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 5) throw new Error("Full-status reconciliation reverted a successful Goal resume");

    api.nextStatusDelayMs = 1_600;
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).click();
    await page.getByRole("button", { name: "恢复 Product Release", exact: true }).waitFor({ state: "attached" });
    await page.getByRole("button", { name: "恢复 Product Release", exact: true }).click();
    await page.getByText("确认执行", { exact: true }).waitFor({ state: "visible" });
    await page.getByRole("button", { name: "恢复 Goal", exact: true }).click();
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).waitFor({ state: "attached" });
    await page.waitForTimeout(1_800);
    if ((await page.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 5) throw new Error("A stale background response overwrote a newer optimistic Goal transition");

    api.failNextLifecyclePreview = true;
    api.nextLifecyclePreviewDelayMs = 900;
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).click();
    await page.getByRole("button", { name: "恢复 Product Release", exact: true }).waitFor({ state: "attached", timeout: 600 });
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).waitFor({ state: "attached", timeout: 2_000 });
    if (api.goalActivationStates.get("product-release") !== "active") throw new Error("Rejected Goal stop preview mutated the durable fixture state");

    api.failNextLifecycleApply = true;
    api.nextLifecycleApplyDelayMs = 900;
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).click();
    await page.getByRole("button", { name: "恢复 Product Release", exact: true }).waitFor({ state: "attached", timeout: 600 });
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).waitFor({ state: "attached", timeout: 2_000 });
    if (api.goalActivationStates.get("product-release") !== "active") throw new Error("Rejected Goal stop mutated the durable fixture state");
    api.failNextStatusRequest = true;
    api.nextStatusDelayMs = 400;
    await page.getByRole("button", { name: "停止 Product Release", exact: true }).click();
    await page.waitForTimeout(900);
    if (await page.getByText("无法读取状态", { exact: false }).count()) throw new Error("Background lifecycle reconciliation replaced the workspace with a fatal status error");
    if ((await page.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 4) throw new Error("Background reconciliation failure reverted the successful optimistic Goal state");
    const closeLifecycleDrawer = page.getByRole("button", { name: "关闭", exact: true });
    if (await closeLifecycleDrawer.count()) await closeLifecycleDrawer.click();
    await page.emulateMedia({ reducedMotion: "reduce" });
    const stoppedChevronTransition = await stoppedDirectory.locator("summary > svg:first-child").evaluate((element) => getComputedStyle(element).transitionDuration);
    if (stoppedChevronTransition !== "0s") throw new Error(`Stopped Goals disclosure ignores reduced motion: ${stoppedChevronTransition}`);
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.screenshot({ path: resolve(outputDir, "goal-lifecycle-directory.png"), fullPage: false, animations: "disabled" });
    pass(1, "Goal stop applies directly without a redundant confirmation, while resume stays reviewed; both update optimistically, roll back rejected applies, and reconcile status in the background.");
    if (await page.locator(".personal-timeline-row").filter({ hasText: /纠偏/u }).count()) throw new Error("Browse rows expose repeated correction actions");
    pass(2, "Browse rows are full-row click targets and Session rows state that they open execution progress and results.");
    const workspaceSettingsEntry = page.getByRole("button", { name: "设置", exact: true });
    const settingsEntryVisual = await workspaceSettingsEntry.evaluate((element) => {
      const style = getComputedStyle(element);
      const icon = element.querySelector(".personal-sidebar-utility-icon")?.getBoundingClientRect();
      const rect = element.getBoundingClientRect();
      return {
        backgroundColor: style.backgroundColor,
        borderTopWidth: style.borderTopWidth,
        height: rect.height,
        iconHeight: icon?.height ?? 0,
        width: rect.width,
      };
    });
    if (settingsEntryVisual.height < 52 || settingsEntryVisual.iconHeight < 32 || settingsEntryVisual.width < 180) {
      throw new Error(`Settings entry is not a prominent navigation target: ${JSON.stringify(settingsEntryVisual)}`);
    }
    if (settingsEntryVisual.borderTopWidth === "0px" || settingsEntryVisual.backgroundColor === "rgba(0, 0, 0, 0)") {
      throw new Error(`Settings entry still renders as a weak transparent footer row: ${JSON.stringify(settingsEntryVisual)}`);
    }
    await page.screenshot({ path: resolve(outputDir, "desktop-first-screen.png"), fullPage: false, animations: "disabled" });
    pass(4, "First viewport exposes needs-you, running, observing, and scheduled Goal lanes with collapsed history.");
    pass(15, "Desktop viewport matches the approved single-sidebar/channel/drawer composition.");

    await page.locator(".personal-goal-link").first().click();
    await page.getByRole("button", { name: "打开 Goal 详情或能力配置" }).click();
    await page.getByRole("group", { name: "Goal 设置" }).getByRole("button", { name: /Goal 详情/ }).click();
    const drawerHeaderVisual = await page.locator(".personal-drawer-header").evaluate((element) => {
      const close = element.querySelector(".personal-drawer-close")?.getBoundingClientRect();
      const header = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        closeHeight: close?.height ?? 0,
        closeTopInset: close ? close.top - header.top : 0,
        closeWidth: close?.width ?? 0,
        headerHeight: header.height,
        paddingTop: Number.parseFloat(style.paddingTop),
      };
    });
    if (drawerHeaderVisual.closeHeight < 44 || drawerHeaderVisual.closeWidth < 44) {
      throw new Error(`Goal drawer close control is below the 44px target: ${JSON.stringify(drawerHeaderVisual)}`);
    }
    if (drawerHeaderVisual.headerHeight < 84 || drawerHeaderVisual.paddingTop < 18 || drawerHeaderVisual.closeTopInset < 18) {
      throw new Error(`Goal drawer header is still pinned too close to the top edge: ${JSON.stringify(drawerHeaderVisual)}`);
    }
    const goalDrawerOrder = await page.locator(".personal-drawer-body").evaluate((element) => {
      const lark = element.querySelector(".personal-goal-notification");
      const session = element.querySelector(".personal-goal-session");
      const actions = element.querySelector(".personal-drawer-action-grid");
      const subagents = element.querySelector(".personal-goal-subagents");
      const precedes = (earlier, later) => Boolean(earlier && later
        && (earlier.compareDocumentPosition(later) & Node.DOCUMENT_POSITION_FOLLOWING));
      return {
        actionsBeforeSubagents: precedes(actions, subagents),
        larkBeforeSession: precedes(lark, session),
        sessionBeforeSubagents: precedes(session, subagents),
        subagentsLast: subagents?.nextElementSibling === null,
      };
    });
    if (!goalDrawerOrder.larkBeforeSession
      || !goalDrawerOrder.sessionBeforeSubagents
      || !goalDrawerOrder.actionsBeforeSubagents
      || !goalDrawerOrder.subagentsLast) {
      throw new Error(`Goal drawer did not keep Lark and Session ahead of advanced sub-agent settings: ${JSON.stringify(goalDrawerOrder)}`);
    }
    const subagentSwitch = page.getByRole("switch", { name: "预览开启子代理执行" });
    await subagentSwitch.waitFor({ state: "visible" });
    if (await subagentSwitch.getAttribute("aria-checked") !== "false") throw new Error("Per-Goal sub-agent execution did not default off");
    if (!(await subagentSwitch.isEnabled())) throw new Error("Per-Goal sub-agent execution still required a task-domain selection");
    await page.getByLabel("最多子代理数").selectOption("2");
    const writesBeforeSubagentPreview = api.durableWriteCount;
    api.freezeGoalSubagentStatusProjection = true;
    await subagentSwitch.click();
    await page.getByText("预览已锁定，确认后才会写入这个 Goal。", { exact: true }).waitFor({ state: "visible" });
    if (api.durableWriteCount !== writesBeforeSubagentPreview) throw new Error("Unrestricted sub-agent preview mutated durable Goal state");
    if (api.goalSubagentPreviews.at(-1)?.allowed_domains.length !== 0) throw new Error("Unrestricted sub-agent preview invented a task-domain filter");
    await page.getByText("最多允许创建 2 个子代理；任务领域限制：不限制任务领域。", { exact: true }).waitFor({ state: "visible" });
    const previewPlacement = await page.locator(".personal-goal-subagents").evaluate((element) => {
      const preview = element.querySelector(".personal-subagent-preview");
      const currentSummary = element.querySelector("dl");
      const switchBounds = element.querySelector(".personal-subagent-switch")?.getBoundingClientRect();
      const previewBounds = preview?.getBoundingClientRect();
      return {
        gapFromSwitch: switchBounds && previewBounds ? previewBounds.top - switchBounds.bottom : Number.POSITIVE_INFINITY,
        previewBeforeCurrentSummary: Boolean(preview && currentSummary
          && (preview.compareDocumentPosition(currentSummary) & Node.DOCUMENT_POSITION_FOLLOWING)),
      };
    });
    if (!previewPlacement.previewBeforeCurrentSummary || previewPlacement.gapFromSwitch > 150) {
      throw new Error(`Sub-agent confirmation is detached from its switch: ${JSON.stringify(previewPlacement)}`);
    }
    await page.locator(".personal-subagent-preview").getByRole("button", { name: "确认", exact: true }).click();
    await page.getByText("已写入，并通过共享 Goal 状态读回校验。", { exact: true }).waitFor({ state: "visible" });
    const enabledSubagentSwitch = page.getByRole("switch", { name: "预览关闭子代理执行" });
    await enabledSubagentSwitch.waitFor({ state: "visible" });
    if (await enabledSubagentSwitch.getAttribute("aria-checked") !== "true") throw new Error("Verified apply receipt did not keep the per-Goal switch on while the status projection remained stale");
    if (api.durableWriteCount !== writesBeforeSubagentPreview + 1) throw new Error("Unrestricted sub-agent apply did not produce exactly one durable Goal write");
    api.freezeGoalSubagentStatusProjection = false;
    const echoedStatusResponse = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/status.json",
    );
    await page.getByRole("button", { name: "刷新状态", exact: true }).click();
    await echoedStatusResponse;
    const configuredGoalId = api.goalSubagentPreviews.at(-1)?.goal_id;
    if (!configuredGoalId) throw new Error("Sub-agent apply did not retain its Goal identity");
    api.goalSubagentConfigurations.set(configuredGoalId, {
      mode: "multi_subagent",
      spawn_allowed: true,
      max_children: 3,
      allowed_domains: ["validation"],
    });
    const supersedingStatusResponse = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/status.json",
    );
    await page.getByRole("button", { name: "刷新状态", exact: true }).click();
    await supersedingStatusResponse;
    const maxChildrenInput = page.getByLabel("最多子代理数");
    try {
      await waitForInputValue(maxChildrenInput, "3");
    } catch (error) {
      throw new Error(
        `${error instanceof Error ? error.message : String(error)}; preview=${JSON.stringify(api.goalSubagentPreviews.at(-1))}; authoritative=${JSON.stringify(api.goalSubagentConfigurations.get(configuredGoalId))}`,
      );
    }
    const supersededMaxChildren = await maxChildrenInput.inputValue();
    if (supersededMaxChildren !== "3") {
      throw new Error(
        `A later authoritative status did not supersede the verified apply receipt: max_children=${supersededMaxChildren}, status_requests=${api.statusRequestCount}, preview=${JSON.stringify(api.goalSubagentPreviews.at(-1))}, authoritative=${JSON.stringify(api.goalSubagentConfigurations.get(configuredGoalId))}`,
      );
    }
    if (!(await page.getByRole("checkbox", { name: /validation/u }).isChecked())) {
      throw new Error("The superseding authoritative status did not update allowed domains");
    }
    if (api.durableWriteCount !== writesBeforeSubagentPreview + 1) throw new Error("Status supersession produced a durable write");

    const codeDomain = page.getByRole("checkbox", { name: /code/u });
    const validationDomain = page.getByRole("checkbox", { name: /validation/u });
    await codeDomain.waitFor({ state: "visible" });
    await validationDomain.waitFor({ state: "visible" });
    await codeDomain.check();
    await validationDomain.check();
    await page.getByRole("button", { name: "预览边界调整", exact: true }).click();
    await page.getByText("预览已锁定，确认后才会写入这个 Goal。", { exact: true }).waitFor({ state: "visible" });
    if (api.durableWriteCount !== writesBeforeSubagentPreview + 1) throw new Error("Restricted sub-agent preview mutated durable Goal state");
    if ([...(api.goalSubagentPreviews.at(-1)?.allowed_domains ?? [])].sort((a, b) => a.localeCompare(b)).join(",") !== "code,validation") throw new Error("Sub-agent preview lost the bounded task domains");
    await page.locator(".personal-subagent-preview").getByRole("button", { name: "确认", exact: true }).click();
    await page.getByText("已写入，并通过共享 Goal 状态读回校验。", { exact: true }).waitFor({ state: "visible" });
    if (api.durableWriteCount !== writesBeforeSubagentPreview + 2) throw new Error("Restricted sub-agent apply did not produce exactly one additional Goal write");
    await page.screenshot({ path: resolve(outputDir, "goal-subagent-toggle.png"), fullPage: false, animations: "disabled" });

    await enabledSubagentSwitch.click();
    await page.locator(".personal-subagent-preview").getByRole("button", { name: "确认", exact: true }).click();
    const disabledSubagentSwitch = page.getByRole("switch", { name: "预览开启子代理执行" });
    await disabledSubagentSwitch.waitFor({ state: "visible" });
    if (await disabledSubagentSwitch.getAttribute("aria-checked") !== "false") throw new Error("Verified status readback did not turn the per-Goal switch off");
    if (api.durableWriteCount !== writesBeforeSubagentPreview + 3) throw new Error("Sub-agent disable did not produce exactly one additional durable Goal write");
    await page.getByRole("button", { name: /关闭详情/ }).click();
    const productReleaseGoal = page.locator(".personal-goal-link", { hasText: "Product Release" }).first();
    if (!await productReleaseGoal.isVisible()) {
      const stoppedGoals = page.locator(".personal-stopped-goals");
      if (await stoppedGoals.getAttribute("open") === null) await stoppedGoals.locator("summary").click();
    }
    await productReleaseGoal.waitFor({ state: "visible" });
    await productReleaseGoal.click();
    await page.getByRole("button", { name: "打开 Goal 详情或能力配置" }).click();
    await page.getByRole("group", { name: "Goal 设置" }).getByRole("button", { name: /Goal 详情/ }).click();
    await page.getByText("当前没有开放的 advancement Todo 声明 task_domain", { exact: false }).waitFor({ state: "visible" });
    const emptyDomainSwitch = page.getByRole("switch", { name: "预览开启子代理执行" });
    if (!(await emptyDomainSwitch.isEnabled())) throw new Error("A Goal without projected task domains could not enable unrestricted sub-agent execution");
    api.failNextGoalSubagentResponse = true;
    await emptyDomainSwitch.click();
    await page.getByText("LoopX Chat 服务暂时不可用（HTTP 502）。请确认 Dashboard 与 Chat 服务已启动且来自同一版本。", { exact: true }).waitFor({ state: "visible" });
    if ((await page.locator(".personal-goal-subagents").innerText()).includes("Unexpected end of JSON input")) {
      throw new Error("Empty Chat API responses still expose a raw JSON parser failure");
    }
    if (api.durableWriteCount !== writesBeforeSubagentPreview + 3) throw new Error("A failed Goal sub-agent preview wrote Goal state");
    await emptyDomainSwitch.click();
    await page.getByText("预览已锁定，确认后才会写入这个 Goal。", { exact: true }).waitFor({ state: "visible" });
    if (api.goalSubagentPreviews.at(-1)?.allowed_domains.length !== 0) throw new Error("A Goal without task-domain candidates invented a restriction");
    await page.locator(".personal-subagent-preview").getByRole("button", { name: "取消", exact: true }).click();
    if (api.durableWriteCount !== writesBeforeSubagentPreview + 3) throw new Error("Canceling an unrestricted preview wrote Goal state");
    await page.getByRole("button", { name: /关闭详情/ }).click();
    api.freezeGoalSubagentStatusProjection = false;
    pass(22, "Per-Goal sub-agent execution supports unrestricted and restricted policies, previews before writing, verifies shared-state readback, leaves no-domain Goals usable, and can be disabled again.");

    if (await page.locator("html").getAttribute("lang") !== "zh-CN") throw new Error("Desktop did not start in Simplified Chinese");
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await page.getByRole("region", { name: "设置", exact: true }).waitFor({ state: "visible" });
    await page.getByRole("button", { name: /语言/ }).click();
    const englishLocale = page.getByRole("radio", { name: /English/ });
    await englishLocale.click();
    await page.getByRole("heading", { level: 1, name: "Language", exact: true }).waitFor({ state: "visible" });
    if (await page.locator("html").getAttribute("lang") !== "en") throw new Error("Language switch did not update the document locale");
    if (await page.evaluate(() => localStorage.getItem("loopx-pw-locale")) !== "en") throw new Error("English locale was not persisted");
    await page.screenshot({ path: resolve(outputDir, "desktop-settings-english.png"), fullPage: false, animations: "disabled" });
    await page.reload({ waitUntil: "networkidle" });
    await page.getByTestId("personal-goal-home").waitFor({ state: "visible" });
    await page.getByText("LoopX Manager", { exact: true }).first().waitFor({ state: "visible" });
    if (await page.locator("html").getAttribute("lang") !== "en") throw new Error("English locale did not survive reload");
    await page.locator(".personal-goal-link", { hasText: /loopx meta/i }).click();
    await page.getByRole("button", { name: "Open Goal details or capability settings" }).click();
    await page.getByRole("group", { name: "Goal settings" }).getByRole("button", { name: /Goal details/ }).click();
    await page.getByText("Repository", { exact: true }).waitFor({ state: "visible" });
    await page.getByText("Execution Session", { exact: true }).waitFor({ state: "visible" });
    await page.getByText("Read only", { exact: true }).waitFor({ state: "visible" });
    await page.getByRole("button", { name: /Close details/ }).click();
    const englishGoalNavigation = page.getByRole("navigation", { name: "Goal view" });
    await englishGoalNavigation.getByRole("button", { name: "Chat", exact: true }).click();
    await page.getByText("Agent is waiting for your decision", { exact: true }).first().waitFor({ state: "visible" });
    await englishGoalNavigation.getByRole("button", { name: "Files", exact: true }).click();
    const latestRunOutput = page.locator('[data-output-kind="evidence"]', { hasText: "Latest run" }).first();
    await latestRunOutput.waitFor({ state: "visible" });
    const englishProjectionText = await page.locator(".personal-workspace-main").innerText();
    for (const forbidden of ["最近运行", "最近验证", "Agent 正在整理下一步", "Agent 正在推进当前 Goal", "Agent 等待你的决定"]) {
      if (englishProjectionText.includes(forbidden)) throw new Error(`English projection exposed Chinese UI copy ${forbidden}: ${englishProjectionText}`);
    }
    await page.screenshot({ path: resolve(outputDir, "desktop-english-projection-copy.png"), fullPage: false, animations: "disabled" });

    const writesBeforeEnglishPreviews = api.durableWriteCount;
    await page.locator(".personal-manager-link").first().click();
    await page.getByRole("button", { name: "Create Goal", description: "Insert a Goal template to review before creation" }).click();
    const englishGoalDraft = await page.getByLabel("Send a message to LoopX").inputValue();
    for (const field of ["Objective:", "Completion criteria:", "Execution boundary (optional):", "Related repository (optional):", "Notification method (optional):"]) {
      if (!englishGoalDraft.includes(field)) throw new Error(`English Create Goal draft missing ${field}: ${englishGoalDraft}`);
    }
    await page.getByLabel("Send a message to LoopX").fill([
      "Create a long-term Goal:",
      "Objective: Prepare my weekly work review",
      "Completion criteria: List completed work, blockers, and next-week plans",
      "Execution boundary (optional): Read only; do not call external tools or modify repositories",
      "Related repository (optional):",
      "Notification method (optional):",
    ].join("\n"));
    await page.locator(".personal-channel-composer > button").last().click();
    await page.getByText("Confirm execution", { exact: true }).waitFor({ state: "visible" });
    await page.getByRole("button", { name: "Create Goal and start first run", exact: true }).waitFor({ state: "visible" });
    const englishGoalPreview = api.actionPreviews.at(-1);
    if (englishGoalPreview?.action_kind !== "goal.create") throw new Error(`English Goal input did not create a Goal preview: ${JSON.stringify(englishGoalPreview)}`);
    if (englishGoalPreview.normalized_parameters.title !== "Prepare my weekly work review") throw new Error(`English Goal title drifted: ${JSON.stringify(englishGoalPreview.normalized_parameters)}`);
    if (englishGoalPreview.normalized_parameters.completion_criteria !== "List completed work, blockers, and next-week plans") throw new Error(`English completion criteria were not preserved: ${JSON.stringify(englishGoalPreview.normalized_parameters)}`);
    if (englishGoalPreview.normalized_parameters.execution_boundary !== "Read only; do not call external tools or modify repositories") throw new Error(`English execution boundary was not preserved: ${JSON.stringify(englishGoalPreview.normalized_parameters)}`);
    if (englishGoalPreview.normalized_parameters.permission !== "read_only") throw new Error(`English execution boundary did not remain read-only: ${JSON.stringify(englishGoalPreview.normalized_parameters)}`);
    await page.getByRole("button", { name: "Close", exact: true }).click();

    await page.locator(".personal-goal-link").first().click();
    await page.getByRole("button", { name: "Configure scheduled check", description: "Fill in what to check, frequency, and stop condition before creation" }).click();
    const englishMonitorDraft = await page.getByLabel("Send a message to LoopX").inputValue();
    for (const field of ["Check target:", "Frequency", "Stop condition:"]) {
      if (!englishMonitorDraft.includes(field)) throw new Error(`English monitor draft missing ${field}: ${englishMonitorDraft}`);
    }
    const previewsBeforeEnglishCalendarSchedule = api.actionPreviews.length;
    await page.getByLabel("Send a message to LoopX").fill([
      "Add a scheduled check for the current Goal:",
      "Check target: Verify the weekly review",
      "Frequency: Every Friday at 17:00",
      "Stop condition: Goal completes",
    ].join("\n"));
    await page.locator(".personal-channel-composer > button").last().click();
    await page.getByText("Scheduled checks do not currently support an exact weekday or time.", { exact: false }).waitFor({ state: "visible" });
    if (api.actionPreviews.length !== previewsBeforeEnglishCalendarSchedule) throw new Error("Unsupported English calendar schedule created a misleading preview");
    await page.getByLabel("Send a message to LoopX").fill([
      "Add a scheduled check for the current Goal:",
      "Check target: Verify the review includes completed work, blockers, and next-week plans",
      "Frequency: Every 2 hours",
      "Stop condition: Goal completes",
    ].join("\n"));
    await page.locator(".personal-channel-composer > button").last().click();
    await page.getByText("Confirm execution", { exact: true }).waitFor({ state: "visible" });
    await page.getByRole("button", { name: "Confirm and apply", exact: true }).waitFor({ state: "visible" });
    const englishMonitorPreview = api.actionPreviews.at(-1);
    if (englishMonitorPreview?.action_kind !== "monitor.create") throw new Error(`English monitor input did not create a monitor preview: ${JSON.stringify(englishMonitorPreview)}`);
    if (englishMonitorPreview.normalized_parameters.cadence !== "2h") throw new Error(`English monitor cadence drifted: ${JSON.stringify(englishMonitorPreview.normalized_parameters)}`);
    if (englishMonitorPreview.normalized_parameters.target !== "Verify the review includes completed work, blockers, and next-week plans") throw new Error(`English monitor target drifted: ${JSON.stringify(englishMonitorPreview.normalized_parameters)}`);
    if (englishMonitorPreview.normalized_parameters.stop_condition !== "goal_complete") throw new Error(`English monitor stop condition drifted: ${JSON.stringify(englishMonitorPreview.normalized_parameters)}`);
    if (api.durableWriteCount !== writesBeforeEnglishPreviews) throw new Error("English write previews mutated durable state before confirmation");
    await page.getByRole("button", { name: "Close", exact: true }).click();

    await page.getByRole("button", { name: "Open Goal details or capability settings" }).click();
    await page.getByRole("group", { name: "Goal settings" }).getByRole("button", { name: /Goal details/ }).click();
    await page.getByRole("button", { name: "Set up Heartbeat", exact: true }).click();
    const englishHeartbeatDraft = await page.getByLabel("Send a message to LoopX").inputValue();
    for (const field of ["Frequency: Daily", "Stop condition: Goal completes", "Notification: Only notify me when needed"]) {
      if (!englishHeartbeatDraft.includes(field)) throw new Error("English Heartbeat draft missing " + field + ": " + englishHeartbeatDraft);
    }
    await page.locator(".personal-channel-composer > button").last().click();
    await page.getByText("Confirm execution", { exact: true }).waitFor({ state: "visible" });
    const englishHeartbeatPreview = api.actionPreviews.at(-1);
    if (englishHeartbeatPreview?.action_kind !== "heartbeat.bind") throw new Error("English Heartbeat input did not create a heartbeat preview: " + JSON.stringify(englishHeartbeatPreview));
    if (englishHeartbeatPreview.normalized_parameters.cadence !== "1d") throw new Error("English Heartbeat cadence drifted: " + JSON.stringify(englishHeartbeatPreview.normalized_parameters));
    if (englishHeartbeatPreview.normalized_parameters.stop_condition !== "goal_complete") throw new Error("English Heartbeat stop condition drifted: " + JSON.stringify(englishHeartbeatPreview.normalized_parameters));
    const writesBeforeEnglishHeartbeatApply = api.durableWriteCount;
    api.allowNextHeartbeatApply = true;
    await page.getByRole("button", { name: "Confirm and apply", exact: true }).click();
    await page.getByText("Applied. LoopX state will refresh.", { exact: true }).waitFor({ state: "visible" });
    if (api.durableWriteCount !== writesBeforeEnglishHeartbeatApply + 1) throw new Error("English Heartbeat apply did not produce exactly one durable write");
    await page.getByRole("button", { name: "View updated Goal", exact: true }).click();
    await page.getByRole("navigation", { name: "Goal view" }).getByRole("button", { name: "Chat", exact: true }).click();
    const englishHeartbeatSchedule = page.locator(".personal-schedule-row", { hasText: "Goal Heartbeat" }).first();
    await englishHeartbeatSchedule.waitFor({ state: "visible" });
    const englishHeartbeatScheduleText = await englishHeartbeatSchedule.innerText();
    if (!englishHeartbeatScheduleText.includes("1d")) throw new Error("Applied English Heartbeat lost cadence: " + englishHeartbeatScheduleText);
    await englishHeartbeatSchedule.click();
    const englishHeartbeatDrawer = page.locator('.personal-context-drawer[data-context-kind="schedule"]');
    await englishHeartbeatDrawer.getByText("goal_complete", { exact: true }).waitFor({ state: "visible" });
    await englishHeartbeatDrawer.getByText("Asia/Shanghai", { exact: true }).waitFor({ state: "visible" });
    const englishHeartbeatReadback = await englishHeartbeatDrawer.innerText();
    for (const forbidden of ["等待下次宿主唤醒", "仅在需要你时通知", "由 heartbeat-prompt 生命周期驱动", "Goal 完成或 owner 停止"]) {
      if (englishHeartbeatReadback.includes(forbidden)) throw new Error("Applied English Heartbeat exposed Chinese fallback " + forbidden + ": " + englishHeartbeatReadback);
    }
    await page.getByRole("button", { name: /Close details/ }).click();
    pass(20, "English Goal and monitor previews stay read-only until confirmation, and applied Heartbeat readback preserves typed schedule semantics.");

    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.getByRole("button", { name: /Language/ }).click();
    await page.getByRole("radio", { name: /Simplified Chinese/ }).click();
    await page.getByRole("heading", { level: 1, name: "语言", exact: true }).waitFor({ state: "visible" });
    if (await page.evaluate(() => localStorage.getItem("loopx-pw-locale")) !== "zh-CN") throw new Error("Simplified Chinese locale was not persisted");
    await page.getByRole("button", { name: "返回工作区", exact: true }).click();
    await page.locator(".personal-manager-link").first().click();
    await page.getByTestId("personal-goal-home").waitFor({ state: "visible" });

    if (await page.locator(".personal-manager-conversation-tray").count()) {
      throw new Error("Historical manager messages kept a conversation receipt permanently visible before a new send");
    }
    const managerNavigation = page.getByRole("navigation", { name: "管家视图" });
    await managerNavigation.waitFor({ state: "visible" });
    if (await managerNavigation.getByRole("button", { name: "总览", exact: true }).getAttribute("aria-current") !== "page") {
      throw new Error("Manager overview did not expose its persistent selected tab");
    }
    await managerNavigation.getByRole("button", { name: "Chat", exact: true }).click();
    if (await managerNavigation.getByRole("button", { name: "Chat", exact: true }).getAttribute("aria-current") !== "page") {
      throw new Error("Manager Chat did not become the selected view");
    }
    if (await page.locator(".personal-home-board").isVisible()) throw new Error("Manager Chat kept the overview board visible");
    await managerNavigation.getByRole("button", { name: "总览", exact: true }).click();
    await page.locator(".personal-home-board").waitFor({ state: "visible" });

    await page.getByRole("button", { name: "汇总所有 Goal 进展" }).click();
    const reportDeadline = Date.now() + 5_000;
    while (!api.turnRequests.some((turn) => turn.message.includes("汇总所有活跃 Goal 的最新进展与阻塞")) && Date.now() < reportDeadline) {
      await new Promise((resolveWait) => setTimeout(resolveWait, 50));
    }
    if (!api.turnRequests.some((turn) => turn.message.includes("汇总所有活跃 Goal 的最新进展与阻塞"))) throw new Error("Progress report shortcut did not send a useful scoped request");
    while (await page.getByRole("button", { name: "汇总所有 Goal 进展" }).isDisabled()) await new Promise((resolveWait) => setTimeout(resolveWait, 50));
    await page.locator(".personal-manager-conversation-tray").waitFor({ state: "visible" });
    if (!(await page.getByTestId("personal-home-lane-running").isVisible())) throw new Error("Manager send replaced the four-lane home overview");
    const managerUrlBefore = page.url();
    await page.getByRole("button", { name: "询问全局待办", exact: true }).click();
    await page.getByLabel("向 LoopX 发送消息").fill("我现在该做什么？只读回答，不要创建或修改任何状态。");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await page.getByText(/^先处理「.+」：.+/u).waitFor({ state: "visible" });
    await page.getByText("查看完整对话", { exact: true }).waitFor({ state: "visible" });
    if (page.url() !== managerUrlBefore) throw new Error(`Manager send navigated away from the overview: ${managerUrlBefore} -> ${page.url()}`);
    await page.screenshot({ path: resolve(outputDir, "manager-conversation-tray-compact.png"), fullPage: false, animations: "disabled" });
    await page.getByText("查看完整对话", { exact: true }).click();
    await page.getByRole("navigation", { name: "管家视图" }).waitFor({ state: "visible" });
    if (await page.locator(".personal-home-board").isVisible()) throw new Error("Full manager Chat left the Goal overview visible behind the conversation");
    if (await page.locator(".personal-manager-conversation-tray").count()) throw new Error("Full manager Chat kept the compact home tray visible");
    if (await page.locator(".personal-channel-timeline .personal-message").count() < 4) throw new Error("Manager Chat did not show the complete conversation history");
    await page.screenshot({ path: resolve(outputDir, "manager-chat.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: "总览", exact: true }).click();
    await page.locator(".personal-home-board").waitFor({ state: "visible" });
    if (await page.locator(".personal-manager-conversation-tray").count()) {
      throw new Error("Manager conversation receipt stayed permanently visible after returning to the overview");
    }

    const [fileChooser] = await Promise.all([
      page.waitForEvent("filechooser"),
      page.getByRole("button", { name: "添加图片" }).click(),
    ]);
    await fileChooser.setFiles({
      buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z8WQAAAAASUVORK5CYII=", "base64"),
      mimeType: "image/png",
      name: "loopx-smoke.png",
    });
    await page.getByRole("img", { name: "loopx-smoke.png" }).waitFor({ state: "visible" });
    if (await page.getByRole("button", { name: "发送", exact: true }).isDisabled()) throw new Error("A valid image attachment did not enable the composer send action");
    await page.getByRole("button", { name: "移除图片 loopx-smoke.png" }).click();
    pass(18, "The visible attachment button opens a file chooser; a valid PNG renders a preview and enables send.");

    await page.getByLabel("向 LoopX 发送消息").evaluate((target) => {
      const png = Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z8WQAAAAASUVORK5CYII="), (char) => char.charCodeAt(0));
      const file = new File([png], "loopx-pasted.png", { type: "image/png" });
      const transfer = new DataTransfer();
      transfer.items.add(file);
      target.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: transfer }));
    });
    await page.getByRole("img", { name: "loopx-pasted.png" }).waitFor({ state: "visible" });
    await page.getByRole("button", { name: "移除图片 loopx-pasted.png" }).click();
    pass(19, "Pasting a clipboard PNG attaches through the same validated composer path.");

    const writesBeforeGoalCreate = api.durableWriteCount;
    await page.getByRole("button", { name: "创建新 Goal" }).click();
    const goalDraft = await page.getByLabel("向 LoopX 发送消息").inputValue();
    for (const field of ["目标：", "完成标准：", "执行边界（可选）：", "关联仓库（可选）：", "通知方式（可选）："]) {
      if (!goalDraft.includes(field)) throw new Error(`Create Goal draft missing ${field}`);
    }
    await page.getByLabel("向 LoopX 发送消息").fill([
      "我想创建一个长期 Goal：",
      "目标：整理我的每周工作复盘",
      "完成标准：列出已完成、阻塞、下周计划",
      "执行边界（可选）：不调用外部工具，不修改仓库",
      "关联仓库（可选）：",
      "通知方式（可选）：",
    ].join("\n"));
    await page.locator(".personal-channel-composer > button").last().click();
    await page.getByText("确认执行").waitFor({ state: "visible" });
    const goalPreview = api.actionPreviews.at(-1);
    for (const field of ["agent_id", "goal_id", "heartbeat", "initial_todos", "permission", "stop_condition", "workspace_ref"]) {
      if (!(field in (goalPreview?.normalized_parameters ?? {}))) throw new Error(`Goal preview missing ${field}`);
    }
    if (goalPreview?.normalized_parameters.title !== "整理我的每周工作复盘") throw new Error(`Structured Goal title drifted: ${JSON.stringify(goalPreview?.normalized_parameters)}`);
    if (goalPreview?.normalized_parameters.goal_id === "loopx" || !String(goalPreview?.normalized_parameters.goal_id).startsWith("goal-")) throw new Error(`Structured Goal id was derived from template chrome: ${JSON.stringify(goalPreview?.normalized_parameters)}`);
    if (!String(goalPreview?.normalized_parameters.objective).includes("列出已完成、阻塞、下周计划")) throw new Error(`Goal completion standard was lost: ${JSON.stringify(goalPreview?.normalized_parameters)}`);
    if (goalPreview?.normalized_parameters.completion_criteria !== "列出已完成、阻塞、下周计划") throw new Error(`Goal completion criteria were not preserved structurally: ${JSON.stringify(goalPreview?.normalized_parameters)}`);
    if (goalPreview?.normalized_parameters.execution_boundary !== "不调用外部工具，不修改仓库") throw new Error(`Goal execution boundary was not preserved structurally: ${JSON.stringify(goalPreview?.normalized_parameters)}`);
    if (goalPreview?.normalized_parameters.permission !== "read_only") throw new Error(`Goal execution boundary did not remain read-only: ${JSON.stringify(goalPreview?.normalized_parameters)}`);
    if (JSON.stringify(goalPreview?.normalized_parameters.initial_todos).includes("推进首个可验证结果")) throw new Error(`Goal preview kept unrelated generic Todos: ${JSON.stringify(goalPreview?.normalized_parameters)}`);
    if (api.durableWriteCount !== writesBeforeGoalCreate) throw new Error("Goal preview wrote durable state before confirmation");
    pass(7, "Goal preview includes Goal, Agent, workspace, permissions, Todos, heartbeat, and stop condition fields.");
    await page.getByRole("button", { name: "创建 Goal 并开始首轮", exact: true }).click();
    try {
      await page.getByText(/已应用/).first().waitFor({ state: "visible" });
    } catch (error) {
      await page.screenshot({ path: resolve(outputDir, "goal-apply-failed.png"), fullPage: true, animations: "disabled" });
      throw new Error(`${error.message}; applies=${JSON.stringify(api.actionApplies)}; errors=${pageErrors.join(" | ")}; body=${(await page.locator("body").innerText()).slice(0, 3000)}`);
    }
    if (api.durableWriteCount !== writesBeforeGoalCreate + 1) throw new Error("Goal apply did not create exactly one durable resource");
    await page.evaluate(async (proposalId) => {
      await fetch(`/api/actions/${proposalId}/apply`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
    }, goalPreview.proposalId);
    if (api.durableWriteCount !== writesBeforeGoalCreate + 1) throw new Error("Repeated proposal apply duplicated durable state");
    pass(9, "A repeated apply request kept one durable resource and one first-turn resource key.");
    await page.getByRole("button", { name: /关闭详情/ }).click();
    const actionReceiptClose = page.getByRole("button", { name: "关闭操作回执", exact: true });
    if (await actionReceiptClose.isVisible().catch(() => false)) await actionReceiptClose.click();

    const goalButton = page.locator(".personal-goal-link").first();
    await goalButton.click();
    const goalNavigation = page.getByRole("navigation", { name: "Goal 视图" });
    const defaultTasksTab = goalNavigation.getByRole("button", { name: "Tasks" });
    if (await defaultTasksTab.getAttribute("aria-current") !== "page") throw new Error("Selecting a Goal did not prioritize its Tasks view");
    await page.screenshot({ path: resolve(outputDir, "goal-tasks-loopx-theme.png"), fullPage: false, animations: "disabled" });
    await goalNavigation.getByRole("button", { name: "Files" }).click();
    const publicFiles = page.locator(".personal-files-list > button");
    await publicFiles.first().waitFor({ state: "visible" });
    await page.screenshot({ path: resolve(outputDir, "goal-files-loopx-theme.png"), fullPage: false, animations: "disabled" });
    await goalNavigation.getByRole("button", { name: "Chat" }).click();
    await page.locator(".personal-channel-timeline").waitFor({ state: "visible" });
    await page.screenshot({ path: resolve(outputDir, "goal-chat-loopx-theme.png"), fullPage: false, animations: "disabled" });
    await defaultTasksTab.click();
    const desktopNavigationTrigger = page.locator(".personal-mobile-menu");
    if (await desktopNavigationTrigger.isVisible()) {
      throw new Error("Mobile-only Goal navigation trigger leaked into the persistent desktop sidebar layout");
    }
    const fullDesktopViewport = page.viewportSize();
    await page.setViewportSize({ width: 900, height: 720 });
    const compactHeaderButtons = [
      page.locator(".personal-mobile-menu"),
      page.locator(".personal-refresh-control .personal-icon-button"),
    ];
    for (const button of compactHeaderButtons) {
      const box = await button.boundingBox();
      if (!box || Math.abs(box.width - 36) > 0.5 || Math.abs(box.height - 36) > 0.5) {
        throw new Error(`Compact header icon button was compressed: ${JSON.stringify(box)}`);
      }
    }
    const compactGoalSettingsBox = await page.locator(".personal-goal-tools-trigger").boundingBox();
    if (!compactGoalSettingsBox || compactGoalSettingsBox.width < 40 || compactGoalSettingsBox.height < 36) {
      throw new Error(`Compact Goal settings trigger was compressed: ${JSON.stringify(compactGoalSettingsBox)}`);
    }
    const compactHeaderLayout = await page.evaluate(() => {
      const live = document.querySelector(".personal-live-indicator");
      return {
        documentWidth: document.documentElement.scrollWidth,
        liveHeight: live?.getBoundingClientRect().height ?? 0,
        liveScrollWidth: live?.scrollWidth ?? 0,
        liveWidth: live?.getBoundingClientRect().width ?? 0,
        viewportWidth: window.innerWidth,
      };
    });
    if (compactHeaderLayout.liveScrollWidth > compactHeaderLayout.liveWidth + 1 || compactHeaderLayout.liveHeight > 36) {
      throw new Error(`Compact header live status wrapped: ${JSON.stringify(compactHeaderLayout)}`);
    }
    if (compactHeaderLayout.documentWidth > compactHeaderLayout.viewportWidth + 1) {
      throw new Error(`Compact header caused horizontal overflow: ${JSON.stringify(compactHeaderLayout)}`);
    }
    await page.screenshot({ path: resolve(outputDir, "goal-header-compact-width.png"), fullPage: false, animations: "disabled" });
    if (fullDesktopViewport) await page.setViewportSize(fullDesktopViewport);
    await page.locator(".personal-goal-link", { hasText: "Progress Projection" }).click();
    await page.getByRole("heading", { name: "Progress Projection" }).waitFor({ state: "visible" });
    const progressHeader = page.locator(".personal-channel-title p");
    if (!(await progressHeader.innerText()).includes("Current Todo")) throw new Error(`Goal header did not prefer the current Todo: ${await progressHeader.innerText()}`);
    const progressColumn = page.locator(".personal-object-list", { hasText: "待执行 / 进行中" });
    if ((await progressColumn.locator(".personal-task-card").count()) !== 5) throw new Error("Id-less long Todo was duplicated across compact and full projections");
    await progressColumn.getByText("Full queue follow-up", { exact: true }).waitFor();
    await progressColumn.getByText("Deferred queue task", { exact: true }).waitFor();
    await progressColumn.getByText("Deferred follow-up outside preview", { exact: true }).waitFor();
    async function assertDeferredTask(conditionExpected = true) {
      const title = conditionExpected ? "Deferred queue task" : "Deferred follow-up outside preview";
      const card = page.locator(".personal-task-card", { hasText: title });
      await card.getByText("已延期", { exact: true }).waitFor();
      if (await card.getByText("待执行", { exact: true }).count()) throw new Error("Deferred task was labeled queued");
      await card.getByText(title, { exact: true }).click();
      const drawer = page.getByRole("dialog", { name: "Todo 详情" });
      await drawer.getByText("等待恢复条件满足后重新评估", { exact: true }).waitFor();
      const condition = drawer.locator("dl > div", { has: page.getByText("恢复条件", { exact: true }) });
      await condition.getByText(conditionExpected ? "todo_done:todo-progress-full" : "未设置", { exact: true }).waitFor();
      if (await drawer.getByText("待执行", { exact: true }).count()) throw new Error("Deferred drawer was labeled ready");
      await page.screenshot({ path: resolve(outputDir, `deferred-task-${conditionExpected ? "condition" : "missing"}.png`), fullPage: false, animations: "disabled" });
      await drawer.getByRole("button", { name: /关闭详情/ }).click();
    }
    await assertDeferredTask();
    await assertDeferredTask(false);
    const completedColumn = page.locator(".personal-object-list", { hasText: "已完成" }).last();
    const taskLaneScrollers = page.locator('.personal-task-kanban .personal-task-lane-scroll');
    if (await taskLaneScrollers.count() !== 4) throw new Error('Every desktop Task lane must own a scroll region');
    for (let laneIndex = 0; laneIndex < 4; laneIndex += 1) {
      if (await taskLaneScrollers.nth(laneIndex).evaluate(element => getComputedStyle(element).overflowY) !== 'auto') {
        throw new Error(`Task lane ${laneIndex + 1} does not support independent scrolling`);
      }
    }
    await completedColumn.getByText("4087", { exact: true }).waitFor({ state: "visible" });
    await completedColumn.getByText("Completed A", { exact: true }).waitFor({ state: "visible" });
    if (await completedColumn.getByText("Completed Monitor", { exact: true }).count()) throw new Error("Completed continuous monitor leaked into the completed Tasks column");
    const historyScroll = completedColumn.locator('.personal-task-lane-scroll');
    for (let batch = 1; batch < 103; batch += 1) {
      const response = page.waitForResponse(response => response.url().includes('/api/chat/completed-todos?') && response.url().includes(`cursor=${batch * 40}`));
      await historyScroll.evaluate(element => { element.scrollTop = element.scrollHeight; });
      await response;
      await page.waitForFunction(minimum => {
        const window = document.querySelector('[data-testid="completed-task-lane"] .personal-completed-window');
        return window && Number.parseFloat(window.style.height) >= minimum;
      }, Math.min(4087, (batch + 1) * 40) * 148);
      if (await completedColumn.locator('.personal-completed-row').count() > 20) throw new Error('Completed history DOM grew with accumulated pages');
    }
    await historyScroll.evaluate(element => { element.scrollTop = element.scrollHeight; });
    await completedColumn.getByText('Completed historical Task 4087', { exact: true }).waitFor();
    await completedColumn.getByText('已显示全部完成记录', { exact: true }).waitFor();
    await page.screenshot({ path: resolve(outputDir, 'completed-history-4087.png'), fullPage: false, animations: 'disabled' });
    await historyScroll.evaluate(element => { element.scrollTop = 0; });
    await completedColumn.getByText('Completed A', { exact: true }).waitFor();
    // Both presentations retain one snapshot, including archived history and evidence.
    let historyRequests = 0;
    page.on('request', request => { if (request.url().includes('/api/chat/completed-todos?')) historyRequests += 1; });
    await page.getByRole('button', { name: '列表', exact: true }).click();
    await assertDeferredTask();
    const listHistory = page.getByTestId('completed-task-lane');
    await listHistory.getByRole('button', { name: '已完成', exact: false }).click();
    await listHistory.getByText('4087', { exact: true }).waitFor();
    await listHistory.getByText('Completed A', { exact: true }).waitFor();
    await listHistory.locator('.personal-task-lane-scroll').evaluate(element => { element.scrollTop = element.scrollHeight; });
    await listHistory.getByText('Completed historical Task 4087', { exact: true }).waitFor();
    if (await listHistory.locator('.personal-completed-row').count() > 20) throw new Error('List history DOM grew with accumulated pages');
    await page.screenshot({ path: resolve(outputDir, 'completed-history-list.png'), fullPage: false, animations: 'disabled' });
    await page.getByRole('button', { name: '看板', exact: true }).click();
    await completedColumn.getByText('Completed A', { exact: true }).waitFor();
    if (historyRequests) throw new Error('Switching presentation replaced the completed-history snapshot');
    await page.locator(".personal-goal-link", { hasText: "Multi Agent Projection" }).click();
    const multiAgentHeader = await page.locator(".personal-channel-title p").innerText();
    if (!multiAgentHeader.includes("2 个工作 Agent") || multiAgentHeader.includes("codex-older-lane ·")) {
      throw new Error(`Multi-Agent Goal header still implies arbitrary single-lane ownership: ${multiAgentHeader}`);
    }
    if ((await page.locator(".personal-object-list", { hasText: "待执行 / 进行中" }).locator(".personal-task-card").count()) !== 2) {
      throw new Error("All-Agent default did not preserve both projected work lanes");
    }
    const laneFilter = page.getByRole("combobox", { name: "按工作 Agent 筛选" });
    if (await laneFilter.inputValue() !== "all") throw new Error("Multi-Agent Tasks view did not default to all work lanes");
    await page.screenshot({ path: resolve(outputDir, "multi-agent-task-lanes.png"), fullPage: false, animations: "disabled" });
    await laneFilter.selectOption("codex-latest-lane");
    const filteredText = await page.locator(".personal-object-list", { hasText: "待执行 / 进行中" }).innerText();
    if (!filteredText.includes("Latest lane work") || filteredText.includes("Older lane work")) {
      throw new Error(`Work-Agent filter did not consistently filter task cards: ${filteredText}`);
    }
    const runtimeSelector = page.getByRole("combobox", { name: "选择聊天 Runtime" });
    if (!await runtimeSelector.count()) throw new Error("Chat runtime selector is not explicitly labelled independently from work-Agent lanes");
    await goalButton.click();
    const readBoardGeometry = async () => {
      const kanban = page.locator(".personal-task-kanban");
      await kanban.waitFor({ state: "visible" });
      const kanbanBox = await kanban.boundingBox();
      const columns = await page.locator(".personal-task-kanban > .personal-object-list").evaluateAll((els) =>
        els.map((el) => { const rect = el.getBoundingClientRect(); return { left: rect.left, right: rect.right, width: rect.width }; })
      );
      return { kanbanBox, columns };
    };
    const assertBoardGeometry = (label, geometry) => {
      if (!geometry.kanbanBox || geometry.columns.length !== 4) {
        throw new Error(`${label}: expected 4 kanban columns, got ${geometry.columns?.length}`);
      }
      const kanbanRight = geometry.kanbanBox.x + geometry.kanbanBox.width;
      if (Math.abs(geometry.columns[3].right - kanbanRight) > 2) {
        throw new Error(`${label}: kanban columns do not fill the board (lastRight=${geometry.columns[3].right}, boardRight=${kanbanRight})`);
      }
      if (new Set(geometry.columns.map((column) => Math.round(column.width))).size !== 1) {
        throw new Error(`${label}: kanban columns are not equal width: ${JSON.stringify(geometry.columns)}`);
      }
    };
    const selectFirstGoal = async () => {
      await page.locator(".personal-goal-link").first().click();
      await page.locator(".personal-task-kanban").waitFor({ state: "visible" });
    };
    const selectProductReleaseGoal = async () => {
      const goal = page.locator(".personal-goal-link", { hasText: "Product Release" }).first();
      if (!await goal.isVisible()) {
        const stoppedGoals = page.locator(".personal-stopped-goals");
        if (await stoppedGoals.getAttribute("open") === null) await stoppedGoals.locator("summary").click();
      }
      await goal.click();
      await page.locator(".personal-task-kanban").waitFor({ state: "visible" });
    };
    const populatedGeometry = await readBoardGeometry();
    assertBoardGeometry("populated board", populatedGeometry);
    await selectProductReleaseGoal();
    const emptyGeometry = await readBoardGeometry();
    assertBoardGeometry("empty board", emptyGeometry);
    if (Math.abs(emptyGeometry.kanbanBox.width - populatedGeometry.kanbanBox.width) > 2) {
      throw new Error(`Empty board width ${emptyGeometry.kanbanBox.width} differs from populated ${populatedGeometry.kanbanBox.width}`);
    }
    const desktopViewport = page.viewportSize();
    await page.setViewportSize({ width: 2048, height: 1200 });
    await page.waitForTimeout(200);
    await selectFirstGoal();
    const populatedWide = await readBoardGeometry();
    assertBoardGeometry("populated board (wide)", populatedWide);
    await selectProductReleaseGoal();
    const emptyWide = await readBoardGeometry();
    assertBoardGeometry("empty board (wide)", emptyWide);
    if (Math.abs(emptyWide.kanbanBox.width - populatedWide.kanbanBox.width) > 2) {
      throw new Error(`Empty board width (wide) ${emptyWide.kanbanBox.width} differs from populated ${populatedWide.kanbanBox.width}`);
    }
    await page.setViewportSize(desktopViewport);
    await page.waitForTimeout(200);
    await selectFirstGoal();
    await page.locator(".personal-object-list").first().waitFor({ state: "visible" });
    if (await page.locator(".personal-task-capability-callout").count()) throw new Error("Goal capability settings still consume a full-width Tasks row");
    await page.getByRole("button", { name: "打开 Goal 详情或能力配置" }).click();
    const goalSettingsMenu = page.getByRole("group", { name: "Goal 设置" });
    const capabilityMenuItem = goalSettingsMenu.getByRole("button", { name: /能力配置/ });
    await capabilityMenuItem.waitFor({ state: "visible" });
    await page.screenshot({ path: resolve(outputDir, "goal-settings-unified-menu.png"), fullPage: false, animations: "disabled" });
    await capabilityMenuItem.click();
    await page.getByRole("heading", { level: 1, name: "Goal 能力", exact: true }).waitFor({ state: "visible" });
    if (await page.locator(".personal-workspace-shell").count()) throw new Error("Unified Goal capability action did not open the Settings surface");
    await page.getByRole("heading", { level: 2, name: "周期报告", exact: true }).waitFor({ state: "visible" });
    const goalCapabilityOrder = await page.locator(".personal-capability-list button small").allTextContents();
    if (await page.locator(".personal-capability-editor-status").count()) throw new Error("Editable Goal settings must not show internal editor-contract notices");
    const expectedGoalCapabilities = [
      "change_quality_qualification", "explore_graph", "explore_harness", "lark_event_inbox",
      "lark_kanban_heartbeat_sync", "local_authority_shadow", "multi_subagent",
      "peer_task_coordination", "periodic_report", "reward_memory",
    ];
    if (JSON.stringify([...goalCapabilityOrder].sort()) !== JSON.stringify(expectedGoalCapabilities)) {
      throw new Error(`Goal capability workbench did not render the complete catalog: ${JSON.stringify(goalCapabilityOrder)}`);
    }
    const capabilityIndex = (capabilityId) => goalCapabilityOrder.indexOf(capabilityId);
    if (capabilityIndex("periodic_report") >= capabilityIndex("explore_harness")
      || capabilityIndex("multi_subagent") <= capabilityIndex("explore_harness")
      || capabilityIndex("multi_subagent") >= capabilityIndex("local_authority_shadow")
      || capabilityIndex("multi_subagent") >= capabilityIndex("reward_memory")) {
      throw new Error(`Goal capability maturity ordering drifted: ${JSON.stringify(goalCapabilityOrder)}`);
    }
    for (const label of [/^启用$/u, /^报告 Profile/u, /^Goal Channel 路由/u, /^时区/u]) {
      await page.getByLabel(label).waitFor({ state: "visible" });
    }
    await page.screenshot({ path: resolve(outputDir, "goal-capability-zh-cn.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: "预览变更", exact: true }).click();
    await page.getByText("锁定 revision 的变更预览", { exact: true }).waitFor({ state: "visible" });
    const goalConfigurationPreview = api.goalConfigurationRequests.find((item) => item.phase === "preview");
    const projectedKeys = Object.keys(goalConfigurationPreview?.configuration ?? {}).sort((left, right) => left.localeCompare(right));
    if (JSON.stringify(projectedKeys) !== JSON.stringify(["enabled", "profile_preset", "route_ref", "timezone"])) {
      throw new Error(`Goal configuration preview leaked hidden machine fields: ${JSON.stringify(goalConfigurationPreview)}`);
    }
    await page.getByRole("button", { name: "应用此预览", exact: true }).click();
    await page.getByText("Goal 值已保存；共享投影仍需修复", { exact: true }).waitFor({ state: "visible" });
    if (!(await page.getByText(/loopx sync-global --goal-id/u).isVisible())) throw new Error("Partial Goal write did not expose its reconciliation action");
    const goalConfigurationApply = api.goalConfigurationRequests.find((item) => item.phase === "apply");
    if (goalConfigurationApply?.expected_plan_revision !== "sha256:goal-plan-periodic_report") throw new Error("Goal configuration apply lost its reviewed plan revision");

    await page.getByRole("button", { name: /自适应子 Agent 容量/u }).click();
    await page.getByRole("heading", { level: 2, name: "自适应子 Agent 容量", exact: true }).waitFor({ state: "visible" });
    const multiSubagentEnabled = page.getByLabel(/^启用$/u);
    const multiSubagentMaxChildren = page.getByLabel(/^最大子 Agent 数/u);
    const multiSubagentDomains = page.getByLabel(/^允许的职责域/u);
    await multiSubagentEnabled.waitFor({ state: "visible" });
    await waitForInputValue(multiSubagentMaxChildren, "4");
    await multiSubagentEnabled.check();
    await multiSubagentMaxChildren.fill("3");
    await multiSubagentDomains.fill("code\nvalidation");
    await page.screenshot({ path: resolve(outputDir, "goal-subagent-capability-zh-cn.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: "预览变更", exact: true }).click();
    await page.getByText("锁定 revision 的变更预览", { exact: true }).waitFor({ state: "visible" });
    const multiSubagentPreview = api.goalConfigurationRequests.findLast((item) => item.phase === "preview" && item.capability_id === "multi_subagent");
    if (JSON.stringify(multiSubagentPreview?.configuration) !== JSON.stringify({
      enabled: true,
      max_children: 3,
      allowed_domains: ["code", "validation"],
    })) {
      throw new Error(`Unified Goal capability preview lost the sub-agent boundary: ${JSON.stringify(multiSubagentPreview)}`);
    }
    await page.getByRole("button", { name: "应用此预览", exact: true }).click();
    const multiSubagentApply = api.goalConfigurationRequests.findLast((item) => item.phase === "apply" && item.capability_id === "multi_subagent");
    if (multiSubagentApply?.expected_plan_revision !== "sha256:goal-plan-multi_subagent") {
      throw new Error(`Unified Goal capability apply lost its reviewed sub-agent revision: ${JSON.stringify(multiSubagentApply)}`);
    }
    await page.locator(".personal-capability-raw-values > summary").click();
    await page.locator(".personal-capability-value-grid section").first().getByText(/validation/u).waitFor({ state: "visible" });
    await page.getByRole("button", { name: "返回工作区", exact: true }).click();
    await page.getByRole("button", { name: "Tasks", current: "page" }).waitFor({ state: "visible" });
    await page.getByRole("button", { name: "打开 Goal 详情或能力配置" }).click();
    await page.getByRole("group", { name: "Goal 设置" }).getByRole("button", { name: /Goal 详情/ }).click();
    await page.getByText("仓库", { exact: true }).waitFor({ state: "visible" });
    await page.getByText("执行 Session", { exact: true }).waitFor({ state: "visible" });
    await page.getByText("只读", { exact: true }).waitFor({ state: "visible" });
    if (!(await page.getByText("loopx-ai/loopx", { exact: true }).isVisible())) throw new Error("Goal drawer did not show the read-only repository context");
    await page.getByRole("button", { name: /关闭详情/ }).click();

    await page.getByRole("button", { name: "设置", exact: true }).click();
    await page.getByRole("heading", { name: "Lark", exact: true }).waitFor({ state: "visible" });
    if (await page.locator(".personal-workspace-shell").count()) throw new Error("Workspace Settings did not replace the workspace shell");
    if (await page.locator(".personal-channel-composer").count()) throw new Error("Workspace Settings left the chat composer visible");
    if (await page.locator("[data-context-drawer]").count()) throw new Error("Workspace Settings left the context drawer visible");
    await page.screenshot({ path: resolve(outputDir, "workspace-settings.png"), fullPage: false, animations: "disabled" });

    await page.getByRole("button", { name: /机器配置/ }).click();
    await page.getByRole("heading", { level: 1, name: "机器配置", exact: true }).waitFor({ state: "visible" });
    await page.getByRole("heading", { level: 2, name: "周期报告", exact: true }).waitFor({ state: "visible" });
    const machineCatalog = page.getByRole("navigation", { name: "机器能力目录" });
    if (await page.locator(".personal-capability-editor-status").count()) throw new Error("Editable machine settings must not show internal editor-contract notices");
    if (await machineCatalog.getByRole("button").count() !== goalCapabilityCatalog().length) {
      throw new Error("Machine settings hid Goal-only capabilities from the shared catalog");
    }
    const requestsBeforeReadOnly = api.machineConfigurationRequests.length;
    await machineCatalog.getByRole("button", { name: /multi_subagent/ }).click();
    await page.getByText(/此能力目前仅支持 Goal 级配置/u).waitFor({ state: "visible" });
    if (await page.getByRole("button", { name: "预览变更", exact: true }).count()
        || await page.locator("#machine-configuration-json").count()
        || await page.getByLabel(/^启用$/u).count()
        || api.machineConfigurationRequests.length !== requestsBeforeReadOnly) {
      throw new Error("Goal-only capability exposed a machine mutation path");
    }
    await machineCatalog.getByRole("button", { name: /periodic_report/ }).click();
    for (const label of [/^启用$/u, /^报告 Profile/u, /^Goal Channel 路由/u, /^时区/u]) {
      await page.getByLabel(label).waitFor({ state: "visible" });
    }
    await page.getByText("开启后将在已验证的阶段节点自动投递", { exact: true }).waitFor({ state: "visible" });
    await page.getByText(/启用此订阅即授予持续投递权/u).waitFor({ state: "visible" });
    await page.getByRole("button", { name: "预览变更", exact: true }).click();
    await page.getByText("审阅机器配置变更", { exact: true }).waitFor({ state: "visible" });
    const machineConfigurationPreview = api.machineConfigurationRequests.find((item) => item.phase === "preview");
    const machineKeys = Object.keys(machineConfigurationPreview?.namespace_configuration ?? {}).sort((left, right) => left.localeCompare(right));
    if (JSON.stringify(machineKeys) !== JSON.stringify(["enabled", "inheritance", "profile_preset", "route_ref", "schema_version", "timezone"])) {
      throw new Error(`Machine guided editor lost capability-owned hidden fields: ${JSON.stringify(machineConfigurationPreview)}`);
    }
    await page.getByRole("button", { name: "应用已审阅预览", exact: true }).click();
    await page.getByText("机器策略已应用，并通过回读校验。", { exact: true }).waitFor({ state: "visible" });
    const machineConfigurationApply = api.machineConfigurationRequests.find((item) => item.phase === "apply");
    if (machineConfigurationApply?.expected_plan_revision !== "sha256:machine-plan") throw new Error("Machine configuration apply lost its reviewed plan revision");
    await page.screenshot({ path: resolve(outputDir, "machine-capability-behavior-zh-cn.png"), fullPage: false, animations: "disabled" });

    await page.getByRole("button", { name: /语言/ }).click();
    await page.getByRole("radio", { name: /English/ }).click();
    await page.getByRole("button", { name: /Machine configuration/ }).click();
    await page.getByRole("heading", { level: 2, name: "Periodic reports", exact: true }).waitFor({ state: "visible" });
    const rawValues = page.locator(".personal-capability-raw-values");
    if (await rawValues.getAttribute("open") !== null) throw new Error("Raw JSON must be collapsed by default");
    if (!await page.locator(".personal-capability-actions").evaluate((actions) => Boolean(actions.compareDocumentPosition(document.querySelector(".personal-capability-raw-values")) & Node.DOCUMENT_POSITION_FOLLOWING))) {
      throw new Error("Readable configuration actions must precede raw JSON diagnostics");
    }
    await rawValues.locator("summary").focus();
    await page.keyboard.press("Enter");
    await rawValues.locator("pre").first().waitFor({ state: "visible" });
    await page.keyboard.press("Enter");
    if (await rawValues.getAttribute("open") !== null) throw new Error("Raw JSON keyboard collapse failed");
    for (const label of [/^Enabled$/u, /^Report profile/u, /^Goal Channel route/u, /^Timezone/u]) {
      await page.getByLabel(label).waitFor({ state: "visible" });
    }
    await page.getByText("Enabled means automatic delivery at validated stage boundaries", { exact: true }).waitFor({ state: "visible" });
    await page.screenshot({ path: resolve(outputDir, "machine-capability-en.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: /Goal capabilities/ }).click();
    await page.getByRole("button", { name: /Adaptive child capacity/ }).click();
    await page.getByRole("heading", { level: 2, name: "Adaptive child capacity", exact: true }).waitFor({ state: "visible" });
    for (const label of [/^Enabled$/u, /^Maximum children/u, /^Allowed responsibility domains/u]) {
      await page.getByLabel(label).waitFor({ state: "visible" });
    }
    await page.screenshot({ path: resolve(outputDir, "goal-subagent-capability-en.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: /Language/ }).click();
    await page.getByRole("radio", { name: /Simplified Chinese/ }).click();
    await page.getByRole("button", { name: /机器配置/ }).click();
    await page.locator(".personal-settings-body").evaluate((element) => element.scrollTo({ top: 0 }));
    await page.screenshot({ path: resolve(outputDir, "machine-capability-zh-cn.png"), fullPage: false, animations: "disabled" });
    const settingsViewport = page.viewportSize();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(200);
    const machineOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (machineOverflow > 1) throw new Error(`Machine capability settings overflow the mobile viewport by ${machineOverflow}px`);
    await page.screenshot({ path: resolve(outputDir, "machine-capability-mobile-zh-cn.png"), fullPage: false, animations: "disabled" });
    await page.setViewportSize(settingsViewport);
    await page.waitForTimeout(200);
    await page.getByRole("button", { name: /Lark/ }).click();

    await page.getByRole("button", { name: /连接 Lark App/ }).click();
    const connectDialog = page.getByRole("dialog", { name: "连接 Lark App" });
    await connectDialog.waitFor({ state: "visible" });
    await connectDialog.getByRole("option", { name: "Product group" }).waitFor({ state: "attached" });
    await connectDialog.getByLabel("群聊").selectOption({ label: "Product group" });
    await connectDialog.getByLabel("接收范围").selectOption("configured_chat_all");
    const ingressGroup = connectDialog.getByRole("group", { name: "Agent 入站方式" });
    const ingressOptions = await ingressGroup.locator("input[type=radio]").evaluateAll((options) => options.map((option) => option.value));
    if (JSON.stringify(ingressOptions) !== JSON.stringify(["live_steering", "session_queue", "async_inbox"])) throw new Error(`Lark Agent ingress modes drifted: ${JSON.stringify(ingressOptions)}`);
    await ingressGroup.getByLabel("异步收件箱").check();
    await connectDialog.getByLabel("目标 Agent").waitFor({ state: "visible" });
    await connectDialog.getByLabel("绑定到 Goal").selectOption("multi-agent-projection");
    const agentOptions = await connectDialog.getByLabel("目标 Agent").locator("option").evaluateAll((items) => items.map((item) => item.value));
    if (JSON.stringify([...agentOptions].sort((left, right) => left.localeCompare(right))) !== JSON.stringify(["codex-latest-lane", "codex-older-lane"])) throw new Error(`Lark omitted a peer Agent: ${JSON.stringify(agentOptions)}`);
    await connectDialog.getByLabel("目标 Agent").selectOption("codex-older-lane");
    await connectDialog.getByLabel("回复方式").selectOption("topic_reply");
    await page.screenshot({ path: resolve(outputDir, "lark-routing-modes.png"), fullPage: false, animations: "disabled" });
    await connectDialog.getByRole("button", { name: "连接", exact: true }).click();
    await connectDialog.waitFor({ state: "hidden" });
    const connectionReadback = await page.evaluate(async () => (await fetch("/api/chat/lark/connections")).json());
    if (connectionReadback.connections?.length !== 1) throw new Error(`Lark connection API readback mismatch: ${JSON.stringify(connectionReadback)}`);
    try {
      await page.locator(".personal-lark-table-row", { hasText: "Product group" }).waitFor({ state: "visible", timeout: 10_000 });
    } catch (error) {
      await page.screenshot({ path: resolve(outputDir, "lark-connection-refresh-failed.png"), fullPage: true, animations: "disabled" });
      throw new Error(`${error.message}; body=${(await page.locator("body").innerText()).slice(0, 4000)}`);
    }
    const connectedRow = page.locator(".personal-lark-table-row", { hasText: "Product group" });
    if (!(await connectedRow.getByText("事件订阅待验证", { exact: false }).isVisible())) throw new Error("A zero-event listener was presented as automatic-reply ready");
    if (!(await connectedRow.getByRole("link", { name: "查看飞书事件配置" }).isVisible())) throw new Error("An unverified Lark event subscription lacked repair guidance");
    if (api.larkWrites.length !== 1 || api.larkWrites[0].execute !== true) throw new Error("Lark connect did not perform exactly one approved external write");
    if (api.larkWrites[0].capture_scope !== "configured_chat_all" || api.larkWrites[0].incoming_mode !== "all") throw new Error(`Lark capture mode was not projected: ${JSON.stringify(api.larkWrites[0])}`);
    if (api.larkWrites[0].ingress_mode !== "async_inbox" || !api.larkWrites[0].agent_id) throw new Error(`Lark Agent inbox mode lost its Agent binding: ${JSON.stringify(api.larkWrites[0])}`);
    if (api.larkWrites[0].agent_id !== "codex-older-lane" || api.larkWrites[0].goal_id !== "multi-agent-projection") throw new Error("Lark replaced the selected peer with the default Agent");
    if (api.larkWrites[0].reply_mode !== "topic_reply") throw new Error(`Lark reply mode was not projected: ${JSON.stringify(api.larkWrites[0])}`);
    Object.assign(api.larkConnections[0], {
      event_count: 1,
      health_error_code: "lark_event_route_mismatch",
      last_event_reason: "topic_mismatch",
      last_event_status: "ignored",
    });
    const mismatchReadback = await page.evaluate(async () => (await fetch("/api/chat/lark/connections")).json());
    if (mismatchReadback.connections?.[0]?.last_event_reason !== "topic_mismatch") {
      throw new Error(`Lark route mismatch API readback mismatch: ${JSON.stringify(mismatchReadback)}`);
    }
    await page.getByRole("button", { name: "返回工作区", exact: true }).click();
    await page.reload({ waitUntil: "networkidle" });
    await page.getByTestId("personal-goal-home").waitFor({ state: "visible" });
    await page.getByRole("button", { name: "设置", exact: true }).click();
    const routeMismatchRow = page.locator(".personal-lark-table-row", { hasText: "Product group" });
    try {
      await routeMismatchRow.getByText("消息未匹配当前 Goal Topic", { exact: false }).waitFor({ state: "visible" });
    } catch (error) {
      throw new Error(`${error.message}; body=${(await page.locator("body").innerText()).slice(0, 4000)}`);
    }
    await routeMismatchRow.getByText("请重新选择群聊并连接该 Goal", { exact: false }).waitFor({ state: "visible" });
    await page.locator(".personal-lark-table-row", { hasText: "Product group" }).getByRole("button", { name: /配置/ }).click();
    const editDialog = page.getByRole("dialog", { name: "编辑 Lark 连接" });
    await editDialog.waitFor({ state: "visible" });
    if (await editDialog.getByLabel("接收范围").inputValue() !== "configured_chat_all") throw new Error("Lark edit mode did not restore capture_scope");
    if (!await editDialog.getByRole("group", { name: "Agent 入站方式" }).getByLabel("异步收件箱").isChecked()) throw new Error("Lark edit mode did not restore ingress_mode");
    if (await editDialog.getByLabel("目标 Agent").inputValue() !== api.larkWrites[0].agent_id) throw new Error("Lark edit mode did not restore agent_id");
    await editDialog.getByLabel("目标 Agent").selectOption("codex-latest-lane");
    await editDialog.getByRole("button", { name: "保存连接", exact: true }).click();
    await editDialog.waitFor({ state: "hidden" });
    if (api.larkWrites.length !== 2 || api.larkConnections.length !== 2) throw new Error("Peer Agent route did not coexist");
    if (!api.larkConnections.some((item) => item.agent_id === "codex-older-lane") || !api.larkConnections.some((item) => item.agent_id === "codex-latest-lane")) throw new Error("One-click Goal Channel lost a peer Agent route");
    const removedConnection = api.larkConnections.find((item) => item.agent_id === "codex-older-lane");
    const originalAgent = removedConnection.agent_id;
    removedConnection.agent_id = "removed-peer";
    await page.getByRole("button", { name: "返回工作区", exact: true }).click();
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await page.locator(".personal-lark-table-row", { hasText: "removed-peer" }).getByRole("button", { name: /配置/ }).click();
    await editDialog.getByRole("alert").filter({ hasText: "不会自动替换" }).waitFor({ state: "visible" });
    if (!(await editDialog.getByRole("button", { name: "保存连接", exact: true }).isDisabled())) throw new Error("Removed recipient remained connectable");
    if (await editDialog.getByLabel("目标 Agent").inputValue() !== "removed-peer") throw new Error("Removed recipient silently fell back to another Agent");
    await editDialog.getByRole("button", { name: "取消" }).click();
    removedConnection.agent_id = originalAgent;
    await page.screenshot({ path: resolve(outputDir, "lark-goal-connections.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: "返回工作区", exact: true }).click();
    await selectProductReleaseGoal();
    await page.getByRole("navigation", { name: "Goal 视图" }).getByRole("button", { name: "Tasks" }).click();
    await page.locator(".personal-object-list").first().waitFor({ state: "visible" });
    await page.getByRole("navigation", { name: "Goal 视图" }).getByRole("button", { name: "Files" }).click();
    const reportOutput = page.getByTestId("personal-goal-outputs").getByRole("button", { name: /Product Release milestone report/ });
    await reportOutput.waitFor({ state: "visible" });
    await reportOutput.click();
    await page.getByTestId("personal-periodic-report-detail").getByText("Release candidate verified", { exact: true }).waitFor({ state: "visible" });
    await page.getByTestId("personal-periodic-report-detail").getByText("Rollout plan updated", { exact: true }).waitFor({ state: "visible" });
    if (await page.locator('[data-testid="frontstage-milestone-reports"]').count()) throw new Error("Milestone report still rendered in the deprecated Ops Frontstage");
    await page.getByRole("button", { name: /关闭详情/ }).click();
    await selectFirstGoal();
    await page.getByRole("navigation", { name: "Goal 视图" }).getByRole("button", { name: "Chat" }).click();

    const composer = page.getByLabel("向 LoopX 发送消息");
    const previewCountBeforeSemanticIntent = api.actionPreviews.length;
    async function expectConversationalProtectedTurn(message, answer, previewError) {
      await composer.fill(message);
      await page.getByRole("button", { name: "发送", exact: true }).click();
      await page.getByText(answer, { exact: true }).last().waitFor({ state: "visible", timeout: 10_000 });
      if (api.actionPreviews.length !== previewCountBeforeSemanticIntent) throw new Error(previewError);
    }
    await expectConversationalProtectedTurn("请只回复：合并后真实回复已收到", "合并后真实回复已收到", "An exact-wording protected-action mention created a typed preview");
    await expectConversationalProtectedTurn("请分析：合并 PR #123 后会有什么风险", "主要风险是检查未完成或目标分支发生变化；这里只做分析，不会创建合并预览。", "Protected-action analysis created a typed preview");
    await expectConversationalProtectedTurn("请合并", "请告诉我要合并的具体 PR 或 MR；在目标明确前不会创建执行预览。", "A targetless protected action created an incomplete preview");
    await expectConversationalProtectedTurn("请合并我刚才说的那个", "这个指代不够明确，请提供具体 PR 或 MR。", "A model-invented protected target created a typed preview");

    await composer.fill("请合并 PR #123");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await page.getByText("确认执行").waitFor({ state: "visible", timeout: 10_000 });
    const protectedMerge = api.actionPreviews.find((preview) => preview.action_kind === "goal.update" && preview.summary.includes("PR #123"));
    if (!protectedMerge) throw new Error("A clear Agent semantic proposal did not create the protected typed preview");
    await page.screenshot({ path: resolve(outputDir, "semantic-protected-action-preview.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: "关闭", exact: true }).click();

    await composer.fill("添加一个「补充回归测试」普通 Todo，并交给 Codex。不要设置 Heartbeat，也不要创建定时检查");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await page.getByText("确认执行").waitFor({ state: "visible" });
    const naturalTodo = api.actionPreviews.find((preview) => preview.action_kind === "todo.create" && preview.normalized_parameters.text === "补充回归测试");
    if (naturalTodo?.normalized_parameters.endpoint_id !== "codex") throw new Error(`Natural-language Todo creation lost the selected Endpoint: ${JSON.stringify(api.actionPreviews.at(-1))}`);
    if (api.actionPreviews.findLast((preview) => preview.summary.includes("补充回归测试"))?.action_kind !== "todo.create") throw new Error("A negated Heartbeat mention overrode explicit Todo creation");
    await page.getByRole("button", { name: "关闭", exact: true }).click();

    const previewCountBeforeAnalysis = api.actionPreviews.length;
    const turnCountBeforeAnalysis = api.turnRequests.length;
    await page.getByRole("navigation", { name: "Goal 视图" }).getByRole("button", { name: "Tasks" }).click();
    await composer.fill("做一次只读分析：判断刚刚新增的 Todo 是否与当前 Goal 一致，并在当前 Chat 返回两点理由。不要修改状态。");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    const taskConversationReceipt = page.getByRole("region", { name: "最近对话" });
    await taskConversationReceipt.getByText("Agent 已回复", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    await taskConversationReceipt.getByText("本次对话没有直接修改 Tasks。需要执行时，可先转成 Task 草稿并确认。", { exact: true }).waitFor({ state: "visible" });
    if (api.actionPreviews.length !== previewCountBeforeAnalysis) throw new Error("A read-only reference to an existing Todo created another Todo preview");
    if (api.turnRequests.length <= turnCountBeforeAnalysis) throw new Error("Read-only Todo analysis did not reach the Goal Chat Session");
    await page.screenshot({ path: resolve(outputDir, "task-chat-receipt.png"), fullPage: false, animations: "disabled" });
    await taskConversationReceipt.getByRole("button", { name: "查看回复" }).click();
    await page.getByText("已沿用当前 Goal 与 Agent Session。接下来会先核对状态，再继续推进。", { exact: true }).last().waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("navigation", { name: "Goal 视图" }).getByRole("button", { name: "Tasks" }).click();
    await page.getByRole("region", { name: "最近对话" }).getByRole("button", { name: "转为 Task" }).click();
    if (!(await composer.inputValue()).startsWith("创建一个 Task：")) throw new Error("Converting the latest reply did not create an editable Task draft");
    await page.getByText("已根据回复生成 Task 草稿。编辑后发送，LoopX 会先展示确认预览。", { exact: true }).waitFor({ state: "visible" });
    await composer.fill("");
    await page.getByRole("navigation", { name: "Goal 视图" }).getByRole("button", { name: "Chat" }).click();

    await composer.fill("让 Claude Code 负责管理这个 Goal");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await page.getByText("确认执行").waitFor({ state: "visible" });
    const naturalBinding = api.actionPreviews.find((preview) => preview.action_kind === "agent.bind" && preview.normalized_parameters.agent_id === "claude-code");
    if (!naturalBinding) throw new Error("Natural-language Agent binding did not create a typed preview");
    await page.getByRole("button", { name: "关闭", exact: true }).click();

    const selectedGoalId = new URL(page.url()).searchParams.get("goalId");
    if (!selectedGoalId) throw new Error("Selected Goal URL did not preserve goalId for the Session authority smoke");
    const authoritativeSessionId = `session-authoritative-${selectedGoalId}`;
    page.__loopxRuntime.sessions.set(authoritativeSessionId, {
      session_id: authoritativeSessionId,
      goal_id: selectedGoalId,
      agent_id: "codex",
      adapter_kind: "codex",
      channel_id: "task.todo-session-authority-smoke",
      status: "stale",
      active_turn_id: null,
      last_error_code: null,
      created_at: "2026-08-13T01:00:00Z",
      updated_at: "2026-08-13T01:00:00Z",
      last_activity_at: "2026-08-13T01:00:00Z",
      resumable: true,
    });
    page.__loopxRuntime.messages.set(authoritativeSessionId, []);
    const authoritativeRun = page.locator(".personal-run-row", { hasText: "Agent 执行任务" });
    await authoritativeRun.waitFor({ state: "visible", timeout: 5_000 });
    page.__loopxRuntime.messages.set(authoritativeSessionId, [{
      message_id: "message-authoritative-result",
      turn_id: "turn-authoritative-result",
      role: "agent",
      text: "权威 Session 已完成只读分析，并返回可核验结果。",
      created_at: "2026-08-13T01:00:03Z",
    }]);
    await authoritativeRun.click();
    await page.getByText("执行 Session", { exact: true }).waitFor({ state: "visible" });
    if (await page.getByRole("tab", { name: "执行过程与结果" }).getAttribute("aria-selected") !== "true") throw new Error("Session drawer did not open on the execution record");
    const authoritativeRecord = page.locator(".personal-session-message-record");
    try {
      await authoritativeRecord.locator("header strong").filter({ hasText: "已完成" }).first().waitFor({ state: "visible", timeout: 8_000 });
    } catch (error) {
      await page.screenshot({ path: resolve(outputDir, "session-authority-refresh-failed.png"), fullPage: true, animations: "disabled" });
      throw new Error(`${error.message}; body=${(await page.locator("body").innerText()).slice(-5000)}`);
    }
    await page.getByLabel("执行 Session").getByText("1/1", { exact: true }).waitFor({ state: "visible" });
    await page.getByText("权威 Session 已完成只读分析，并返回可核验结果。", { exact: true }).waitFor({ state: "visible" });
    if (await page.getByText("stale", { exact: true }).count()) throw new Error("Fresh Session result left a stale status visible");
    await page.getByText("运行记录", { exact: true }).waitFor({ state: "visible" });
    await page.screenshot({ path: resolve(outputDir, "session-execution-record.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("tab", { name: "详情与操作" }).click();
    const correction = page.getByLabel("输入纠偏信息");
    const turnCountBeforeCorrection = api.turnRequests.length;
    await correction.fill("先核对权限边界，再继续推进。");
    await page.getByRole("button", { name: "发送纠偏" }).click();
    try {
      const correctionDeadline = Date.now() + 10_000;
      while (api.turnRequests.length <= turnCountBeforeCorrection && Date.now() < correctionDeadline) {
        await page.waitForTimeout(100);
      }
      await page.getByText(/已沿用当前 Goal/).last().waitFor({ state: "visible", timeout: 10_000 });
    } catch (error) {
      await page.screenshot({ path: resolve(outputDir, "run-correction-failed.png"), fullPage: true, animations: "disabled" });
      throw new Error(`${error.message}; turns=${JSON.stringify(api.turnRequests)}; errors=${pageErrors.join(" | ")}; body=${(await page.locator("body").innerText()).slice(0, 4000)}`);
    }
    const firstCorrection = api.turnRequests.slice(turnCountBeforeCorrection).find((turn) => turn.message === "先核对权限边界，再继续推进。");
    if (!firstCorrection?.sessionId || firstCorrection.sessionId.includes("manager")) throw new Error(`Run correction did not use the selected Goal's execution Session: ${JSON.stringify(firstCorrection)}`);
    pass(5, "Run-detail correction used a recoverable Goal-scoped Agent Session.");
    await page.getByRole("button", { name: /关闭详情/ }).click();

    const writesBeforeHeartbeat = api.durableWriteCount;
    await composer.fill("每天推进这个 Goal，设置 heartbeat");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await page.getByText("确认执行").waitFor({ state: "visible" });
    await page.getByRole("button", { name: "确认并应用", exact: true }).click();
    await page.getByText("需要宿主确认").waitFor({ state: "visible" });
    if (api.durableWriteCount !== writesBeforeHeartbeat) throw new Error("Protected heartbeat gate wrote durable state");
    pass(8, "Agent semantic protected intent creates only a typed preview, while discussion and targetless requests remain conversational and all protected-gate paths perform zero durable writes before confirmation.");
    pass(11, "Heartbeat apply surfaced an explicit host-activation gate.");
    const heartbeatPreview = api.actionPreviews.find((preview) => preview.action_kind === "heartbeat.bind");
    if (!heartbeatPreview) throw new Error("Continuation intent did not map to heartbeat.bind");
    await page.getByRole("button", { name: "关闭", exact: true }).click();

    await page.getByRole("button", { name: "打开 Goal 详情或能力配置" }).click();
    await page.getByRole("group", { name: "Goal 设置" }).getByRole("button", { name: /Goal 详情/ }).click();
    await page.getByRole("button", { name: "Tasks" }).click();
    const taskCards = page.locator(".personal-object-list", { hasText: "进行中" }).locator(".personal-task-card");
    const taskRow = taskCards.first().locator(":scope > button");
    await taskRow.click();
    const taskInspector = page.getByRole("dialog", { name: "Todo 详情" });
    await taskInspector.waitFor({ state: "visible" });
    await page.waitForFunction(() => document.querySelector('[data-context-drawer]')?.contains(document.activeElement));
    const mainBox = await page.locator(".personal-workspace-main").boundingBox();
    const inspectorBox = await page.locator('[data-context-drawer][data-drawer-mode="inspector"]').boundingBox();
    if (!mainBox || !inspectorBox || mainBox.x + mainBox.width > inspectorBox.x + 1) throw new Error("Half-screen Todo inspector covered the task board instead of occupying its own layout column");
    if (!(await page.locator(".personal-task-card.is-selected").isVisible())) throw new Error("Opening a Todo did not keep its selected card visible in the board viewport");
    await page.getByRole("button", { name: "切换到全屏", exact: true }).click();
    if (await page.locator(".personal-workspace-main").isVisible()) throw new Error("Full-screen Todo inspector left the board visible");
    await page.getByRole("button", { name: "切换到半屏", exact: true }).click();
    if (!(await page.locator(".personal-workspace-main").isVisible())) throw new Error("Half-screen Todo inspector did not restore the board");
    if (await taskCards.count() < 2) throw new Error("Todo focus smoke requires two task cards");
    const secondTaskRow = taskCards.nth(1).locator(":scope > button");
    await secondTaskRow.click();
    await page.waitForFunction(() => document.activeElement?.id === "personal-drawer-title");
    await page.getByRole("button", { name: /关闭详情/ }).click();
    await page.waitForFunction(() => document.activeElement?.closest(".personal-task-card") === document.querySelectorAll(".personal-task-card")[1]);
    await taskRow.click();
    let taskManagement = page.locator("details.personal-task-management");
    await taskManagement.locator("summary").click();
    await taskManagement.locator(".personal-inline-agent-select", { hasText: "改派给" }).getByRole("button", { name: "查看处理方式", exact: true }).click();
    await page.getByText("确认执行").waitFor({ state: "visible" });
    if (!api.actionPreviews.some((preview) => preview.action_kind === "todo.update" && preview.normalized_parameters.operation === "reassign")) throw new Error("Todo reassign did not create a typed preview");
    await page.getByRole("button", { name: "关闭", exact: true }).click();
    await taskRow.click();
    taskManagement = page.locator("details.personal-task-management");
    await taskManagement.locator("summary").click();
    await page.getByLabel("Todo 暂缓恢复条件").fill("pr_merged:huangruiteng/loopx#3399");
    await page.screenshot({ path: resolve(outputDir, "todo-defer-resume-condition.png"), fullPage: false, animations: "disabled" });
    await taskManagement.locator(".personal-inline-resume-when").getByRole("button", { name: "检查暂缓" }).click();
    await page.getByText("确认执行").waitFor({ state: "visible" });
    const explicitDefer = api.actionPreviews.findLast((preview) => preview.action_kind === "todo.update" && preview.normalized_parameters.operation === "defer");
    if (explicitDefer?.normalized_parameters.resume_when !== "pr_merged:huangruiteng/loopx#3399") throw new Error(`Todo defer did not preserve its supported resume condition: ${JSON.stringify(explicitDefer)}`);
    if (JSON.stringify(api.actionPreviews).includes("owner_resume")) throw new Error("Personal Workspace emitted the unsupported owner_resume sentinel");
    await page.getByRole("button", { name: "关闭", exact: true }).click();
    for (const [label, actionKind, operation, managementAction] of [
      ["标记阻塞", "todo.update", "block", true],
      ["标记完成", "todo.update", "complete", false],
      ["创建后续 Todo", "todo.create", null, true],
    ]) {
      await taskRow.click();
      if (managementAction) await page.locator("details.personal-task-management").locator("summary").click();
      await page.getByRole("button", { name: label, exact: true }).click();
      await page.getByText("确认执行").waitFor({ state: "visible" });
      if (!api.actionPreviews.some((preview) => preview.action_kind === actionKind && (operation === null || preview.normalized_parameters.operation === operation))) throw new Error(`Todo ${label} did not create the expected typed preview`);
      await page.getByRole("button", { name: "关闭", exact: true }).click();
    }
    api.nextActionPreviewDelayMs = 900;
    const quickComplete = taskCards.first().getByRole("button", { name: /^标记完成：/u });
    const quickPreviewCount = api.actionPreviews.length;
    await quickComplete.click();
    await page.waitForFunction(
      () => document.querySelector('button[aria-label^="标记完成："]')?.getAttribute("aria-busy") === "true",
      null,
      { timeout: 600 },
    );
    if (!(await quickComplete.isDisabled())) throw new Error("Quick Todo completion remained clickable while preview creation was pending");
    await page.getByText(/^正在准备确认预览：/u).waitFor({ state: "visible", timeout: 600 });
    await page.getByText("确认执行").waitFor({ state: "visible", timeout: 2_000 });
    if (api.actionPreviews.length !== quickPreviewCount + 1) throw new Error("Quick Todo completion did not create exactly one typed preview");
    const quickPreview = api.actionPreviews.at(-1);
    if (quickPreview?.action_kind !== "todo.update" || quickPreview.normalized_parameters.operation !== "complete") throw new Error(`Quick Todo completion created the wrong typed preview: ${JSON.stringify(quickPreview)}`);
    await page.getByRole("button", { name: "关闭", exact: true }).click();
    api.failNextActionPreview = true;
    api.nextActionPreviewDelayMs = 300;
    await quickComplete.click();
    await page.getByText(/^无法准备确认预览：/u).waitFor({ state: "visible", timeout: 1_000 });
    if (await quickComplete.isDisabled()) throw new Error("Quick Todo completion stayed disabled after a preview failure");
    if (api.actionPreviews.length !== quickPreviewCount + 1) throw new Error("A rejected quick completion preview was recorded as ready");
    await page.getByRole("navigation", { name: "Goal 视图" }).getByRole("button", { name: "Chat" }).click();
    await page.getByRole("dialog").filter({ hasText: "确认执行" }).waitFor({ state: "hidden" });

    await page.getByRole("button", { name: "配置定时检查" }).click();
    await page.getByLabel("向 LoopX 发送消息").fill("为当前 Goal 添加定时检查：\n检查内容：复盘是否包含已完成、阻塞、下周计划\n频率：每周五 17:00\n停止条件：Goal 完成");
    const previewsBeforeUnsupportedSchedule = api.actionPreviews.length;
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await page.getByText(/不支持精确到星期或时刻的日历计划/).waitFor({ state: "visible" });
    if (api.actionPreviews.length !== previewsBeforeUnsupportedSchedule) throw new Error("Unsupported weekly schedule created a misleading preview");
    if (!(await page.getByLabel("向 LoopX 发送消息").inputValue()).includes("每周五 17:00")) throw new Error("Unsupported schedule draft was discarded");
    await page.getByLabel("向 LoopX 发送消息").fill("为当前 Goal 添加定时检查：\n检查内容：复盘是否包含已完成、阻塞、下周计划\n频率：每 2 小时\n停止条件：Goal 完成");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await page.getByText("确认执行").waitFor({ state: "visible" });
    const monitorCreate = api.actionPreviews.findLast((preview) => preview.action_kind === "monitor.create");
    if (!monitorCreate) throw new Error("Bounded monitor configuration did not map to monitor.create");
    if (monitorCreate.normalized_parameters.cadence !== "2h") throw new Error(`Monitor cadence drifted: ${JSON.stringify(monitorCreate.normalized_parameters)}`);
    if (monitorCreate.normalized_parameters.target !== "复盘是否包含已完成、阻塞、下周计划") throw new Error(`Monitor target drifted: ${JSON.stringify(monitorCreate.normalized_parameters)}`);
    await page.getByRole("button", { name: "关闭", exact: true }).click();

    await goalNavigation.getByRole("button", { name: "Chat" }).click();
    const schedule = page.locator(".personal-schedule-row").first();
    for (const [label, operation] of [["立即运行", "run_now"], ["暂停", "pause"], ["改为每 2 小时", "edit"], ["停止定时检查", "stop"]]) {
      await schedule.click();
      await page.getByText("定时检查", { exact: true }).last().waitFor({ state: "visible" });
      await page.getByRole("button", { name: label, exact: true }).click();
      await page.getByText("确认执行").waitFor({ state: "visible" });
      const monitorUpdate = api.actionPreviews.find((preview) => preview.action_kind === "monitor.update" && preview.normalized_parameters.operation === operation);
      if (!monitorUpdate) throw new Error(`Monitor ${operation} did not map to monitor.update`);
      if (operation === "pause") {
        const writesBeforeApply = api.durableWriteCount;
        await page.getByRole("button", { name: "确认并应用", exact: true }).click();
        await page.getByText("执行结果", { exact: true }).waitFor({ state: "visible" });
        await page.getByText("已应用，LoopX 状态将刷新。").waitFor({ state: "visible" });
        if (api.durableWriteCount !== writesBeforeApply + 1) throw new Error("Monitor confirmation did not produce exactly one durable write");
        if (!api.actionApplies.includes(monitorUpdate.proposalId)) throw new Error("Monitor confirmation did not apply the previewed proposal");
        api.nextStatusDelayMs = 1_600;
        await page.getByRole("button", { name: "查看更新后的 Goal", exact: true }).click();
        await page.getByRole("dialog").filter({ hasText: "执行结果" }).waitFor({ state: "hidden", timeout: 600 });
        await goalNavigation.getByRole("button", { name: "Tasks", current: "page" }).waitFor({ state: "visible", timeout: 600 });
        await goalNavigation.getByRole("button", { name: "Chat" }).click();
      } else {
        await page.getByRole("button", { name: "关闭", exact: true }).click();
      }
    }
    pass(10, "Continuation mapped to heartbeat.bind and bounded monitoring mapped to monitor.create/continuous_monitor UI.");

    const agentSelect = page.getByRole("combobox", { name: "选择聊天 Runtime" });
    await agentSelect.click();
    const agentListbox = page.getByRole("listbox", { name: "选择聊天 Runtime" });
    const unavailableAgent = agentListbox.getByRole("option", { name: /Offline Agent · 不可用/ });
    if ((await unavailableAgent.count()) !== 1) throw new Error(`Unavailable Agent missing; options=${await agentListbox.getByRole("option").allTextContents()}`);
    const unavailableDisabled = await unavailableAgent.isDisabled();
    const unavailableLabel = await unavailableAgent.textContent();
    if (!unavailableDisabled || !unavailableLabel?.includes("不可用")) {
      throw new Error(`Unavailable Agent is selectable or lacks explanation; disabled=${unavailableDisabled}; label=${unavailableLabel}`);
    }
    await page.screenshot({ path: resolve(outputDir, "agent-select-open.png"), fullPage: false, animations: "disabled" });
    await page.keyboard.press("ArrowDown");
    const focusedAgentOption = await page.locator(":focus").textContent();
    if (!focusedAgentOption?.includes("Claude Code")) throw new Error(`Agent keyboard navigation did not advance: ${focusedAgentOption}`);
    await page.keyboard.press("Escape");
    if (await agentListbox.isVisible().catch(() => false)) throw new Error("Agent menu did not close on Escape");
    if (!(await agentSelect.evaluate((element) => element === document.activeElement))) throw new Error("Agent menu did not restore trigger focus");
    pass(14, "Codex remained the healthy default and the unavailable Agent option was disabled with explanation.");
    await agentSelect.click();
    const reopenedAgentListbox = page.getByRole("listbox", { name: "选择聊天 Runtime" });
    await reopenedAgentListbox.getByRole("option", { name: "Claude Code", exact: true }).click();
    if ((await agentSelect.getAttribute("data-value")) !== "claude-code") throw new Error("Healthy Agent selection did not update");
    await page.getByRole("button", { name: "刷新状态" }).click();

    await page.locator(".personal-run-row").first().click();
    await page.getByRole("tab", { name: "详情与操作" }).click();
    const runningCorrection = page.getByLabel("输入纠偏信息");
    await runningCorrection.fill("保持运行，等我检查中断控制。 ");
    await page.getByRole("button", { name: "发送纠偏" }).click();
    await page.getByText("更多运行操作").click();
    const interruptButton = page.getByRole("button", { name: "中断本次运行" });
    try {
      await interruptButton.waitFor({ state: "visible", timeout: 8_000 });
    } catch (error) {
      await page.screenshot({ path: resolve(outputDir, "interrupt-state-failed.png"), fullPage: true, animations: "disabled" });
      throw new Error(`${error.message}; body=${(await page.locator("body").innerText()).slice(-4000)}`);
    }
    await interruptButton.click();
    const secondCorrection = api.turnRequests.find((turn) => turn.message.includes("中断控制"));
    if (!secondCorrection || secondCorrection.sessionId === firstCorrection.sessionId) {
      throw new Error("Agent change reused the earlier Agent Session or failed to start the second correction");
    }
    if (!api.interrupts.some((turn) => turn.sessionId === secondCorrection.sessionId && turn.turnId === secondCorrection.turnId)) {
      throw new Error("Interrupt did not target the active Session and Turn");
    }
    await page.getByRole("button", { name: /关闭详情/ }).click();
    await page.getByText("已中断。你可以在当前会话继续发送消息。", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });

    await page.locator(".personal-run-row").first().click();
    const rowHandle = page.locator(".personal-run-row").first();
    await page.getByRole("button", { name: /关闭详情/ }).press("Escape");
    await rowHandle.waitFor({ state: "visible" });
    await page.waitForFunction(
      () => document.activeElement?.classList.contains("personal-run-row"),
      null,
      { timeout: 2_000 },
    );
    if (!(await rowHandle.evaluate((element) => element === document.activeElement))) throw new Error("Drawer Escape did not restore focus to the selected row");

    await page.getByRole("button", { name: /LoopX 管家/ }).first().click();
    const needsYouCard = page.getByTestId("personal-home-lane-needs_you").locator(".personal-home-goal-card").first();
    const needsYouSource = await needsYouCard.locator("strong").innerText();
    const needsYouAction = await needsYouCard.locator("p").innerText();
    await needsYouCard.click();
    await page.getByRole("heading", { name: needsYouSource }).waitFor({ state: "visible" }).catch(() => {});
    await page.getByText(needsYouAction, { exact: true }).first().waitFor({ state: "visible" });
    await page.locator(".personal-object-list").first().getByRole("button").first().click();
    await page.getByText("需要你", { exact: true }).last().waitFor({ state: "visible" });
    await page.getByText("更多决定").click();
    await page.getByRole("button", { name: "稍后决定", exact: true }).click();
    await page.getByText("确认执行").waitFor({ state: "visible" });
    const deferredDecision = api.actionPreviews.find((preview) => preview.action_kind === "gate.resolve" && preview.normalized_parameters.decision === "defer");
    if (!deferredDecision) throw new Error("Decision defer did not create a Gate preview");
    await page.getByRole("button", { name: "稍后", exact: true }).click();
    await page.getByText(/已暂缓/).waitFor({ state: "visible" });
    if (!api.actionTransitions.some((transition) => transition.transition === "defer")) throw new Error("Proposal defer transition was not sent");
    await page.getByRole("button", { name: "关闭", exact: true }).click();
    await page.locator(".personal-manager-link").first().click();
    const sourceGoalCard = page.locator(".personal-home-goal-card").first();
    await sourceGoalCard.click();
    await goalNavigation.getByRole("button", { name: "Chat" }).click();
    if (!(await page.locator(".personal-run-row").count())) throw new Error("Source Goal did not expose its execution row after direct navigation");
    pass(3, "Needs-you and running cards navigate directly to their source Goal and expose typed details.");

    const visibleText = await page.locator("body").innerText();
    if (/session-goal-|turn-\d{6,}|\/Users\/|credential|provider payload|tool output/u.test(visibleText)) {
      fail(12, "Default surface exposes a raw runtime identifier, path, credential, or provider/tool payload.");
    } else {
      pass(12, "Default surface kept raw runtime ids, paths, credentials, and provider/tool payloads hidden.");
    }
    pass(13, "Manager cards retain Goal source lineage and Goal views retain Agent, schedule, and execution lineage.");

    await page.locator(".personal-goal-link").first().click();
    await goalNavigation.getByRole("button", { name: "Chat" }).click();
    await page.locator(".personal-run-row").first().click();
    await page.getByRole("tab", { name: "详情与操作" }).click();
    await page.getByLabel("输入纠偏信息").fill("保持运行，用于验证刷新恢复。 ");
    await page.getByRole("button", { name: "发送纠偏" }).click();
    let recoveryTurn;
    for (let attempt = 0; attempt < 40 && !recoveryTurn; attempt += 1) {
      recoveryTurn = api.turnRequests.find((turn) => turn.message.includes("刷新恢复"));
      if (!recoveryTurn) await page.waitForTimeout(50);
    }
    if (!recoveryTurn) throw new Error("Active recovery Turn was not accepted");

    try {
      await page.reload({ waitUntil: "networkidle" });
      await page.getByTestId("personal-goal-home").waitFor({ state: "visible" });
      await page.locator(".personal-goal-link").first().click();
      await goalNavigation.getByRole("button", { name: "Chat" }).click();
      await page.getByText("保持运行，用于验证刷新恢复。").waitFor({ state: "visible", timeout: 10_000 });
      await page.getByText("正在整理…").waitFor({ state: "hidden", timeout: 10_000 });
      const recovered = page.__loopxRuntime.sessions.get(recoveryTurn.sessionId);
      if (recovered?.active_turn_id !== null && recovered?.active_turn_id !== recoveryTurn.turnId) {
        throw new Error("Recovered Session points at a different active Turn");
      }
      pass(6, "Reload restored visible Goal history and resumed the active Turn SSE stream.");
    } catch (error) {
      fail(6, "Reload did not restore the active Goal conversation and reconnect its active Turn within 10 seconds.");
      await page.screenshot({ path: resolve(outputDir, "refresh-recovery-failed.png"), fullPage: true, animations: "disabled" });
      observations.push(`Refresh recovery failure: ${error.message}`);
    }

    const remote = await browser.newPage({ viewport: { width: 1512, height: 982 } });
    await installApi(remote);
    await remote.goto(url, { waitUntil: "networkidle" });
    await remote.getByRole("button", { name: "添加 SSH 隧道来源" }).click();
    await remote.getByLabel("本机 SSH Host").fill("remote-lab");
    await remote.getByText("ssh -N -L 8876:127.0.0.1:8766 remote-lab", { exact: true }).waitFor({ state: "visible" });
    await remote.getByRole("button", { name: "添加只读来源" }).click();
    await remote.getByText("远端只读投影", { exact: true }).waitFor({ state: "visible" });
    await remote.getByRole("button", { name: "添加 SSH 隧道来源" }).click();
    await remote.getByRole("tab", { name: "手动 URL" }).click();
    await remote.getByLabel("名称").fill("Remote build host");
    await remote.getByLabel("本地转发 URL").fill("http://127.0.0.1:8976/status.json");
    await remote.getByRole("button", { name: "添加只读来源" }).click();
    const remoteSourceSelect = remote.getByRole("combobox", { name: "选择控制面来源" });
    await remoteSourceSelect.click();
    const remoteSourceListbox = remote.getByRole("listbox", { name: "选择控制面来源" });
    if (await remoteSourceListbox.getByRole("option").count() !== 4) throw new Error("Multiple SSH tunnel sources were not retained in the source catalog");
    if (await remoteSourceListbox.locator(".personal-select-group-label").count() !== 1) throw new Error("Configured SSH Host quick-add group is missing");
    await remote.screenshot({ path: resolve(outputDir, "control-plane-select-open.png"), fullPage: false, animations: "disabled" });
    await remoteSourceListbox.getByRole("option", { name: "remote-build", exact: true }).click();
    await remote.locator(".personal-read-only-source", { hasText: "remote-build" }).waitFor({ state: "visible", timeout: 10_000 });
    pass(21, "Quick-add configured SSH host from the control-plane source dropdown.");
    await remoteSourceSelect.click();
    await remote.getByRole("listbox", { name: "选择控制面来源" }).getByRole("option", { name: "remote-lab", exact: true }).click();
    await remote.locator(".personal-read-only-source", { hasText: "remote-lab" }).waitFor({ state: "visible", timeout: 10_000 });
    await remote.locator(".personal-channel-composer").waitFor({ state: "detached", timeout: 3_000 });
    await remote.screenshot({ path: resolve(outputDir, "remote-read-only-source.png"), fullPage: false, animations: "disabled" });
    const visibleRemoteCreateButtons = await visibleElementCount(remote.locator('button[aria-label="创建 Goal"]'));
    if (visibleRemoteCreateButtons) throw new Error("Remote read-only source still exposed Goal creation");
    if (!(await remote.getByText("remote-lab", { exact: true }).count())) throw new Error("Remote source identity is not visible");
    await remote.locator(".personal-goal-link").first().click();
    await remote.getByRole("button", { name: "Tasks", current: "page" }).waitFor({ state: "visible" });
    await remote.locator(".personal-object-list", { hasText: "进行中" }).locator("button").first().click();
    await remote.getByRole("dialog", { name: "Todo 详情" }).waitFor({ state: "visible" });
    const remoteTodoDrawer = remote.getByRole("dialog", { name: "Todo 详情" });
    for (const label of ["标记完成", "管理任务"]) {
      const visibleMatches = await visibleElementCount(remoteTodoDrawer.getByRole("button", { name: label, exact: true }));
      if (visibleMatches) throw new Error(`Remote Todo drawer exposed ${label}`);
    }
    await remote.getByRole("button", { name: /关闭详情/ }).click();
    await remote.locator(".personal-object-list", { hasText: "定时与持续" }).locator("button").first().click();
    await remote.getByText("定时检查", { exact: true }).last().waitFor({ state: "visible" });
    const remoteScheduleDrawer = remote.getByRole("dialog", { name: "定时检查" });
    for (const label of ["立即运行", "暂停", "改为每 2 小时", "停止定时检查"]) {
      const visibleMatches = await visibleElementCount(remoteScheduleDrawer.getByRole("button", { name: label, exact: true }));
      if (visibleMatches) {
        throw new Error(`Remote schedule drawer exposed ${label}: ${(await remoteScheduleDrawer.innerText()).slice(0, 2000)}`);
      }
    }
    await remote.close();

    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
    await installApi(mobile);
    await mobile.goto(url, { waitUntil: "networkidle" });
    await mobile.getByTestId("personal-goal-home").waitFor({ state: "visible" });
    const mobileLaneSeparators = await mobile.locator(".personal-home-lane").evaluateAll((lanes) => lanes.map((lane) => {
      const style = getComputedStyle(lane);
      return { borderLeftWidth: style.borderLeftWidth, borderTopWidth: style.borderTopWidth };
    }));
    if (mobileLaneSeparators.some((lane) => lane.borderLeftWidth !== "0px")
      || mobileLaneSeparators.slice(1).some((lane) => lane.borderTopWidth !== "1px")) {
      throw new Error(`Mobile lanes did not switch to horizontal separators: ${JSON.stringify(mobileLaneSeparators)}`);
    }
    const mobileOverflow = await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (mobileOverflow > 1) throw new Error(`Mobile workspace has ${mobileOverflow}px horizontal overflow`);
    await mobile.screenshot({ path: resolve(outputDir, "mobile-first-screen.png"), fullPage: false, animations: "disabled" });
    const mobileComposer = mobile.getByLabel("向 LoopX 发送消息");
    const composerBox = await mobileComposer.boundingBox();
    if (!composerBox || composerBox.y + composerBox.height > 844) throw new Error("Mobile composer is outside the visible safe area");
    const mobileNavigationTrigger = mobile.locator(".personal-mobile-menu");
    await mobileNavigationTrigger.click();
    if (await mobileNavigationTrigger.getAttribute("aria-expanded") !== "true") {
      throw new Error(`Mobile navigation state did not open: ${await mobile.locator(".personal-workspace-shell").getAttribute("class")}`);
    }
    const mobileNavigationDialog = mobile.getByRole("dialog", { name: "Goal 导航" });
    await mobileNavigationDialog.waitFor({ state: "visible" });
    const mobileNavigationClose = mobile.getByRole("button", { name: "关闭 Goal 导航" });
    if (!(await mobileNavigationClose.evaluate((element) => element === document.activeElement))) {
      throw new Error("Mobile navigation did not move focus into its close control");
    }
    const mobileMain = mobile.locator(".personal-workspace-main");
    if (await mobileMain.getAttribute("aria-hidden") !== "true" || !(await mobileMain.evaluate((element) => element.inert))) {
      throw new Error("Mobile navigation left the background workspace exposed to assistive navigation");
    }
    await mobile.keyboard.press("Shift+Tab");
    if (!(await mobileNavigationDialog.evaluate((element) => element.contains(document.activeElement)))) {
      throw new Error("Mobile navigation focus escaped its modal boundary");
    }
    await mobile.keyboard.press("Tab");
    if (!(await mobileNavigationClose.evaluate((element) => element === document.activeElement))) {
      throw new Error("Mobile navigation focus did not wrap to its first control");
    }
    const mobileSidebarProbe = await mobile.locator(".personal-workspace-sidebar").evaluate((element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return { className: element.parentElement?.className, display: style.display, height: rect.height, width: rect.width, x: rect.x };
    });
    if (mobileSidebarProbe.display === "none" || mobileSidebarProbe.width < 100) {
      throw new Error(`Mobile sidebar did not become visible: ${JSON.stringify(mobileSidebarProbe)}`);
    }
    const mobileStoppedDirectory = mobile.locator(".personal-stopped-goals");
    if (await mobileStoppedDirectory.getAttribute("open") === null) await mobileStoppedDirectory.locator("summary").click();
    await mobile.screenshot({ path: resolve(outputDir, "mobile-goal-directory.png"), fullPage: false, animations: "disabled" });
    await mobile.keyboard.press("Escape");
    if (await mobileNavigationTrigger.getAttribute("aria-expanded") !== "false") {
      throw new Error("Mobile navigation did not close on Escape");
    }
    if (!(await mobileNavigationTrigger.evaluate((element) => element === document.activeElement))) {
      throw new Error("Mobile navigation did not restore focus to its trigger");
    }
    await mobileNavigationTrigger.click();
    const mobileManagerLink = mobile.locator(".personal-manager-link");
    try {
      await mobileManagerLink.waitFor({ state: "visible", timeout: 1500 });
    } catch {
      throw new Error(`Mobile manager link hidden after open: sidebar=${JSON.stringify(mobileSidebarProbe)} chain=${JSON.stringify(await mobileManagerLink.evaluate((element) => { const chain = []; let current = element; while (current && chain.length < 6) { const style = getComputedStyle(current); const rect = current.getBoundingClientRect(); chain.push({ className: current.className, display: style.display, height: rect.height, position: style.position, width: rect.width, x: rect.x }); current = current.parentElement; } return chain; }))}`);
    }
    await mobileManagerLink.click();
    await mobile.locator(".personal-home-board").waitFor({ state: "visible" });
    await mobileNavigationTrigger.click();
    await mobile.getByRole("dialog", { name: "Goal 导航" }).waitFor({ state: "visible" });
    await mobile.locator(".personal-goal-link").first().click();
    await mobile.getByRole("button", { name: "Tasks", current: "page" }).waitFor({ state: "visible" });
    await mobile.getByRole("button", { name: "打开 Goal 详情或能力配置" }).click();
    const mobileGoalToolsMenu = mobile.getByRole("group", { name: "Goal 设置" });
    await mobileGoalToolsMenu.waitFor({ state: "visible" });
    const mobileMenuBox = await mobileGoalToolsMenu.boundingBox();
    if (!mobileMenuBox || mobileMenuBox.x < 0 || mobileMenuBox.x + mobileMenuBox.width > 390) {
      throw new Error(`Mobile Goal settings menu escaped the viewport: ${JSON.stringify(mobileMenuBox)}`);
    }
    const mobileGoalOverflow = await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (mobileGoalOverflow > 1) throw new Error(`Mobile Goal header has ${mobileGoalOverflow}px horizontal overflow`);
    await mobile.screenshot({ path: resolve(outputDir, "mobile-goal-settings-menu.png"), fullPage: false, animations: "disabled" });
    await mobile.close();
    const progressive = await browser.newPage({ viewport: { width: 1512, height: 982 } });
    const progressiveApi = await installApi(progressive);
    progressiveApi.nextFullStatusDelayMs = 1_500;
    await progressive.goto(url, { waitUntil: "domcontentloaded" });
    await progressive.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 10_000 });
    const progressiveActiveVisibleBeforeStopped = await progressive.waitForFunction(
      () => document.querySelectorAll(".personal-goal-list:not(.is-stopped) .personal-goal-row").length === 5,
      null,
      { timeout: 3_000 },
    );
    const stoppedLoadingVisible = await progressive.locator(".personal-stopped-goals summary svg.is-spinning, .personal-stopped-goals summary svg[class*='spinning']").count();
    if (!progressiveActiveVisibleBeforeStopped) throw new Error("Active Goals did not render first while the stopped archive was still loading");
    if (stoppedLoadingVisible === 0) throw new Error("Stopped Goals archive did not expose an accessible loading state");
    await progressive.locator(".personal-stopped-goals .personal-goal-row").first().waitFor({ state: "attached", timeout: 6_000 });
    const progressiveStoppedCount = await progressive.locator(".personal-stopped-goals .personal-goal-row").count();
    if (progressiveStoppedCount !== 2) throw new Error(`Stopped Goals archive loaded the wrong count: ${progressiveStoppedCount}`);
    if ((await progressive.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 5) throw new Error("Active Goal directory regressed after the stopped archive loaded");
    pass(23, "The stopped archive loads after active Goals: active Goals are interactive first, the stopped section shows an accessible loading state, then stopped Goals arrive without replacing the page.");
    await progressive.close();

    const revisionRace = await browser.newPage({ viewport: { width: 1512, height: 982 } });
    const revisionRaceApi = await installApi(revisionRace);
    revisionRaceApi.captureNextStatusGeneration = true;
    revisionRaceApi.activationChangeAfterCapturedActive = {
      goalId: "product-release",
      activationState: "stopped",
    };
    revisionRaceApi.nextFullStatusDelayMs = 800;
    await revisionRace.goto(url, { waitUntil: "domcontentloaded" });
    await revisionRace.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 10_000 });
    await revisionRace.locator(".personal-stopped-goals .personal-goal-row").first().waitFor({ state: "attached", timeout: 6_000 });
    await revisionRace.waitForFunction(() => document.querySelectorAll(".personal-goal-list:not(.is-stopped) .personal-goal-row").length === 4, null, { timeout: 6_000 });
    if (await revisionRace.locator(".personal-stopped-goal-error").count()) {
      throw new Error("Registry revision mismatch did not converge after the bounded automatic resync");
    }
    if (await revisionRace.locator(".personal-goal-row").filter({ hasText: "Product Release" }).count() !== 1) {
      throw new Error("Registry revision race duplicated or omitted Product Release");
    }
    await revisionRace.close();

    const progressiveError = await browser.newPage({ viewport: { width: 1512, height: 982 } });
    const errorApi = await installApi(progressiveError);
    errorApi.failNextFullStatus = true;
    await progressiveError.goto(url, { waitUntil: "domcontentloaded" });
    await progressiveError.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 10_000 });
    await progressiveError.locator(".personal-stopped-goal-error").waitFor({ state: "visible", timeout: 4_000 });
    if ((await progressiveError.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 5) throw new Error("A failed stopped archive replaced the active workspace");
    await progressiveError.getByText("重试", { exact: true }).click();
    await progressiveError.locator(".personal-stopped-goals .personal-goal-row").first().waitFor({ state: "attached", timeout: 6_000 });
    const errorRecoveredCount = await progressiveError.locator(".personal-stopped-goals .personal-goal-row").count();
    if (errorRecoveredCount !== 2) throw new Error(`Retry did not recover the stopped archive: ${errorRecoveredCount}`);
    pass(24, "A stopped-archive failure keeps active Goals usable and offers a retry that restores the stopped section without a full-page error.");
    await progressiveError.close();

    if (await page.locator(".personal-workspace-shell").getAttribute("data-pw-theme") !== "loopx") throw new Error("Personal workspace did not start with the LoopX standard theme");
    if (await page.getByRole("button", { name: /切换到野兽主题|切换到默认主题/ }).count()) throw new Error("Workspace header still exposes the old theme toggle");
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await page.getByRole("button", { name: /外观/ }).click();
    await page.getByRole("radio", { name: /高对比/ }).click();
    if (await page.locator(".personal-settings-page").getAttribute("data-pw-theme") !== "brutal") throw new Error("Settings did not enable the high-contrast theme");
    await page.getByRole("radio", { name: /纸张/ }).click();
    if (await page.locator(".personal-settings-page").getAttribute("data-pw-theme") !== "paper") throw new Error("Settings did not enable the paper theme");
    await page.getByRole("radio", { name: /LoopX 标准/ }).click();
    if (await page.locator(".personal-settings-page").getAttribute("data-pw-theme") !== "loopx") throw new Error("Settings did not restore the LoopX standard theme");
    if (await page.evaluate(() => localStorage.getItem("loopx-pw-theme")) !== "loopx") throw new Error("LoopX standard theme was not persisted");
    await page.screenshot({ path: resolve(outputDir, "desktop-settings-loopx-theme.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: "返回工作区", exact: true }).click();
    if (await page.locator(".personal-workspace-shell").getAttribute("data-pw-theme") !== "loopx") throw new Error("Workspace did not apply the LoopX standard theme readback");
    await page.reload({ waitUntil: "networkidle" });
    await page.getByTestId("personal-goal-home").waitFor({ state: "visible" });
    if (await page.locator(".personal-workspace-shell").getAttribute("data-pw-theme") !== "loopx") throw new Error("LoopX standard theme did not survive reload");
    pass(16, "The Settings appearance tab switches among all three themes and restores the LoopX standard default.");
    await page.locator(".personal-manager-link").first().click();
    await page.waitForTimeout(600);
    const workerCards = await page.locator(".personal-worker-strip > button").count();
    if (workerCards !== 0) throw new Error(`Redundant Agent worker strip is still visible: ${workerCards}`);
    if (!(await page.locator(".personal-digest-card").isVisible().catch(() => false))) throw new Error("Morning digest card did not render on the manager home");
    pass(17, "Manager home keeps the morning digest while omitting the redundant Agent worker strip.");
    pass(20, "Empty and populated Tasks boards keep identical width and four equal columns at desktop and wide desktop viewports.");
    const report = { criteria: Object.fromEntries(results), observations };
    await writeFile(resolve(outputDir, "acceptance-results.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
    console.log(`personal-workspace-browser-smoke (${packaged ? "packaged" : "development"}): ok\npreview=${url}\nscreenshot=${resolve(outputDir, "desktop-first-screen.png")}`);
    const failures = [...results.entries()].filter(([, result]) => result.status !== "PASS");
    if (failures.length) throw new Error(`Acceptance failures: ${failures.map(([criterion, result]) => `${criterion} ${result.status}: ${result.note}`).join(" | ")}`);
  } finally {
    if ([...results.values()].some((result) => result.status !== "PASS")) {
      await writeFile(resolve(outputDir, "acceptance-results.json"), `${JSON.stringify({ criteria: Object.fromEntries(results), observations }, null, 2)}\n`, "utf8");
    }
    await browser?.close();
    server.kill("SIGTERM");
  }
}

await main();
