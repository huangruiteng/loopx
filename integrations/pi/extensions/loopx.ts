import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { StringEnum } from "@earendil-works/pi-ai";
import {
  DEFAULT_MAX_BYTES,
  DEFAULT_MAX_LINES,
  formatSize,
  truncateHead,
  withFileMutationQueue,
  type ExtensionAPI,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const LOOPX_BIN = process.env.LOOPX_BIN || "loopx";
const DEFAULT_AGENT_ID = process.env.LOOPX_PI_AGENT_ID || "pi-main";
const DEFAULT_CAPABILITIES = ["shell", "filesystem", "filesystem_write"];
const TOOL_TIMEOUT_MS = 60_000;

const ACTIONS = [
  "doctor",
  "status",
  "start_goal",
  "connect",
  "register_agent",
  "ready_score",
  "quota_should_run",
  "turn_plan",
  "todo_list",
  "todo_add",
  "todo_claim",
  "todo_complete",
  "history",
  "diagnose",
  "refresh_state",
  "spend_slot",
] as const;

const controlParameters = Type.Object({
  action: StringEnum(ACTIONS),
  project: Type.Optional(Type.String({ description: "Project directory; defaults to pi's current directory" })),
  goalId: Type.Optional(Type.String({ description: "Stable LoopX goal id" })),
  goalText: Type.Optional(Type.String({ description: "Exact long-running goal text" })),
  agentId: Type.Optional(Type.String({ description: `Registered agent id; defaults to ${DEFAULT_AGENT_ID}` })),
  todoId: Type.Optional(Type.String({ description: "Structured LoopX todo id" })),
  text: Type.Optional(Type.String({ description: "Public-safe todo text" })),
  role: Type.Optional(StringEnum(["agent", "user"] as const)),
  taskClass: Type.Optional(
    StringEnum(["advancement_task", "continuous_monitor", "user_gate", "user_action", "blocker"] as const),
  ),
  actionKind: Type.Optional(Type.String({ description: "Public-safe action token" })),
  taskRepository: Type.Optional(
    Type.String({ description: "Credential-free Git repository identity for an agent todo" }),
  ),
  evidence: Type.Optional(Type.String({ description: "Public-safe validation evidence or pointer" })),
  note: Type.Optional(Type.String({ description: "Public-safe lifecycle note" })),
  nextAgentTodo: Type.Optional(Type.String({ description: "Public-safe successor agent todo" })),
  nextAction: Type.Optional(Type.String({ description: "Durable next action for refresh_state" })),
  classification: Type.Optional(Type.String({ description: "Public-safe refresh classification" })),
  recommendedAction: Type.Optional(Type.String({ description: "Public-safe recommended action" })),
  deliveryBatchScale: Type.Optional(
    StringEnum(["test_only", "single_surface", "multi_surface", "implementation"] as const),
  ),
  deliveryOutcome: Type.Optional(
    StringEnum(["surface_only", "outcome_gap", "outcome_progress", "primary_goal_outcome"] as const),
  ),
  deliveryWorkspace: Type.Optional(
    Type.String({ description: "Git checkout that produced the accountable delivery; defaults to project" }),
  ),
  visionState: Type.Optional(Type.String({ description: "Agent vision lifecycle state for refresh_state" })),
  visionSummary: Type.Optional(Type.String({ description: "Bounded agent vision summary" })),
  visionRoleScope: Type.Optional(Type.String({ description: "Bounded agent role scope" })),
  visionAcceptance: Type.Optional(Type.String({ description: "Bounded agent vision acceptance summary" })),
  visionAdvancementPolicy: Type.Optional(StringEnum(["as_needed", "repeat_until_closed"] as const)),
  visionReplanTrigger: Type.Optional(Type.String({ description: "Bounded agent vision replan trigger" })),
  visionLastPatch: Type.Optional(Type.String({ description: "Bounded summary of the latest vision patch" })),
  visionTodoDelta: Type.Optional(
    Type.Array(Type.String({ description: "Compact public-safe todo delta" }), { maxItems: 8 }),
  ),
  visionUnchangedReason: Type.Optional(
    Type.String({ description: "Reason an existing agent vision remains unchanged" }),
  ),
  noFollowUp: Type.Optional(Type.Boolean({ description: "Record that a completed todo intentionally has no successor" })),
  execute: Type.Optional(Type.Boolean({ description: "Apply a mutation; false or omitted means preview/read-only" })),
  limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100 })),
});

