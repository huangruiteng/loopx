// <!-- loopx-managed-slash-command:v1 command=/goal surface=opencode-runtime -->
import { execFile as execFileCallback } from "node:child_process"
import { promises as fs } from "node:fs"
import os from "node:os"
import path from "node:path"
import { promisify } from "node:util"


const execFile = promisify(execFileCallback)
const BRIDGE_SCHEMA_VERSION = "loopx_opencode_goal_bridge_v0"
const TERMINAL_STATE_SCHEMA_VERSION = "goal_terminal_state_v0"
const SOURCE_COMPLETENESS_SCHEMA_VERSION = "goal_terminal_source_completeness_v0"
const DEFAULT_RETRY_MINUTES = 3
const LOOPX_GOAL_LIMITS = {
  maxTurns: 10000,
  maxDurationMs: 30 * 24 * 60 * 60 * 1000,
  maxTokens: 1_000_000_000,
}


function sessionIDFromEvent(event) {
  return (
    event?.properties?.sessionID ||
    event?.properties?.info?.sessionID ||
    event?.data?.sessionID ||
    event?.data?.info?.sessionID ||
    null
  )
}


function isIdleEvent(event) {
  return (
    event?.type === "session.idle" ||
    (event?.type === "session.status" && event?.properties?.status?.type === "idle")
  )
}


function shouldPauseForHostEvent(event) {
  if (event?.type === "session.error") return true
  if (event?.type !== "permission.replied") return false
  const reply = String(
    event?.properties?.reply ??
      event?.properties?.response ??
      event?.data?.reply ??
      event?.data?.response ??
      "",
  )
  return /^(?:reject(?:ed)?|deny|denied)$/i.test(reply)
}


function textFromParts(parts) {
  return (parts || [])
    .filter((part) => part?.type === "text" && !part?.ignored)
    .map((part) => part.text || "")
    .join("\n")
    .trim()
}


function parseToolResult(value) {
  if (typeof value !== "string") return null
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}


function toolResultSucceeded(value) {
  const parsed = parseToolResult(value)
  return parsed?.ok === true || (typeof value === "string" && /^Goal (?:cleared|completed)/i.test(value))
}


function toolResultHasError(value, error) {
  const parsed = parseToolResult(value)
  return parsed?.ok === false && parsed?.error === error
}


function sanitizedSessionID(sessionID) {
  const value = String(sessionID || "").replace(/[^A-Za-z0-9_-]/g, "_")
  if (!value) throw new Error("OpenCode session id is required")
  return value.slice(0, 160)
}


function defaultStateRoot() {
  if (process.env.LOOPX_OPENCODE_STATE_DIR) {
    return path.resolve(process.env.LOOPX_OPENCODE_STATE_DIR)
  }
  const xdgState = process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state")
  return path.join(xdgState, "loopx", "opencode")
}


export function createFileBindingStore({ root = defaultStateRoot() } = {}) {
  const target = (sessionID) => path.join(root, `${sanitizedSessionID(sessionID)}.json`)
  return {
    async read(sessionID) {
      try {
        const payload = JSON.parse(await fs.readFile(target(sessionID), "utf8"))
        if (payload?.schemaVersion !== BRIDGE_SCHEMA_VERSION || payload?.sessionID !== sessionID) {
          throw new Error("invalid LoopX OpenCode binding")
        }
        return payload
      } catch (error) {
        if (error?.code === "ENOENT") return null
        throw error
      }
    },
    async write(sessionID, binding) {
      await fs.mkdir(root, { recursive: true, mode: 0o700 })
      const destination = target(sessionID)
      const temporary = `${destination}.${process.pid}.${Date.now()}.tmp`
      const payload = {
        schemaVersion: BRIDGE_SCHEMA_VERSION,
        sessionID,
        ...binding,
        updatedAt: new Date().toISOString(),
      }
      await fs.writeFile(temporary, `${JSON.stringify(payload, null, 2)}\n`, {
        encoding: "utf8",
        mode: 0o600,
      })
      await fs.rename(temporary, destination)
      await fs.chmod(destination, 0o600)
      return payload
    },
    async remove(sessionID) {
      try {
        await fs.unlink(target(sessionID))
      } catch (error) {
        if (error?.code !== "ENOENT") throw error
      }
    },
  }
}


