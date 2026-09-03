import assert from "node:assert/strict";
import test from "node:test";

import {
  GOAL_AMENDMENT_PROPOSAL_ADMISSION_SCHEMA_VERSION,
  admitGoalAmendmentProposal,
} from "../../loopx/control_plane/goals/goal_amendment_proposal.ts";

// The default proposal binds to the derived basis: equal sequence AND
// equal source basis digest. MISMATCHED_DIGEST exercises the binding.
const DIGEST = "sha256:" + "a".repeat(64);
const MISMATCHED_DIGEST = "sha256:" + "b".repeat(64);

function baseRequest(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "goal_amendment_proposal_request_v0",
    proposal: {
      schema_version: "goal_amendment_proposal_v0",
      proposal_id: "gap_stage2_001",
      goal_id: "goal-stage2",
      proposer_agent_id: "agent-a",
      amendment_class: "shared_acceptance",
      base_state_event_basis_sequence: 17,
      base_source_basis_digest: DIGEST,
      retained: ["original outcome remains unchanged"],
      changed: ["acceptance now requires the recovered receipt"],
      stopped: [],
      evidence_refs: ["evidence:evt_stage2_001"],
      affected_todo_ids: ["todo_stage2_a", "todo_stage2_b"],
      replan_obligation_id: "replan-fe2d75e84da47ac3",
    },
    derived_basis: {
      state_event_basis_sequence: 17,
      revision_basis: "state_event_log",
      source_basis_digest: DIGEST,
    },
    ...overrides,
  };
}

test("admits a well-formed proposal with no canonical effect", () => {
  const result = admitGoalAmendmentProposal(baseRequest());

  assert.equal(
    result.schema_version,
    GOAL_AMENDMENT_PROPOSAL_ADMISSION_SCHEMA_VERSION,
  );
  assert.equal(result.proposal_id, "gap_stage2_001");
  assert.equal(result.goal_id, "goal-stage2");
  assert.equal(result.proposer_agent_id, "agent-a");
  assert.equal(result.amendment_class, "shared_acceptance");
  assert.equal(result.admission, "admitted");
  assert.deepEqual(result.admission_facts, []);
  assert.equal(result.canonical_effect, "none");
  assert.match(result.proposal_digest, /^sha256:[0-9a-f]{64}$/);
  assert.deepEqual(result.retained, ["original outcome remains unchanged"]);
  assert.deepEqual(result.evidence_refs, ["evidence:evt_stage2_001"]);
});

test("a base sequence behind the derived head is retained as needs_rebase", () => {
  const result = admitGoalAmendmentProposal(
    baseRequest({
      proposal: {
        ...baseRequest().proposal,
        base_state_event_basis_sequence: 12,
      },
    }),
  );

  assert.equal(result.admission, "needs_rebase");
  assert.deepEqual(result.admission_facts, [
    "base_state_event_basis_sequence_behind_derived_head",
  ]);
  assert.equal(result.canonical_effect, "none");
});

test("an equal sequence with a mismatched base digest needs rebase", () => {
  // Same sequence, different source basis identity: the proposal is NOT
  // bound to the basis it claims, so it must never be admitted fresh.
  const result = admitGoalAmendmentProposal(
    baseRequest({
      proposal: {
        ...baseRequest().proposal,
        base_source_basis_digest: MISMATCHED_DIGEST,
      },
    }),
  );

  assert.equal(result.admission, "needs_rebase");
  assert.deepEqual(result.admission_facts, [
    "base_source_basis_digest_mismatch",
  ]);
  assert.equal(result.canonical_effect, "none");
});

test("a behind sequence with a mismatched digest reports both facts", () => {
  const result = admitGoalAmendmentProposal(
    baseRequest({
      proposal: {
        ...baseRequest().proposal,
        base_state_event_basis_sequence: 12,
        base_source_basis_digest: MISMATCHED_DIGEST,
      },
    }),
  );

  assert.equal(result.admission, "needs_rebase");
  assert.deepEqual(result.admission_facts, [
    "base_state_event_basis_sequence_behind_derived_head",
    "base_source_basis_digest_mismatch",
  ]);
});

test("a base sequence ahead of the derived head fails closed", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            base_state_event_basis_sequence: 99,
          },
        }),
      ),
    /ahead of the derived state event basis head/,
  );
});

test("a markdown basis admits with an unverifiable base fact", () => {
  const result = admitGoalAmendmentProposal(
    baseRequest({
      derived_basis: {
        state_event_basis_sequence: 0,
        revision_basis: "markdown_active_state",
        source_basis_digest: DIGEST,
      },
    }),
  );

  assert.equal(result.admission, "admitted");
  assert.deepEqual(result.admission_facts, ["base_source_basis_unverifiable"]);
});

test("an unknown amendment class is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            amendment_class: "emergency_powers",
          },
        }),
      ),
    /amendment class is unsupported/,
  );
});

test("every amendment class in the RFC table is admissible", () => {
  for (const amendmentClass of [
    "lane_route",
    "shared_work_graph",
    "shared_acceptance",
    "protected_authority",
  ]) {
    const result = admitGoalAmendmentProposal(
      baseRequest({
        proposal: { ...baseRequest().proposal, amendment_class: amendmentClass },
      }),
    );
    assert.equal(result.amendment_class, amendmentClass);
    assert.equal(result.canonical_effect, "none");
  }
});