type ControlParams = {
  action: (typeof ACTIONS)[number];
  project?: string;
  goalId?: string;
  goalText?: string;
  agentId?: string;
  todoId?: string;
  text?: string;
  role?: "agent" | "user";
  taskClass?: "advancement_task" | "continuous_monitor" | "user_gate" | "user_action" | "blocker";
  actionKind?: string;
  taskRepository?: string;
  evidence?: string;
  note?: string;
  nextAgentTodo?: string;
  nextAction?: string;
  classification?: string;
  recommendedAction?: string;
  deliveryBatchScale?: "test_only" | "single_surface" | "multi_surface" | "implementation";
  deliveryOutcome?: "surface_only" | "outcome_gap" | "outcome_progress" | "primary_goal_outcome";
  deliveryWorkspace?: string;
  visionState?: string;
  visionSummary?: string;
  visionRoleScope?: string;
  visionAcceptance?: string;
  visionAdvancementPolicy?: "as_needed" | "repeat_until_closed";
  visionReplanTrigger?: string;
  visionLastPatch?: string;
  visionTodoDelta?: string[];
  visionUnchangedReason?: string;
  noFollowUp?: boolean;
  execute?: boolean;
  limit?: number;
};

type ExecContext = {
  cwd: string;
  signal?: AbortSignal;
};

function required(value: string | undefined, name: string): string {
  const normalized = value?.trim();
  if (!normalized) throw new Error(`${name} is required for this LoopX action`);
  return normalized;
}

function projectPath(value: string | undefined, cwd: string): string {
  if (!value?.trim()) return cwd;
  const expanded = value.startsWith("~/") ? join(homedir(), value.slice(2)) : value;
  return isAbsolute(expanded) ? resolve(expanded) : resolve(cwd, expanded);
}

function addCapabilities(args: string[]): void {
  for (const capability of DEFAULT_CAPABILITIES) {
    args.push("--available-capability", capability);
  }
}

