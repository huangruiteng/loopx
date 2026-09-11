import assert from "node:assert/strict";
import test from "node:test";

import { effectRuntimeErrorPayload } from "../../loopx/control_plane/effect_runtime_errors.ts";
import { settlementIdentity } from "../../loopx/control_plane/effect_program.ts";
import {
  reduceTurnSettlementTransaction,
  TURN_SETTLEMENT_TRANSACTION_SCHEMA_VERSION,
} from "../../loopx/control_plane/turn_driver/settlement.ts";

const phases = [
  "host_execute",
  "typed_result",
  "validation",
  "durable_writeback",
  "quota_spend",
  "scheduler_apply",
  "scheduler_ack",
] as const;

const identity = settlementIdentity({
  goal_id: "goal",
  agent_id: "agent",
  todo_id: "todo",
  turn_instance_id: "turn",
});

function request(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    schema_version: TURN_SETTLEMENT_TRANSACTION_SCHEMA_VERSION,
    transaction_plan: { settlement_plan: { identity } },
    transaction_phases: [...phases],
    completed_phases: [...phases.slice(0, 5)],
    committed_effect_id: identity.effect_id,
    writeback_payload: { ok: true, appended: true, record: "writeback" },
    quota_spend_payload: { ok: true, appended: true, record: "spend" },
    terminal_closeout_required: false,
    terminal_closeout_payload: null,
    failed_provider_attempt: null,
    effect_attempts: {},
    provider_observations: {},
    ...overrides,
  };
}

test("complete Turn settlement constructs one ordered receipt chain", () => {
  const reduced = reduceTurnSettlementTransaction(request());

  assert.equal(reduced.result.failure, null);
  assert.deepEqual(
    reduced.result.receipts.map((receipt) => receipt.step_kind),
    ["validation", "durable_writeback", "quota_spend"],
  );
  assert.deepEqual(reduced.result.value, {
    completed_phases: [...phases.slice(0, 5)],
    writeback: { ok: true, appended: true, record: "writeback" },
    quota_spend: { ok: true, appended: true, record: "spend" },
  });
  assert.deepEqual(reduced.settlement_result, {
    ok: true,
    receipts: reduced.result.receipts.map((receipt) => ({
      schema_version: "quota_settlement_receipt_v1",
      ...receipt,
    })),
    failure: null,
  });
});

test("Turn settlement rejects an unknown result_kind at the typed boundary", () => {
  assert.throws(
    () => reduceTurnSettlementTransaction(request({ turn_result_kind: "done" })),
    /turn_result_kind is unsupported/,
  );
});

test("iteration failure cannot enter durable settlement", () => {
  assert.throws(
    () => reduceTurnSettlementTransaction(
      request({ turn_result_kind: "iteration_failed" }),
    ),
    /cannot run for iteration stop result_kind iteration_failed/,
  );
});

test("non-terminal completion requires a durable continuing Todo outcome", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({ turn_result_kind: "validated_completion" }),
  );

  assert.equal(reduced.result.failure?.kind, "receipt_missing");
  assert.equal(reduced.result.failure?.step_kind, "durable_writeback");
});

test("non-terminal completion accepts a durable continuing Todo outcome", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      turn_result_kind: "validated_completion",
      writeback_payload: {
        ok: true,
        appended: true,
        completion: { todo_id: "todo", continuation: "active_goal" },
      },
    }),
  );

  assert.equal(reduced.result.failure, null);
  assert.deepEqual(
    (reduced.settlement_result as Record<string, unknown>).turn_outcome,
    {
      schema_version: "loopx_turn_settlement_outcome_v0",
      result_kind: "validated_completion",
      completed_phases: [...phases.slice(0, 5)],
      failed_phase: null,
      completion: { todo_id: "todo", continuation: "active_goal" },
    },
  );
});

test("successful successor completion is included in the canonical outcome", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      turn_result_kind: "validated_completion",
      writeback_payload: {
        ok: true,
        appended: true,
        completion: {
          todo_id: "todo",
          continuation: "successor",
          successor_todo_ids: ["next"],
        },
      },
    }),
  );

  assert.equal(reduced.result.failure, null);
  assert.deepEqual(
    (reduced.settlement_result as Record<string, unknown>).turn_outcome?.completion,
    {
      todo_id: "todo",
      continuation: "successor",
      successor_todo_ids: ["next"],
    },
  );
});

