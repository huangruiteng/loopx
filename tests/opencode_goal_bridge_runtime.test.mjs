import assert from "node:assert/strict"
import test from "node:test"

import { createLoopxGoalPlugin } from "../loopx/opencode_goal_mode/goal-bridge-runtime.mjs"


function fakeTool(spec) {
  return spec
}
const optional = () => ({ optional })
fakeTool.schema = {
  string: optional,
  number: optional,
  array: () => ({ optional }),
  object: () => ({}),
  enum: () => ({}),
}


function memoryBindingStore() {
  const bindings = new Map()
  return {
    bindings,
    async read(sessionID) {
      return bindings.get(sessionID) || null
    },
    async write(sessionID, binding) {
      const value = { schemaVersion: "loopx_opencode_goal_bridge_v0", sessionID, ...binding }
      bindings.set(sessionID, value)
      return value
    },
    async remove(sessionID) {
      bindings.delete(sessionID)
    },
  }
}


function terminalDecision() {
  return {
    should_run: false,
    effective_action: "terminal_no_followup",
    reason: "validated closure",
    goal_frontier_projection: {
      terminal_state: {
        schema_version: "goal_terminal_state_v0",
        kind: "no_followup",
        derived: true,
        source: "validated_goal_closure",
      },
      source_completeness: {
        schema_version: "goal_terminal_source_completeness_v0",
        user_todos: "valid",
        agent_todos: "valid",
      },
    },
  }
}


function harness(initialDecision) {
  const store = memoryBindingStore()
  const calls = { chat: 0, event: 0, complete: 0, dispose: 0, quota: 0, resume: 0 }
  const scheduled = []
  let decision = initialDecision
  const GoalPlugin = async (_context, options) => ({
    config: async () => {},
    "command.execute.before": async () => {},
    "chat.message": async () => {
      calls.chat += 1
    },
    event: async () => {
      calls.event += 1
    },
    tool: {
      goal_set: fakeTool({
        args: {},
        execute: async () => JSON.stringify({ version: 1, operation: "set", ok: true }),
      }),
      goal_resume: fakeTool({
        args: {},
        execute: async () => {
          calls.resume += 1
          return JSON.stringify({ version: 1, operation: "resume", ok: true })
        },
      }),
      goal_complete: fakeTool({
        args: {},
        execute: async (_args, context) => {
          calls.complete += 1
          const verdict = await options.auditor({ sessionID: context.sessionID })
          return JSON.stringify({
            version: 1,
            operation: "complete",
            ok: verdict.approved,
            ...(verdict.approved ? {} : { error: "completion_rejected" }),
          })
        },
      }),
    },
    dispose: async () => {
      calls.dispose += 1
    },
  })
  const plugin = createLoopxGoalPlugin({
    GoalPlugin,
    tool: fakeTool,
    bindingStore: store,
    quotaProbe: async () => {
      calls.quota += 1
      if (decision instanceof Error) throw decision
      return decision
    },
    setTimer: (callback, delay) => {
      const timer = { callback, cleared: false, delay, unref() {} }
      scheduled.push(timer)
      return timer
    },
    clearTimer: (timer) => {
      timer.cleared = true
    },
  })
  return {
    calls,
    plugin,
    scheduled,
    store,
    setDecision(value) {
      decision = value
    },
  }
}


test("suppresses the OpenCode 1.18 command reflection that pauses a new goal", async () => {
  const fixture = harness({ should_run: true, scheduler_hint: { action: "run_now" } })
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  await hooks["command.execute.before"](
    { command: "goal", sessionID: "session-command", arguments: "ship the task" },
    { parts: [] },
  )
  await hooks["chat.message"](
    { sessionID: "session-command" },
    { parts: [{ type: "text", text: "ship the task" }] },
  )
  assert.equal(fixture.calls.chat, 0)
})