function buildArgs(
  params: ControlParams,
  cwd: string,
): { args: string[]; project: string; commandCwd: string; agentId: string } {
  const project = projectPath(params.project, cwd);
  const deliveryWorkspace = projectPath(params.deliveryWorkspace, project);
  const agentId = params.agentId?.trim() || DEFAULT_AGENT_ID;
  const limit = String(params.limit ?? 20);
  const goalId = params.goalId?.trim();
  let args: string[];
  let commandCwd = project;

  switch (params.action) {
    case "doctor":
      args = ["--format", "json", "doctor", "--deep"];
      break;
    case "status":
      args = ["--format", "json", "status", "--limit", limit];
      if (goalId) args.push("--goal-id", goalId, "--agent-id", agentId);
      break;
    case "start_goal":
      args = [
        "--format",
        "json",
        "start-goal",
        "--guided",
        "--project",
        project,
        "--host-surface",
        "pi",
        "--agent-id",
        agentId,
        "--goal-text",
        required(params.goalText, "goalText"),
      ];
      if (goalId) args.push("--goal-id", goalId);
      addCapabilities(args);
      break;
    case "connect":
      args = [
        "--format",
        "json",
        "bootstrap",
        "--project",
        project,
        "--objective",
        required(params.goalText, "goalText"),
        "--adapter-kind",
        "read_only_project_map_v0",
        "--adapter-status",
        "connected-read-only",
        "--no-onboarding-scan",
        "--codex-app-heartbeat",
        "no",
      ];
      if (goalId) args.push("--goal-id", goalId);
      if (!params.execute) args.push("--dry-run");
      break;
    case "register_agent":
      args = [
        "--format",
        "json",
        "register-agent",
        "--goal-id",
        required(goalId, "goalId"),
        "--agent-id",
        agentId,
      ];
      if (params.execute) args.push("--execute");
      break;
    case "ready_score":
      args = [
        "--format",
        "json",
        "ready-score",
        "--goal-id",
        required(goalId, "goalId"),
        "--agent-id",
        agentId,
      ];
      break;
    case "quota_should_run":
      args = [
        "--format",
        "json",
        "quota",
        "should-run",
        "--goal-id",
        required(goalId, "goalId"),
        "--agent-id",
        agentId,
        "--turn-envelope",
      ];
      addCapabilities(args);
      break;
    case "turn_plan":
      args = [
        "--format",
        "json",
        "turn",
        "plan",
        "--goal-id",
        required(goalId, "goalId"),
        "--agent-id",
        agentId,
        "--host",
        "generic-cli",
        "--execution-mode",
        "interactive-visible",
      ];
      addCapabilities(args);
      break;
    case "todo_list":
      args = ["--format", "json", "todo", "list", "--goal-id", required(goalId, "goalId")];
      break;
    case "todo_add":
      args = [
        "--format",
        "json",
        "todo",
        "add",
        "--goal-id",
        required(goalId, "goalId"),
        "--role",
        params.role ?? "agent",
        "--text",
        required(params.text, "text"),
        "--task-class",
        params.taskClass ?? (params.role === "user" ? "user_gate" : "advancement_task"),
      ];
      if (params.actionKind) args.push("--action-kind", params.actionKind);
      if (params.taskRepository) args.push("--task-repository", params.taskRepository);
      if (params.role !== "user") args.push("--claimed-by", agentId);
      if (!params.execute) args.push("--dry-run");
      break;
    case "todo_claim":
      args = [
        "--format",
        "json",
        "todo",
        "claim",
        "--goal-id",
        required(goalId, "goalId"),
        "--todo-id",
        required(params.todoId, "todoId"),
        "--claimed-by",
        agentId,
      ];
      if (!params.execute) args.push("--dry-run");
      break;
    case "todo_complete":
      args = [
        "--format",
        "json",
        "todo",
        "complete",
        "--goal-id",
        required(goalId, "goalId"),
        "--todo-id",
        required(params.todoId, "todoId"),
        "--claimed-by",
        agentId,
      ];
      if (params.evidence) args.push("--evidence", params.evidence);
      if (params.note) args.push("--note", params.note);
      if (params.nextAgentTodo) args.push("--next-agent-todo", params.nextAgentTodo);
      if (params.noFollowUp) args.push("--no-follow-up");
      if (!params.execute) args.push("--dry-run");
      break;
    case "history":
      args = ["--format", "json", "history", "--goal-id", required(goalId, "goalId"), "--limit", limit];
      break;
    case "diagnose":
      args = [
        "--format",
        "json",
        "diagnose",
        "--goal-id",
        required(goalId, "goalId"),
        "--agent-id",
        agentId,
        "--limit",
        limit,
      ];
      addCapabilities(args);
      break;
    case "refresh_state":
      args = [
        "--format",
        "json",
        "refresh-state",
        "--goal-id",
        required(goalId, "goalId"),
        "--project",
        project,
        "--agent-id",
        agentId,
        "--progress-scope",
        "goal",
      ];
      if (params.classification) args.push("--classification", params.classification);
      if (params.recommendedAction) args.push("--recommended-action", params.recommendedAction);
      if (params.nextAction) args.push("--next-action", params.nextAction);
      if (params.deliveryBatchScale) args.push("--delivery-batch-scale", params.deliveryBatchScale);
      if (params.deliveryOutcome) args.push("--delivery-outcome", params.deliveryOutcome);
      if (params.deliveryWorkspace) args.push("--delivery-workspace-path", deliveryWorkspace);
      if (params.visionState) args.push("--vision-state", params.visionState);
      if (params.visionSummary) args.push("--vision-summary", params.visionSummary);
      if (params.visionRoleScope) args.push("--vision-role-scope", params.visionRoleScope);
      if (params.visionAcceptance) args.push("--vision-acceptance", params.visionAcceptance);
      if (params.visionAdvancementPolicy) {
        args.push("--vision-advancement-policy", params.visionAdvancementPolicy);
      }
      if (params.visionReplanTrigger) args.push("--vision-replan-trigger", params.visionReplanTrigger);
      if (params.visionLastPatch) args.push("--vision-last-patch", params.visionLastPatch);
      for (const delta of params.visionTodoDelta ?? []) args.push("--vision-todo-delta", delta);
      if (params.visionUnchangedReason) {
        args.push("--vision-unchanged-reason", params.visionUnchangedReason);
      }
      if (!params.execute) args.push("--dry-run");
      break;
    case "spend_slot":
      commandCwd = deliveryWorkspace;
      args = [
        "--format",
        "json",
        ...(params.deliveryWorkspace ? ["--registry", join(project, ".loopx", "registry.json")] : []),
        "quota",
        "spend-slot",
        "--goal-id",
        required(goalId, "goalId"),
        "--agent-id",
        agentId,
        "--slots",
        "1",
        "--source",
        "controller",
        params.execute ? "--execute" : "--dry-run",
      ];
      addCapabilities(args);
      break;
    default:
      throw new Error(`Unsupported LoopX action: ${String(params.action)}`);
  }

  return { args, project, commandCwd, agentId };
}