test("successor completion requires durable successor Todo ids", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      turn_result_kind: "validated_completion",
      writeback_payload: {
        ok: true,
        appended: true,
        completion: { todo_id: "todo", continuation: "successor" },
      },
    }),
  );

  assert.equal(reduced.result.failure?.kind, "receipt_missing");
  assert.match(
    reduced.result.failure?.reason ?? "",
    /successor completion requires successor Todo ids/,
  );
});

test("terminal closeout requires a validated completion result", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      turn_result_kind: "validated_progress",
      terminal_closeout_required: true,
    }),
  );

  assert.equal(reduced.decision, "failed");
  assert.equal(reduced.result.failure?.kind, "terminal_closeout_rejected");
  assert.equal(reduced.result.failure?.step_kind, "terminal_closeout");
  assert.match(
    reduced.result.failure?.reason ?? "",
    /terminal closeout requires a validated completion result/,
  );
});

test("preflight authorizes ordered providers without settling early", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      completed_phases: [...phases.slice(0, 3)],
      writeback_payload: null,
      quota_spend_payload: null,
    }),
  );

  assert.equal(reduced.decision, "execute");
  assert.deepEqual(reduced.provider_effects, [
    {
      step_kind: "durable_writeback",
      action: "prepare_and_execute",
      effect_ref: `${identity.effect_id}#durable_writeback`,
      completed_phases: [...phases.slice(0, 4)],
    },
  ]);
  assert.equal(reduced.result, null);
  assert.equal(reduced.settlement_result, null);
});

test("mismatched replay fails before accepting committed provider outcomes", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({ committed_effect_id: "another-effect" }),
  );

  assert.equal(reduced.result.value, null);
  assert.equal(reduced.result.failure?.kind, "identity_mismatch");
  assert.deepEqual(reduced.result.receipts, []);
});

test("writeback rejection retains validation receipt and typed failure", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      turn_result_kind: "validated_progress",
      completed_phases: [...phases.slice(0, 3)],
      writeback_payload: null,
      quota_spend_payload: null,
      failed_provider_attempt: {
        step_kind: "durable_writeback",
        payload: {
          ok: false,
          appended: false,
          reason: "writeback denied",
        },
      },
    }),
  );

  assert.equal(reduced.result.failure?.kind, "writeback_rejected");
  assert.deepEqual(
    reduced.result.receipts.map((receipt) => receipt.step_kind),
    ["validation"],
  );
  assert.deepEqual(
    (reduced.settlement_result as Record<string, unknown>).turn_outcome,
    {
      schema_version: "loopx_turn_settlement_outcome_v0",
      result_kind: "writeback_failed",
      completed_phases: [...phases.slice(0, 3)],
      failed_phase: "durable_writeback",
    },
  );
});

test("internal settlement contradictions remain internal failures", () => {
  let caught: unknown;
  try {
    reduceTurnSettlementTransaction(
      request({
        completed_phases: [...phases.slice(0, 3)],
        writeback_payload: null,
        quota_spend_payload: null,
        failed_provider_attempt: {
          step_kind: "durable_writeback",
          payload: { ok: true, appended: true, record: "writeback" },
        },
      }),
    );
  } catch (error) {
    caught = error;
  }

  assert.deepEqual(effectRuntimeErrorPayload(caught), {
    kind: "internal_failure",
    code: "unexpected_handler_error",
    message: "Effect runtime handler failed unexpectedly",
  });
});

test("terminal closeout joins the same transaction after spend", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      turn_result_kind: "validated_completion",
      terminal_closeout_required: true,
      terminal_closeout_payload: {
        ok: true,
        appended: true,
        completion: { todo_id: "todo", continuation: "no_followup" },
      },
    }),
  );

  assert.equal(reduced.result.failure, null);
  assert.deepEqual(
    reduced.result.receipts.map((receipt) => receipt.step_kind),
    [
      "validation",
      "durable_writeback",
      "quota_spend",
      "terminal_closeout",
    ],
  );
  assert.deepEqual(
    (reduced.settlement_result as Record<string, unknown>).turn_outcome,
    {
      schema_version: "loopx_turn_settlement_outcome_v0",
      result_kind: "validated_completion",
      completed_phases: [...phases.slice(0, 5)],
      failed_phase: null,
      completion: { todo_id: "todo", continuation: "no_followup" },
    },
  );
});