test("gates active and quiet idle turns through LoopX quota", async () => {
  const fixture = harness({ should_run: true, scheduler_hint: { action: "run_now" } })
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  await hooks.tool.loopx_goal_activate.execute(
    { goalId: "goal-1", objective: "LoopX task body" },
    { sessionID: "session-idle" },
  )
  await hooks.event({ event: { type: "session.idle", properties: { sessionID: "session-idle" } } })
  assert.equal(fixture.calls.event, 1)

  fixture.setDecision({
    should_run: false,
    scheduler_hint: {
      action: "backoff_waiting_for_user",
      reset_policy: { reset_token: "wait-1" },
      unchanged_poll: {
        local_scheduler: {
          recommended_interval_minutes: 3,
          example_progression_minutes: [3, 6, 12],
          unchanged_poll_limit: 3,
        },
      },
    },
  })
  await hooks.event({ event: { type: "session.idle", properties: { sessionID: "session-idle" } } })
  assert.equal(fixture.calls.event, 1)
  assert.equal(fixture.scheduled.at(-1).delay, 180_000)
})


test("fails closed and schedules a bounded retry after a quota network timeout", async () => {
  const fixture = harness(new Error("network timeout"))
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  await hooks.tool.loopx_goal_activate.execute(
    { goalId: "goal-timeout", objective: "LoopX task body" },
    { sessionID: "session-timeout" },
  )

  await hooks.event({
    event: { type: "session.idle", properties: { sessionID: "session-timeout" } },
  })

  assert.equal(fixture.calls.quota, 1)
  assert.equal(fixture.calls.event, 0)
  assert.equal(fixture.scheduled.length, 1)
  assert.equal(fixture.scheduled[0].delay, 180_000)
  assert.equal(fixture.scheduled[0].cleared, false)
})


test("fails closed when the session binding cannot be read", async () => {
  const fixture = harness({ should_run: true, scheduler_hint: { action: "run_now" } })
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  await hooks.tool.loopx_goal_activate.execute(
    { goalId: "goal-binding-error", objective: "LoopX task body" },
    { sessionID: "session-binding-error" },
  )
  fixture.store.read = async () => {
    const error = new Error("binding filesystem unavailable")
    error.code = "EACCES"
    throw error
  }

  await hooks.event({
    event: { type: "session.idle", properties: { sessionID: "session-binding-error" } },
  })

  assert.equal(fixture.calls.quota, 0)
  assert.equal(fixture.calls.event, 0)
  assert.equal(fixture.scheduled.length, 0)
  assert.equal(fixture.store.bindings.has("session-binding-error"), true)
})


test("keeps scheduled quota timers isolated between sessions", async () => {
  const fixture = harness({
    should_run: false,
    scheduler_hint: {
      action: "backoff_waiting_for_user",
      reset_policy: { reset_token: "wait-multi" },
      unchanged_poll: {
        local_scheduler: {
          recommended_interval_minutes: 3,
          unchanged_poll_limit: 3,
        },
      },
    },
  })
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  for (const sessionID of ["session-a", "session-b"]) {
    await hooks.tool.loopx_goal_activate.execute(
      { goalId: `goal-${sessionID}`, objective: "LoopX task body" },
      { sessionID },
    )
    await hooks.event({ event: { type: "session.idle", properties: { sessionID } } })
  }

  assert.equal(fixture.scheduled.length, 2)
  assert.equal(fixture.scheduled[0].cleared, false)
  assert.equal(fixture.scheduled[1].cleared, false)

  fixture.setDecision({ should_run: true, scheduler_hint: { action: "run_now" } })
  await hooks.event({
    event: { type: "session.idle", properties: { sessionID: "session-a" } },
  })

  assert.equal(fixture.scheduled[0].cleared, true)
  assert.equal(fixture.scheduled[1].cleared, false)
  assert.equal(fixture.calls.event, 1)
})