export async function probeLoopxQuota(binding, { directory, execFileImpl = execFile } = {}) {
  const args = []
  if (binding.registryPath) args.push("--registry", binding.registryPath)
  args.push(
    "--format",
    "json",
    "quota",
    "should-run",
    "--goal-id",
    binding.goalId,
    "--runtime-profile",
    "generic_cli",
    "--include-scheduler-detail",
  )
  if (binding.agentId) args.push("--agent-id", binding.agentId)
  for (const capability of binding.availableCapabilities || []) {
    args.push("--available-capability", capability)
  }
  const { stdout } = await execFileImpl(process.env.LOOPX_BIN || "loopx", args, {
    cwd: binding.directory || directory,
    timeout: 20_000,
    maxBuffer: 4 * 1024 * 1024,
  })
  const decision = JSON.parse(stdout || "{}")
  if (!decision || typeof decision !== "object" || Array.isArray(decision)) {
    throw new Error("loopx quota should-run returned a non-object payload")
  }
  return decision
}


export function isTerminalNoFollowup(decision) {
  const frontier = decision?.goal_frontier_projection
  const terminal = frontier?.terminal_state
  const completeness = frontier?.source_completeness
  return Boolean(
    decision?.should_run === false &&
      decision?.effective_action === "terminal_no_followup" &&
      terminal?.schema_version === TERMINAL_STATE_SCHEMA_VERSION &&
      terminal?.kind === "no_followup" &&
      terminal?.derived === true &&
      terminal?.source === "validated_goal_closure" &&
      completeness?.schema_version === SOURCE_COMPLETENESS_SCHEMA_VERSION &&
      completeness?.user_todos === "valid" &&
      completeness?.agent_todos === "valid",
  )
}


function shouldRunNow(decision) {
  return decision?.scheduler_hint?.action === "run_now" || decision?.should_run === true
}


function waitPlan(decision, binding) {
  const local = decision?.scheduler_hint?.unchanged_poll?.local_scheduler
  if (!local || local === "stop") return { stop: true }
  const token = decision?.scheduler_hint?.reset_policy?.reset_token || ""
  const sameIdentity = token && token === binding.schedulerToken
  const unchangedPolls = sameIdentity ? Number(binding.unchangedPolls || 0) : 0
  const limit = Number.isInteger(local.unchanged_poll_limit) ? local.unchanged_poll_limit : null
  if (limit !== null && unchangedPolls >= limit) return { stop: true }
  const progression = Array.isArray(local.example_progression_minutes)
    ? local.example_progression_minutes.filter((value) => Number(value) > 0)
    : []
  const fallback = Number(local.recommended_interval_minutes || DEFAULT_RETRY_MINUTES)
  const minutes = progression.length
    ? Number(progression[Math.min(unchangedPolls, progression.length - 1)])
    : fallback
  return {
    stop: false,
    minutes: Number.isFinite(minutes) && minutes > 0 ? minutes : DEFAULT_RETRY_MINUTES,
    schedulerToken: token,
    unchangedPolls: unchangedPolls + 1,
  }
}


function toolContext(context, sessionID) {
  return {
    sessionID,
    directory: context.directory,
    worktree: context.worktree,
  }
}


async function executeTool(definition, args, context) {
  if (!definition || typeof definition.execute !== "function") {
    throw new Error("required opencode-goal-plugin tool is unavailable")
  }
  return definition.execute(args, context)
}


function commandKind(argumentsText) {
  const normalized = String(argumentsText || "").trim().toLowerCase()
  if (!normalized || normalized === "status" || normalized === "history" || normalized === "list") {
    return "inspect"
  }
  if (["clear", "stop", "off", "reset", "none", "cancel"].includes(normalized)) return "clear"
  if (normalized === "resume") return "resume"
  if (normalized === "pause") return "pause"
  if (normalized.startsWith("edit ")) return "edit"
  return "replace"
}