async function ensureLocalLoopxExcludes(pi: ExtensionAPI, project: string, signal?: AbortSignal) {
  const gitPath = await pi.exec("git", ["rev-parse", "--git-path", "info/exclude"], {
    cwd: project,
    signal,
    timeout: 5000,
  });
  if (gitPath.code !== 0) {
    return { updated: false, reason: "not_a_git_repository" };
  }

  const rawPath = gitPath.stdout.trim();
  const excludePath = isAbsolute(rawPath) ? rawPath : resolve(project, rawPath);
  const requiredPatterns = [".loopx/", ".codex/goals/", ".local/"];

  return withFileMutationQueue(excludePath, async () => {
    let current = "";
    try {
      current = await readFile(excludePath, "utf8");
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code !== "ENOENT") throw error;
    }

    const existing = new Set(
      current
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean),
    );
    const missing = requiredPatterns.filter((pattern) => !existing.has(pattern));
    if (missing.length === 0) return { updated: false, path: excludePath, added: [] };

    const prefix = current.length === 0 || current.endsWith("\n") ? "" : "\n";
    const block = `${prefix}# LoopX local state (managed by loopx-pi-adapter)\n${missing.join("\n")}\n`;
    await mkdir(dirname(excludePath), { recursive: true });
    await writeFile(excludePath, current + block, "utf8");
    return { updated: true, path: excludePath, added: missing };
  });
}

