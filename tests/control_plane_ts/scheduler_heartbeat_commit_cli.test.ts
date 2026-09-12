import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { schedulerStatePath } from "../../loopx/control_plane/scheduler/state_store.ts";

const entrypoint = fileURLToPath(
  new URL(
    "../../loopx/control_plane/scheduler/heartbeat_commit_cli.ts",
    import.meta.url,
  ),
);
const scope = {
  goal_id: "goal-heartbeat-cli",
  agent_id: "agent-heartbeat-cli",
  surface: "codex_app",
  state_key: "scheduler_hint.app_automation.stateful_backoff",
};

function facts(runtimeRoot: string, extra: Record<string, unknown> = {}) {
  return {
    schema_version: "loopx_scheduler_heartbeat_host_facts_v0",
    operation: "ack",
    runtime_root: runtimeRoot,
    ...scope,
    reset_token: "reset-cli",
    identity_signature: "identity-cli",
    progression_index: 0,
    progression_minutes: [15, 30, 60],
    expected_rrule: "FREQ=MINUTELY;INTERVAL=15",
    applied_rrule: "FREQ=MINUTELY;INTERVAL=15",
    cadence_class: "active_work",
    generated_at: "2026-08-24T08:00:00Z",
    ...extra,
  };
}

function runCli(input: unknown) {
  const child = spawnSync(
    process.execPath,
    ["--no-warnings", "--experimental-strip-types", entrypoint],
    {
      input: typeof input === "string" ? input : JSON.stringify(input),
      encoding: "utf8",
    },
  );
  assert.equal(child.error, undefined, child.error?.message);
  const lines = child.stdout.trim().split(/\r?\n/).filter(Boolean);
  assert.equal(lines.length, 1, child.stdout);
  return {
    status: child.status,
    stderr: child.stderr,
    value: JSON.parse(lines[0]) as Record<string, unknown>,
  };
}

async function tempRuntime(t: test.TestContext): Promise<string> {
  const runtimeRoot = await mkdtemp(join(tmpdir(), "loopx-heartbeat-cli-"));
  t.after(() => rm(runtimeRoot, { recursive: true, force: true }));
  return runtimeRoot;
}

test("native scheduler command writes and replays without a daemon", async (t) => {
  const runtimeRoot = await tempRuntime(t);
  const first = runCli(facts(runtimeRoot));
  assert.equal(first.status, 0);
  assert.equal(first.value.status, "written");
  const replay = runCli(facts(runtimeRoot, {
    generated_at: "2026-08-24T08:01:00Z",
  }));
  assert.equal(replay.status, 0);
  assert.equal(replay.value.status, "replayed");
  assert.equal(replay.value.effect_id, first.value.effect_id);
  assert.equal(replay.value.state_digest, first.value.state_digest);
});

test("preview returns a receipt without creating scheduler state", async (t) => {
  const runtimeRoot = await tempRuntime(t);
  const preview = runCli(facts(runtimeRoot, { execute: false }));
  assert.equal(preview.status, 0);
  assert.equal(preview.value.status, "preview");
  const path = schedulerStatePath(runtimeRoot, {
    goalId: scope.goal_id,
    agentId: scope.agent_id,
    surface: scope.surface,
    stateKey: scope.state_key,
  });
  await assert.rejects(readFile(path, "utf8"), { code: "ENOENT" });
});

test("nested ACK facts retain the explicit stale-hint tolerance", async (t) => {
  const runtimeRoot = await tempRuntime(t);
  const result = runCli(facts(runtimeRoot, {
    stale_tolerance_minutes: undefined,
    ack: { stale_hint_tolerance_minutes: 7 },
  }));
  assert.equal(result.status, 0);
  assert.equal(result.value.status, "written");
  assert.equal(result.value.stale_hint_tolerance_minutes, 7);
});

test("conflicts retain the full CAS/effect receipt and use a nonzero exit", async (t) => {
  const runtimeRoot = await tempRuntime(t);
  const first = runCli(facts(runtimeRoot, { operation_id: "cli-effect-1" }));
  assert.equal(first.status, 0);
  const conflict = runCli(facts(runtimeRoot, {
    operation_id: "cli-effect-1",
    applied_rrule: "FREQ=MINUTELY;INTERVAL=30",
  }));
  assert.notEqual(conflict.status, 0);
  assert.equal(conflict.value.status, "conflict");
  assert.equal(conflict.value.reason_code, "effect_id_conflict");
  assert.equal(typeof conflict.value.state_digest, "string");
  assert.equal(typeof conflict.value.expected_state_digest, "string");
});

test("malformed input returns one typed public error envelope", () => {
  const malformed = runCli("not-json");
  assert.notEqual(malformed.status, 0);
  assert.equal(
    malformed.value.schema_version,
    "loopx_scheduler_heartbeat_commit_error_v0",
  );
  assert.equal(malformed.value.status, "error");
  assert.deepEqual(malformed.value.error, {
    kind: "request_rejected",
    code: "invalid_json",
    message: "scheduler heartbeat host facts input must be valid JSON",
  });
});