export function createLoopxGoalPlugin({
  GoalPlugin,
  tool,
  bindingStore = createFileBindingStore(),
  quotaProbe = probeLoopxQuota,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
} = {}) {
  if (typeof GoalPlugin !== "function") throw new Error("GoalPlugin factory is required")
  if (typeof tool !== "function" || !tool.schema) throw new Error("OpenCode tool helper is required")

  return async function LoopXGoalPlugin(context) {
    const timers = new Map()
    const evaluations = new Map()
    const pendingGoalCommands = new Map()
    const initializedSessions = new Set()
    let disposed = false

    const log = async (level, message, extra = {}) => {
      try {
        await context.client?.app?.log?.({
          body: { service: "loopx-opencode-goal", level, message, extra },
        })
      } catch {
        // Logging must never change the continuation policy.
      }
    }

    const cancelScheduled = (sessionID) => {
      const timer = timers.get(sessionID)
      if (timer !== undefined) clearTimer(timer)
      timers.delete(sessionID)
    }

    const readBinding = async (sessionID) => bindingStore.read(sessionID)
    const updateBinding = async (sessionID, changes) => {
      const current = await readBinding(sessionID)
      if (!current) return null
      return bindingStore.write(sessionID, { ...current, ...changes })
    }

    const auditor = async ({ sessionID }) => {
      const binding = await readBinding(sessionID)
      if (!binding) return { approved: true }
      try {
        const decision = await quotaProbe(binding, { directory: context.directory })
        return isTerminalNoFollowup(decision)
          ? { approved: true }
          : {
              approved: false,
              reason: "LoopX has not derived terminal no-follow-up from a complete empty frontier.",
            }
      } catch (error) {
        return {
          approved: false,
          reason: `LoopX terminal audit unavailable: ${error?.message || String(error)}`,
        }
      }
    }

    const base = await GoalPlugin(context, { auditor })
    const baseTools = base.tool || {}
    const baseGoalSet = baseTools.goal_set
    const baseGoalResume = baseTools.goal_resume
    const baseGoalComplete = baseTools.goal_complete
    const baseEvent = base.event
    const baseChatMessage = base["chat.message"]
    const baseCommand = base["command.execute.before"]

    const completeTerminalGoal = async (sessionID, binding, decision) => {
      try {
        const reason = String(decision?.reason || "LoopX validated an empty terminal frontier.")
        const result = await executeTool(
          baseGoalComplete,
          {
            summary: "LoopX validated terminal no-follow-up.",
            criteria: [
              {
                criterion: "LoopX reports validated goal closure with no remaining follow-up.",
                evidence: [reason],
              },
            ],
          },
          toolContext(context, sessionID),
        )
        if (toolResultSucceeded(result) || toolResultHasError(result, "no_active_goal")) {
          await bindingStore.remove(sessionID)
          cancelScheduled(sessionID)
          await log("info", "LoopX terminal frontier completed the OpenCode goal", {
            goalId: binding.goalId,
            sessionID,
          })
          return
        }
        await log("warn", "OpenCode goal completion was rejected after LoopX terminal state", {
          goalId: binding.goalId,
          sessionID,
        })
      } catch (error) {
        await log("error", "OpenCode goal completion failed", {
          goalId: binding.goalId,
          sessionID,
          error: error?.message || String(error),
        })
      }
    }

    const scheduleEvaluation = (sessionID, minutes) => {
      if (disposed) return
      cancelScheduled(sessionID)
      const timer = setTimer(async () => {
        timers.delete(sessionID)
        if (disposed) return
        try {
          await evaluateIdle(sessionID, {
            event: { type: "session.idle", properties: { sessionID } },
          })
        } catch (error) {
          await log("error", "Scheduled LoopX quota evaluation failed closed", {
            sessionID,
            error: error?.message || String(error),
          })
        }
      }, Math.max(1, minutes) * 60_000)
      if (typeof timer?.unref === "function") timer.unref()
      timers.set(sessionID, timer)
    }

    const evaluateIdleOnce = async (sessionID, input) => {
      if (disposed) return
      let binding
      try {
        binding = await readBinding(sessionID)
      } catch (error) {
        cancelScheduled(sessionID)
        await log("error", "Invalid LoopX OpenCode binding; continuation failed closed", {
          sessionID,
          error: error?.message || String(error),
        })
        return
      }
      if (!binding) {
        await baseEvent?.(input)
        return
      }
      if (binding.autoResume === false) {
        cancelScheduled(sessionID)
        return
      }

      let decision
      try {
        decision = await quotaProbe(binding, { directory: context.directory })
      } catch (error) {
        await log("warn", "LoopX quota probe failed closed; scheduling a bounded retry", {
          goalId: binding.goalId,
          sessionID,
          error: error?.message || String(error),
        })
        scheduleEvaluation(sessionID, DEFAULT_RETRY_MINUTES)
        return
      }
      if (disposed) return

      const currentBinding = await readBinding(sessionID)
      if (
        !currentBinding ||
        currentBinding.autoResume === false ||
        currentBinding.goalId !== binding.goalId
      ) {
        cancelScheduled(sessionID)
        return
      }
      binding = currentBinding

      if (isTerminalNoFollowup(decision)) {
        await completeTerminalGoal(sessionID, binding, decision)
        return
      }

      if (shouldRunNow(decision)) {
        cancelScheduled(sessionID)
        await bindingStore.write(sessionID, {
          ...binding,
          schedulerToken: "",
          unchangedPolls: 0,
        })
        if (!initializedSessions.has(sessionID)) {
          initializedSessions.add(sessionID)
          try {
            await executeTool(baseGoalResume, {}, toolContext(context, sessionID))
          } catch (error) {
            await log("warn", "OpenCode goal resume probe failed before continuation", {
              goalId: binding.goalId,
              sessionID,
              error: error?.message || String(error),
            })
          }
        }
        if (disposed) return
        await baseEvent?.(input)
        return
      }

      const wait = waitPlan(decision, binding)
      if (wait.stop) {
        cancelScheduled(sessionID)
        await log("info", "LoopX unchanged-poll limit stopped the OpenCode timer", {
          goalId: binding.goalId,
          sessionID,
        })
        return
      }
      await bindingStore.write(sessionID, {
        ...binding,
        schedulerToken: wait.schedulerToken,
        unchangedPolls: wait.unchangedPolls,
      })
      scheduleEvaluation(sessionID, wait.minutes)
    }

    const evaluateIdle = (sessionID, input) => {
      if (disposed) return Promise.resolve()
      const existing = evaluations.get(sessionID)
      if (existing) return existing
      const evaluation = evaluateIdleOnce(sessionID, input).finally(() => {
        if (evaluations.get(sessionID) === evaluation) evaluations.delete(sessionID)
      })
      evaluations.set(sessionID, evaluation)
      return evaluation
    }

    const activateTool = tool({
      description:
        "Activate a LoopX-backed OpenCode goal after LoopX start-goal has written todos and produced a heartbeat task_body.",
      args: {
        goalId: tool.schema.string(),
        objective: tool.schema.string(),
        agentId: tool.schema.string().optional(),
        registryPath: tool.schema.string().optional(),
        availableCapabilities: tool.schema.array(tool.schema.string()).optional(),
      },
      async execute(args, toolCtx) {
        const sessionID = toolCtx?.sessionID || toolCtx?.session_id || toolCtx?.session?.id
        if (!sessionID) {
          return JSON.stringify({
            version: 1,
            operation: "loopx_activate",
            ok: false,
            error: "missing_session",
            message: "No OpenCode session id is available.",
          })
        }
        const result = await executeTool(
          baseGoalSet,
          {
            objective: args.objective,
            successCriteria:
              "LoopX derives terminal no-follow-up from complete todo sources and an empty frontier.",
            constraints:
              "Run every continuation through LoopX quota should-run and do not self-declare terminal closure.",
            ...LOOPX_GOAL_LIMITS,
          },
          toolCtx,
        )
        if (!toolResultSucceeded(result)) return result
        const binding = await bindingStore.write(sessionID, {
          directory: context.directory,
          goalId: String(args.goalId),
          agentId: args.agentId ? String(args.agentId) : "",
          registryPath: args.registryPath ? String(args.registryPath) : "",
          availableCapabilities: Array.isArray(args.availableCapabilities)
            ? args.availableCapabilities.map(String)
            : [],
          autoResume: true,
          schedulerToken: "",
          unchangedPolls: 0,
        })
        initializedSessions.add(sessionID)
        cancelScheduled(sessionID)
        return JSON.stringify({
          version: 1,
          operation: "loopx_activate",
          ok: true,
          message: "LoopX-backed OpenCode goal activated.",
          data: { goalId: binding.goalId, sessionID },
        })
      },
    })

    const tools = { ...baseTools, loopx_goal_activate: activateTool }

    const wrapTool = (name, after) => {
      const original = tools[name]
      if (!original || typeof original.execute !== "function") return
      tools[name] = {
        ...original,
        execute: async (args, toolCtx) => {
          const result = await original.execute(args, toolCtx)
          const sessionID = toolCtx?.sessionID || toolCtx?.session_id || toolCtx?.session?.id
          if (sessionID) await after(sessionID, args || {}, result)
          return result
        },
      }
    }

    for (const name of ["goal_set", "set_goal"]) {
      wrapTool(name, async (sessionID, _args, result) => {
        if (toolResultSucceeded(result)) await bindingStore.remove(sessionID)
      })
    }
    for (const name of ["goal_complete", "clear_goal"]) {
      wrapTool(name, async (sessionID, _args, result) => {
        if (toolResultSucceeded(result)) {
          await bindingStore.remove(sessionID)
          cancelScheduled(sessionID)
        }
      })
    }
    wrapTool("goal_resume", async (sessionID, _args, result) => {
      if (toolResultSucceeded(result)) {
        await updateBinding(sessionID, { autoResume: true })
        initializedSessions.add(sessionID)
      }
    })
    for (const name of ["goal_pause", "goal_block"]) {
      wrapTool(name, async (sessionID, _args, result) => {
        if (toolResultSucceeded(result)) {
          await updateBinding(sessionID, { autoResume: false })
          cancelScheduled(sessionID)
        }
      })
    }

    return {
      ...base,
      tool: tools,
      config: async (config) => {
        if (config && typeof config === "object") {
          config.command ||= {}
          config.command.goal ||= {
            description: "Set a session-scoped goal and auto-continue until complete.",
            template: "$ARGUMENTS",
            agent: "build",
          }
        }
        await base.config?.(config)
      },
      "command.execute.before": async (input, output) => {
        await baseCommand?.(input, output)
        if (input?.command !== "goal" || !input?.sessionID) return
        const sessionID = input.sessionID
        const args = String(input.arguments || "").trim()
        pendingGoalCommands.set(sessionID, { args, recordedAt: Date.now() })
        const kind = commandKind(args)
        if (kind === "clear" || kind === "replace") {
          await bindingStore.remove(sessionID)
          cancelScheduled(sessionID)
        } else if (kind === "resume") {
          await updateBinding(sessionID, { autoResume: true })
          initializedSessions.add(sessionID)
        } else if (kind === "pause") {
          await updateBinding(sessionID, { autoResume: false })
          cancelScheduled(sessionID)
        }
      },
      "chat.message": async (input, output) => {
        const sessionID = input?.sessionID
        if (!sessionID) {
          await baseChatMessage?.(input, output)
          return
        }
        const pending = pendingGoalCommands.get(sessionID)
        if (pending) {
          pendingGoalCommands.delete(sessionID)
          const reflected = textFromParts(output?.parts)
          if (Date.now() - pending.recordedAt < 10_000 && reflected === pending.args) {
            return
          }
        }
        const text = textFromParts(output?.parts)
        if (text === "/goal" || text.startsWith("/goal ")) {
          await baseChatMessage?.(input, output)
          return
        }
        const binding = await readBinding(sessionID)
        if (binding) {
          await bindingStore.write(sessionID, { ...binding, autoResume: false })
          cancelScheduled(sessionID)
        }
        await baseChatMessage?.(input, output)
      },
      event: async (input) => {
        const event = input?.event
        const sessionID = sessionIDFromEvent(event)
        if (!isIdleEvent(event)) {
          if (sessionID && event?.type === "session.deleted") {
            await bindingStore.remove(sessionID)
            cancelScheduled(sessionID)
          } else if (sessionID && shouldPauseForHostEvent(event)) {
            await updateBinding(sessionID, { autoResume: false })
            cancelScheduled(sessionID)
          }
          await baseEvent?.(input)
          return
        }
        if (sessionID) await evaluateIdle(sessionID, input)
      },
      dispose: async () => {
        disposed = true
        for (const timer of timers.values()) clearTimer(timer)
        timers.clear()
        evaluations.clear()
        await base.dispose?.()
      },
    }
  }
}