async function runLoopx(pi: ExtensionAPI, params: ControlParams, ctx: ExecContext) {
  const plan = buildArgs(params, ctx.cwd);
  const result = await pi.exec(LOOPX_BIN, plan.args, {
    cwd: plan.commandCwd,
    signal: ctx.signal,
    timeout: TOOL_TIMEOUT_MS,
  });

  if (result.code !== 0) {
    const errorText = (result.stderr || result.stdout || "LoopX command failed").trim();
    throw new Error(errorText.slice(0, 8000));
  }

  const output = result.stdout.trim() || "{}";
  let parsed: unknown;
  try {
    parsed = JSON.parse(output);
  } catch {
    parsed = undefined;
  }

  if (params.action === "connect" && params.execute && parsed && typeof parsed === "object") {
    const goalId = (parsed as Record<string, unknown>).goal_id;
    if (typeof goalId === "string" && goalId) {
      const registration = await pi.exec(
        LOOPX_BIN,
        ["--format", "json", "register-agent", "--goal-id", goalId, "--agent-id", plan.agentId, "--execute"],
        { cwd: plan.project, signal: ctx.signal, timeout: TOOL_TIMEOUT_MS },
      );
      if (registration.code !== 0) {
        const detail = (registration.stderr || registration.stdout || "agent registration failed").trim();
        throw new Error(`Project connected, but pi agent registration failed: ${detail.slice(0, 4000)}`);
      }
      try {
        (parsed as Record<string, unknown>).pi_agent_registration = JSON.parse(registration.stdout);
      } catch {
        (parsed as Record<string, unknown>).pi_agent_registration = registration.stdout.trim();
      }
    }
    (parsed as Record<string, unknown>).pi_local_excludes = await ensureLocalLoopxExcludes(
      pi,
      plan.project,
      ctx.signal,
    );
  }

  const rendered = parsed === undefined ? output : JSON.stringify(parsed, null, 2);
  const truncation = truncateHead(rendered, {
    maxLines: DEFAULT_MAX_LINES,
    maxBytes: DEFAULT_MAX_BYTES,
  });
  let text = truncation.content;
  let fullOutputPath: string | undefined;

  if (truncation.truncated) {
    const dir = await mkdtemp(join(tmpdir(), "loopx-pi-"));
    fullOutputPath = join(dir, `${params.action}.json`);
    await writeFile(fullOutputPath, rendered, "utf8");
    text += `\n\n[LoopX output truncated to ${truncation.outputLines} lines / ${formatSize(truncation.outputBytes)}. Full output: ${fullOutputPath}]`;
  }

  return {
    content: [{ type: "text" as const, text }],
    details: {
      action: params.action,
      project: plan.project,
      commandCwd: plan.commandCwd,
      agentId: plan.agentId,
      execute: params.execute === true,
      truncated: truncation.truncated,
      fullOutputPath,
    },
  };
}

function statusLines(payload: Record<string, unknown>): string[] {
  const queue = payload.attention_queue as { item_count?: number; items?: Array<Record<string, unknown>> } | undefined;
  const lines = [
    `LoopX | goals ${String(payload.goal_count ?? 0)} | runs ${String(payload.run_count ?? 0)} | attention ${String(queue?.item_count ?? 0)}`,
  ];
  for (const item of queue?.items?.slice(0, 5) ?? []) {
    lines.push(
      `${String(item.severity ?? "info")} | ${String(item.goal_id ?? "unknown")} | ${String(item.recommended_action ?? item.status ?? "inspect status")}`,
    );
  }
  return lines;
}