test("a base digest that is not sha256 hex is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            base_source_basis_digest: "md5:zz",
          },
        }),
      ),
    /sha256/,
  );
});

test("duplicate affected todo ids are rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            affected_todo_ids: ["todo_stage2_a", "todo_stage2_a"],
          },
        }),
      ),
    /duplicate todo_id/,
  );
});

test("duplicate evidence pointers are rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            evidence_refs: [
              "evidence:evt_stage2_001",
              "evidence:evt_stage2_001",
            ],
          },
        }),
      ),
    /duplicate pointer/,
  );
});

test("evidence pointers over the budget are rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            evidence_refs: Array.from(
              { length: 9 },
              (_, index) => `evidence:evt_stage2_${index}`,
            ),
          },
        }),
      ),
    /exceeds 8 pointers/,
  );
});

test("an over-long evidence pointer is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            evidence_refs: ["evidence:" + "x".repeat(200)],
          },
        }),
      ),
    /exceeds 200 characters/,
  );
});

test("a proposal with no changed statement is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            changed: [],
          },
        }),
      ),
    /goal_amendment_proposal.changed requires at least 1/,
  );
});

test("a proposal with no retained statement is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            retained: [],
          },
        }),
      ),
    /goal_amendment_proposal.retained requires at least 1/,
  );
});

test("a missing replan obligation id is rejected", () => {
  const proposal = baseRequest().proposal as Record<string, unknown>;
  delete proposal.replan_obligation_id;
  assert.throws(
    () => admitGoalAmendmentProposal(baseRequest({ proposal })),
    /replan_obligation_id/,
  );
});

test("a malformed proposal id is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            proposal_id: "proposal-1",
          },
        }),
      ),
    /gap_<slug>/,
  );
});

test("a request schema mismatch is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({ schema_version: "goal_amendment_proposal_request_v1" }),
      ),
    /schema mismatch/,
  );
});

test("a proposal schema mismatch is rejected", () => {
  const request = baseRequest();
  (request.proposal as Record<string, unknown>).schema_version =
    "goal_amendment_proposal_v1";
  assert.throws(
    () => admitGoalAmendmentProposal(request),
    /schema mismatch/,
  );
});

test("the proposal digest is deterministic and content-bound", () => {
  const first = admitGoalAmendmentProposal(baseRequest());

  // Reordered keys inside the proposal must not change the digest: the
  // digest binds proposal content, not serialization order.
  const reordered: Record<string, unknown> = baseRequest();
  reordered.proposal = Object.fromEntries(
    Object.entries(reordered.proposal as Record<string, unknown>).reverse(),
  );
  const second = admitGoalAmendmentProposal(reordered);

  // A changed statement must change the digest.
  const edited: Record<string, unknown> = baseRequest();
  edited.proposal = {
    ...(edited.proposal as Record<string, unknown>),
    changed: ["acceptance now requires two independent receipts"],
  };
  const third = admitGoalAmendmentProposal(edited);

  assert.equal(second.proposal_digest, first.proposal_digest);
  assert.notEqual(third.proposal_digest, first.proposal_digest);
});

test("an empty evidence_refs array is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            evidence_refs: [],
          },
        }),
      ),
    /requires at least one pointer/,
  );
});

test("affected todo ids over the budget are rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            affected_todo_ids: Array.from(
              { length: 17 },
              (_, index) => `todo_stage2_${index}`,
            ),
          },
        }),
      ),
    /exceeds 16 ids/,
  );
});

test("a malformed affected todo id is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            affected_todo_ids: ["todo-stage2-a"],
          },
        }),
      ),
    /must be a valid Todo id/,
  );
});

test("a blank stopped statement is rejected", () => {
  assert.throws(
    () =>
      admitGoalAmendmentProposal(
        baseRequest({
          proposal: {
            ...baseRequest().proposal,
            stopped: ["   "],
          },
        }),
      ),
    /stopped\[0\] must be a non-empty statement/,
  );
});

test("replan obligation ids follow the normalize_todo_replan_obligation_id contract", () => {
  // The repository authority is TODO_REPLAN_OBLIGATION_ID_PATTERN:
  // "replan-" + 16 lowercase hex, e.g. "replan-fe2d75e84da47ac3".
  // A second obligation namespace must not be invented here.
  const result = admitGoalAmendmentProposal(
    baseRequest({
      proposal: {
        ...baseRequest().proposal,
        replan_obligation_id: "replan-0123456789abcdef",
      },
    }),
  );
  assert.equal(result.replan_obligation_id, "replan-0123456789abcdef");
  for (const replanObligationId of [
    "replan:stage2-001",
    "replan-FE2D75E84DA47AC3",
    "replan-fe2d75e84da47ac",
    "replan-fe2d75e84da47ac33",
    "obligation-stage2-001",
  ]) {
    assert.throws(
      () =>
        admitGoalAmendmentProposal(
          baseRequest({
            proposal: {
              ...baseRequest().proposal,
              replan_obligation_id: replanObligationId,
            },
          }),
        ),
      /replan-<16 lowercase hex>/,
    );
  }
});