test("disposal clears every active session timer before disposing the base plugin", async () => {
  const fixture = harness({
    should_run: false,
    scheduler_hint: {
      action: "backoff_waiting_for_user",
      reset_policy: { reset_token: "wait-dispose" },
      unchanged_poll: {
        local_scheduler: {
          recommended_interval_minutes: 3,
          unchanged_poll_limit: 3,
        },
      },
    },
  })
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  for (const sessionID of ["session-dispose-a", "session-dispose-b"]) {
    await hooks.tool.loopx_goal_activate.execute(
      { goalId: `goal-${sessionID}`, objective: "LoopX task body" },
      { sessionID },
    )
    await hooks.event({ event: { type: "session.idle", properties: { sessionID } } })
  }

  await hooks.dispose()

  assert.equal(fixture.scheduled.length, 2)
  assert.equal(fixture.scheduled.every((timer) => timer.cleared), true)
  assert.equal(fixture.calls.dispose, 1)
})


test("disposal prevents an in-flight quota decision from continuing the session", async () => {
  let releaseDecision
  const pendingDecision = new Promise((resolve) => {
    releaseDecision = resolve
  })
  const fixture = harness(pendingDecision)
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  await hooks.tool.loopx_goal_activate.execute(
    { goalId: "goal-dispose-in-flight", objective: "LoopX task body" },
    { sessionID: "session-dispose-in-flight" },
  )
  const idle = hooks.event({
    event: { type: "session.idle", properties: { sessionID: "session-dispose-in-flight" } },
  })
  for (let index = 0; index < 5 && fixture.calls.quota === 0; index += 1) {
    await Promise.resolve()
  }
  assert.equal(fixture.calls.quota, 1)

  await hooks.dispose()
  releaseDecision({ should_run: true, scheduler_hint: { action: "run_now" } })
  await idle

  assert.equal(fixture.calls.event, 0)
  assert.equal(fixture.scheduled.length, 0)
  assert.equal(fixture.calls.dispose, 1)
})


test("coalesces concurrent idle events into one quota decision", async () => {
  let releaseDecision
  const pendingDecision = new Promise((resolve) => {
    releaseDecision = resolve
  })
  const fixture = harness(pendingDecision)
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  await hooks.tool.loopx_goal_activate.execute(
    { goalId: "goal-concurrent", objective: "LoopX task body" },
    { sessionID: "session-concurrent" },
  )
  const first = hooks.event({
    event: { type: "session.idle", properties: { sessionID: "session-concurrent" } },
  })
  const second = hooks.event({
    event: {
      type: "session.status",
      properties: { sessionID: "session-concurrent", status: { type: "idle" } },
    },
  })
  releaseDecision({ should_run: true, scheduler_hint: { action: "run_now" } })
  await Promise.all([first, second])
  assert.equal(fixture.calls.quota, 1)
  assert.equal(fixture.calls.event, 1)
})


test("does not continue when the user intervenes during a quota probe", async () => {
  let releaseDecision
  const pendingDecision = new Promise((resolve) => {
    releaseDecision = resolve
  })
  const fixture = harness(pendingDecision)
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  await hooks.tool.loopx_goal_activate.execute(
    { goalId: "goal-intervention", objective: "LoopX task body" },
    { sessionID: "session-intervention" },
  )
  const idle = hooks.event({
    event: { type: "session.idle", properties: { sessionID: "session-intervention" } },
  })
  await hooks["chat.message"](
    { sessionID: "session-intervention" },
    { parts: [{ type: "text", text: "change direction" }] },
  )
  releaseDecision({ should_run: true, scheduler_hint: { action: "run_now" } })
  await idle
  assert.equal(fixture.calls.event, 0)
  assert.equal((await fixture.store.read("session-intervention")).autoResume, false)
})


test("completes only after LoopX validates terminal no-follow-up", async () => {
  const fixture = harness(terminalDecision())
  const hooks = await fixture.plugin({ directory: "/workspace", client: {} })
  await hooks.tool.loopx_goal_activate.execute(
    { goalId: "goal-terminal", objective: "LoopX task body" },
    { sessionID: "session-terminal" },
  )
  await hooks.event({
    event: { type: "session.idle", properties: { sessionID: "session-terminal" } },
  })
  assert.equal(fixture.calls.complete, 1)
  assert.equal(await fixture.store.read("session-terminal"), null)
  assert.equal(fixture.calls.event, 0)
})