export default function loopxPiAdapter(pi: ExtensionAPI) {
  pi.registerTool({
    name: "loopx_control",
    label: "LoopX Control",
    description:
      `Inspect and update LoopX's local long-running-goal control plane through structured actions. ` +
      `Mutating actions are previews unless execute=true. Output is truncated to ${DEFAULT_MAX_LINES} lines or ${formatSize(DEFAULT_MAX_BYTES)}.`,
    promptSnippet: "Inspect or update LoopX goals, quota, todos, history, and state writeback",
    promptGuidelines: [
      "Use loopx_control instead of constructing raw loopx shell commands when the requested action is supported.",
      "Before a LoopX work segment, use loopx_control status and quota_should_run; spend a slot only after validated work and refresh_state writeback.",
      "Do not set execute=true for LoopX mutations unless the user explicitly started a goal or approved the state change.",
    ],
    parameters: controlParameters,
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      return runLoopx(pi, params as ControlParams, { cwd: ctx.cwd, signal });
    },
  });

  pi.registerCommand("loopx", {
    description: "Inspect LoopX or start/continue a long-running goal",
    handler: async (args, ctx) => {
      if (!ctx.isIdle()) {
        ctx.ui.notify("Agent is busy; run /loopx after the current turn settles.", "warning");
        return;
      }
      const goalText = args.trim();
      if (ctx.mode === "print") {
        try {
          const commandArgs = goalText
            ? [
                "--format",
                "json",
                "start-goal",
                "--guided",
                "--project",
                ctx.cwd,
                "--host-surface",
                "pi",
                "--agent-id",
                DEFAULT_AGENT_ID,
                "--goal-text",
                goalText,
              ]
            : ["--format", "json", "status", "--limit", "20"];
          if (goalText) addCapabilities(commandArgs);
          const result = await pi.exec(LOOPX_BIN, commandArgs, { cwd: ctx.cwd, timeout: TOOL_TIMEOUT_MS });
          if (result.code !== 0) throw new Error(result.stderr || result.stdout || "LoopX command failed");
          const payload = JSON.parse(result.stdout) as Record<string, unknown>;
          if (goalText) {
            const connection = payload.project_connection as Record<string, unknown> | undefined;
            const next = payload.recommended_next_step as Record<string, unknown> | undefined;
            console.log(
              `LoopX preview | goal ${String(payload.goal_id ?? "unknown")} | connection ${String(connection?.connection_state ?? "unknown")} | next ${String(next?.kind ?? "inspect packet")}`,
            );
          } else {
            console.log(statusLines(payload).join("\n"));
          }
        } catch (error) {
          console.error(error instanceof Error ? error.message : String(error));
        }
        return;
      }

      const request = goalText
        ? `Start or continue this LoopX goal in the current project: ${goalText}\n\nThis /loopx invocation is explicit user intent to create or reuse local LoopX state. Load the loopx-pi skill, use loopx_control start_goal first, connect only if needed, create a concise ranked todo plan without duplicates, then run the first quota-allowed bounded segment. Do not install a background scheduler.`
        : "Inspect the current project's LoopX state in read-only mode. Load the loopx-pi skill, use loopx_control status, and report the active goal, user gate, top runnable agent todo, and next safe action. Do not mutate state.";
      pi.sendUserMessage(request);
    },
  });

  pi.registerCommand("loopx-turn", {
    description: "Run one quota-gated LoopX work segment",
    handler: async (args, ctx) => {
      if (!ctx.isIdle()) {
        ctx.ui.notify("Agent is busy; run /loopx-turn after the current turn settles.", "warning");
        return;
      }
      const goalHint = args.trim();
      pi.sendUserMessage(
        `Run exactly one bounded LoopX turn in the current project${goalHint ? ` for goal ${goalHint}` : ""}. ` +
          "Load the loopx-pi skill. Inspect status and quota first, respect every user/capability gate, claim at most one runnable todo, perform and validate one coherent work segment, then complete/update the todo, refresh state, and spend one slot only when validated delivery was written back. Do not schedule another turn.",
      );
    },
  });

  pi.registerCommand("loopx-status", {
    description: "Show a compact read-only LoopX status widget",
    handler: async (_args, ctx) => {
      try {
        const result = await pi.exec(LOOPX_BIN, ["--format", "json", "status", "--limit", "20"], {
          cwd: ctx.cwd,
          timeout: TOOL_TIMEOUT_MS,
        });
        if (result.code !== 0) throw new Error(result.stderr || result.stdout || "LoopX status failed");
        const payload = JSON.parse(result.stdout) as Record<string, unknown>;
        ctx.ui.setWidget("loopx-pi-status", statusLines(payload), { placement: "aboveEditor" });
        ctx.ui.notify("LoopX status refreshed", "info");
      } catch (error) {
        ctx.ui.notify(error instanceof Error ? error.message : String(error), "error");
      }
    },
  });

  pi.on("session_start", async (_event, ctx) => {
    try {
      const result = await pi.exec(LOOPX_BIN, ["version"], { cwd: ctx.cwd, timeout: 5000 });
      if (result.code === 0) ctx.ui.setStatus("loopx-pi", result.stdout.trim());
    } catch {
      ctx.ui.setStatus("loopx-pi", "LoopX unavailable");
    }
  });
}