test("non-prefix journals fail closed instead of inventing provider work", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      completed_phases: ["host_execute", "validation"],
      writeback_payload: null,
      quota_spend_payload: null,
    }),
  );

  assert.equal(reduced.result.failure?.kind, "receipt_missing");
  assert.match(
    reduced.result.failure?.reason ?? "",
    /ordered transaction prefix/,
  );
});

test("prepared provider attempts authorize one identity-bound readback", () => {
  const effectRef = `${identity.effect_id}#durable_writeback`;
  const reduced = reduceTurnSettlementTransaction(
    request({
      completed_phases: [...phases.slice(0, 3)],
      writeback_payload: null,
      quota_spend_payload: null,
      effect_attempts: {
        durable_writeback: { status: "prepared", effect_ref: effectRef },
      },
    }),
  );

  assert.equal(reduced.decision, "execute");
  assert.deepEqual(reduced.provider_effects, [
    {
      step_kind: "durable_writeback",
      action: "resolve_prepared",
      effect_ref: effectRef,
      completed_phases: [...phases.slice(0, 4)],
      resolution_policy: {
        committed: "checkpoint",
        absent: "execute",
        unknown: "fail_closed",
      },
    },
  ]);
});

test("prepared provider attempts reject identity drift before readback", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      completed_phases: [...phases.slice(0, 3)],
      writeback_payload: null,
      quota_spend_payload: null,
      effect_attempts: {
        durable_writeback: {
          status: "prepared",
          effect_ref: "another-effect#durable_writeback",
        },
      },
    }),
  );

  assert.equal(reduced.decision, "failed");
  assert.equal(reduced.result.failure?.kind, "identity_mismatch");
  assert.equal(reduced.result.failure?.step_kind, "durable_writeback");
  assert.deepEqual(reduced.provider_effects, []);
});

test("unknown prepared provider outcomes fail closed", () => {
  const effectRef = `${identity.effect_id}#durable_writeback`;
  const reduced = reduceTurnSettlementTransaction(
    request({
      completed_phases: [...phases.slice(0, 3)],
      writeback_payload: null,
      quota_spend_payload: null,
      effect_attempts: {
        durable_writeback: { status: "prepared", effect_ref: effectRef },
      },
      provider_observations: {
        durable_writeback: {
          kind: "unknown",
          payload: null,
          reason: "provider readback timed out",
        },
      },
    }),
  );

  assert.equal(reduced.decision, "failed");
  assert.equal(reduced.result.failure?.kind, "effect_outcome_unknown");
  assert.equal(reduced.result.failure?.step_kind, "durable_writeback");
  assert.match(reduced.result.failure?.reason ?? "", /readback timed out/);
  assert.deepEqual(reduced.provider_effects, []);
});

test("committed readback without a durable payload fails closed", () => {
  const effectRef = `${identity.effect_id}#durable_writeback`;
  const reduced = reduceTurnSettlementTransaction(
    request({
      completed_phases: [...phases.slice(0, 3)],
      writeback_payload: null,
      quota_spend_payload: null,
      effect_attempts: {
        durable_writeback: { status: "prepared", effect_ref: effectRef },
      },
      provider_observations: {
        durable_writeback: {
          kind: "committed",
          payload: { ok: true, appended: false },
          reason: null,
        },
      },
    }),
  );

  assert.equal(reduced.decision, "failed");
  assert.equal(reduced.result.failure?.kind, "receipt_missing");
  assert.equal(reduced.result.failure?.step_kind, "durable_writeback");
  assert.deepEqual(reduced.provider_effects, []);
});

test("prepared attempts cannot skip an earlier provider step", () => {
  const reduced = reduceTurnSettlementTransaction(
    request({
      completed_phases: [...phases.slice(0, 3)],
      writeback_payload: null,
      quota_spend_payload: null,
      effect_attempts: {
        quota_spend: {
          status: "prepared",
          effect_ref: `${identity.effect_id}#quota_spend`,
        },
      },
    }),
  );

  assert.equal(reduced.decision, "failed");
  assert.equal(reduced.result.failure?.kind, "receipt_missing");
  assert.equal(reduced.result.failure?.step_kind, "quota_spend");
  assert.deepEqual(reduced.provider_effects, []);
});
