import { createHash } from "node:crypto";

import type { JsonObject } from "../effect_program.ts";
import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import {
  requireInteger,
  requireJsonObject,
  requireNonEmptyString,
  requireStringArray,
  requireStringLiteral,
} from "../runtime_decode.ts";

/**
 * Governed goal amendment proposal admission contract (RFC
 * shared-goal-alignment-and-governed-amendment-v0, Stage 2 — proposal only).
 *
 * The reducer performs RFC §5 step 2 (admit): strict schema decode, actor
 * identity shape, a closed `amendment_class` enum, bounded evidence pointers,
 * and the relation between `base_goal_revision` and the current derived goal
 * basis. Admission validates and retains a proposal; it never approves,
 * commits, or applies one. The answer always carries `canonical_effect:
 * "none"` — a proposal has no canonical effect by construction (RFC §3.4).
 *
 * Admitted statuses are fact tokens only: `admitted`, or `needs_rebase` when
 * the proposal's base revision is behind the derived head (RFC §7: a stale
 * base is never silently merged). A schema violation fails closed as a
 * request rejection — the equivalent `rejected_schema` outcome never yields a
 * record. There is no `approved` status and no commit path in this contract;
 * governed commit belongs to Stage 3+ behind the `GoalAmendmentAuthority`.
 *
 * The derived goal basis facts arrive from the Python adapter via the Stage 1
 * alignment projection (`state_event_log` head = last append sequence). When
 * no event log exists the basis is `markdown_active_state` and the base
 * revision is reported unverifiable instead of fabricating a stale verdict.
 */

export const GOAL_AMENDMENT_PROPOSAL_REQUEST_SCHEMA_VERSION =
  "goal_amendment_proposal_request_v0";
export const GOAL_AMENDMENT_PROPOSAL_SCHEMA_VERSION =
  "goal_amendment_proposal_v0";
export const GOAL_AMENDMENT_PROPOSAL_ADMISSION_SCHEMA_VERSION =
  "goal_amendment_proposal_admission_v0";

export const GOAL_AMENDMENT_CLASSES = [
  "lane_route",
  "shared_work_graph",
  "shared_acceptance",
  "protected_authority",
] as const;
export type GoalAmendmentClass = (typeof GOAL_AMENDMENT_CLASSES)[number];

export const GOAL_AMENDMENT_PROPOSAL_ADMISSIONS = [
  "admitted",
  "needs_rebase",
] as const;
export type GoalAmendmentAdmission =
  (typeof GOAL_AMENDMENT_PROPOSAL_ADMISSIONS)[number];

export const GOAL_AMENDMENT_PROPOSAL_ADMISSION_FACTS = [
  "base_revision_behind_derived_head",
  "base_revision_unverifiable",
] as const;
export type GoalAmendmentAdmissionFact =
  (typeof GOAL_AMENDMENT_PROPOSAL_ADMISSION_FACTS)[number];

export const REVISION_BASIS_VALUES = [
  "state_event_log",
  "markdown_active_state",
] as const;
export type AmendmentRevisionBasis = (typeof REVISION_BASIS_VALUES)[number];

/** Bounded evidence and intent-statement budgets (RFC §5.2 admission). */
export const MAX_EVIDENCE_REFS = 8;
export const MAX_EVIDENCE_REF_LENGTH = 200;
export const MAX_INTENT_STATEMENTS = 16;
export const MAX_INTENT_STATEMENT_LENGTH = 500;
export const MAX_AFFECTED_TODO_IDS = 16;

const PROPOSAL_ID_PATTERN = /^gap_[a-z0-9_-]{3,64}$/;
const REPLAN_OBLIGATION_ID_PATTERN = /^replan:[a-z0-9_.:@-]{1,80}$/;
const INTENT_DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/;
const AGENT_ID_PATTERN = /^[a-z][a-z0-9_.:@-]{0,79}$/;
const TODO_ID_PATTERN = /^todo_[a-z0-9_-]{3,64}$/;

export interface GoalAmendmentProposal extends JsonObject {
  schema_version: typeof GOAL_AMENDMENT_PROPOSAL_SCHEMA_VERSION;
  proposal_id: string;
  goal_id: string;
  proposer_agent_id: string;
  amendment_class: GoalAmendmentClass;
  base_goal_revision: number;
  base_intent_digest: string;
  retained: string[];
  changed: string[];
  stopped: string[];
  evidence_refs: string[];
  affected_todo_ids: string[];
  replan_obligation_id: string;
}

export interface DerivedGoalBasisFacts extends JsonObject {
  goal_revision: number;
  revision_basis: AmendmentRevisionBasis;
  intent_digest: string;
}

export interface GoalAmendmentProposalRequest extends JsonObject {
  schema_version: typeof GOAL_AMENDMENT_PROPOSAL_REQUEST_SCHEMA_VERSION;
  proposal: GoalAmendmentProposal;
  derived_basis: DerivedGoalBasisFacts;
}

export interface GoalAmendmentProposalAdmission extends JsonObject {
  schema_version: typeof GOAL_AMENDMENT_PROPOSAL_ADMISSION_SCHEMA_VERSION;
  proposal_id: string;
  goal_id: string;
  proposer_agent_id: string;
  amendment_class: GoalAmendmentClass;
  proposal_digest: string;
  base_goal_revision: number;
  base_intent_digest: string;
  retained: string[];
  changed: string[];
  stopped: string[];
  evidence_refs: string[];
  affected_todo_ids: string[];
  replan_obligation_id: string;
  admission: GoalAmendmentAdmission;
  admission_facts: GoalAmendmentAdmissionFact[];
  canonical_effect: "none";
}

function agentId(value: unknown, label: string): string {
  const decoded = requireNonEmptyString(value, label).trim().toLowerCase();
  if (!AGENT_ID_PATTERN.test(decoded)) {
    throw new EffectRuntimeRequestError(
      `${label} must be a public-safe agent id`,
    );
  }
  return decoded;
}

function intentDigest(value: unknown, label: string): string {
  const digest = requireNonEmptyString(value, label);
  if (!INTENT_DIGEST_PATTERN.test(digest)) {
    throw new EffectRuntimeRequestError(
      `${label} must be a sha256:<hex> digest`,
    );
  }
  return digest;
}

function boundedStatementArray(
  value: unknown,
  label: string,
  options: { minimum: number },
): string[] {
  const statements = requireStringArray(value, label).map((item, index) => {
    const statement = item.trim();
    if (!statement) {
      throw new EffectRuntimeRequestError(
        `${label}[${index}] must be a non-empty statement`,
      );
    }
    if (statement.length > MAX_INTENT_STATEMENT_LENGTH) {
      throw new EffectRuntimeRequestError(
        `${label}[${index}] exceeds ${MAX_INTENT_STATEMENT_LENGTH} characters`,
      );
    }
    return statement;
  });
  if (statements.length < options.minimum) {
    throw new EffectRuntimeRequestError(
      `${label} requires at least ${options.minimum} statement(s)`,
    );
  }
  if (statements.length > MAX_INTENT_STATEMENTS) {
    throw new EffectRuntimeRequestError(
      `${label} exceeds ${MAX_INTENT_STATEMENTS} statements`,
    );
  }
  return statements;
}

function decodeEvidenceRefs(value: unknown): string[] {
  const refs = requireStringArray(
    value,
    "goal_amendment_proposal.evidence_refs",
  ).map((item, index) => {
    const pointer = item.trim();
    if (!pointer) {
      throw new EffectRuntimeRequestError(
        `goal_amendment_proposal.evidence_refs[${index}] must be a non-empty pointer`,
      );
    }
    if (pointer.length > MAX_EVIDENCE_REF_LENGTH) {
      throw new EffectRuntimeRequestError(
        `goal_amendment_proposal.evidence_refs[${index}] exceeds ${MAX_EVIDENCE_REF_LENGTH} characters`,
      );
    }
    return pointer;
  });
  if (refs.length < 1) {
    throw new EffectRuntimeRequestError(
      "goal_amendment_proposal.evidence_refs requires at least one pointer",
    );
  }
  if (refs.length > MAX_EVIDENCE_REFS) {
    throw new EffectRuntimeRequestError(
      `goal_amendment_proposal.evidence_refs exceeds ${MAX_EVIDENCE_REFS} pointers`,
    );
  }
  requireNoDuplicateValues(
    refs,
    "goal_amendment_proposal.evidence_refs",
    "pointer",
  );
  return refs;
}

function decodeAffectedTodoIds(value: unknown): string[] {
  if (value === null || value === undefined) {
    throw new EffectRuntimeRequestError(
      "goal_amendment_proposal.affected_todo_ids is required",
    );
  }
  const todoIds = requireStringArray(
    value,
    "goal_amendment_proposal.affected_todo_ids",
  ).map((item, index) => {
    const todoId = item.trim().toLowerCase();
    if (!TODO_ID_PATTERN.test(todoId)) {
      throw new EffectRuntimeRequestError(
        `goal_amendment_proposal.affected_todo_ids[${index}] must be a valid Todo id`,
      );
    }
    return todoId;
  });
  if (todoIds.length > MAX_AFFECTED_TODO_IDS) {
    throw new EffectRuntimeRequestError(
      `goal_amendment_proposal.affected_todo_ids exceeds ${MAX_AFFECTED_TODO_IDS} ids`,
    );
  }
  requireNoDuplicateValues(
    todoIds,
    "goal_amendment_proposal.affected_todo_ids",
    "todo_id",
  );
  return todoIds;
}

function requireNoDuplicateValues(
  values: string[],
  label: string,
  kind: string,
): void {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) {
      throw new EffectRuntimeRequestError(
        `${label} contains a duplicate ${kind}: ${value}`,
      );
    }
    seen.add(value);
  }
}

function decodeProposal(value: unknown): GoalAmendmentProposal {
  const proposal = requireJsonObject(value, "goal_amendment_proposal");
  if (proposal.schema_version !== GOAL_AMENDMENT_PROPOSAL_SCHEMA_VERSION) {
    throw new EffectRuntimeRequestError(
      "goal amendment proposal schema mismatch",
    );
  }
  const proposalId = requireNonEmptyString(
    proposal.proposal_id,
    "goal_amendment_proposal.proposal_id",
  ).trim().toLowerCase();
  if (!PROPOSAL_ID_PATTERN.test(proposalId)) {
    throw new EffectRuntimeRequestError(
      "goal_amendment_proposal.proposal_id must match gap_<slug>",
    );
  }
  const replanObligationId = requireNonEmptyString(
    proposal.replan_obligation_id,
    "goal_amendment_proposal.replan_obligation_id",
  ).trim();
  if (!REPLAN_OBLIGATION_ID_PATTERN.test(replanObligationId)) {
    throw new EffectRuntimeRequestError(
      "goal_amendment_proposal.replan_obligation_id must match replan:<slug>",
    );
  }
  return {
    schema_version: GOAL_AMENDMENT_PROPOSAL_SCHEMA_VERSION,
    proposal_id: proposalId,
    goal_id: requireNonEmptyString(
      proposal.goal_id,
      "goal_amendment_proposal.goal_id",
    ).trim(),
    proposer_agent_id: agentId(
      proposal.proposer_agent_id,
      "goal_amendment_proposal.proposer_agent_id",
    ),
    amendment_class: requireStringLiteral(
      proposal.amendment_class,
      GOAL_AMENDMENT_CLASSES,
      "goal_amendment_proposal.amendment_class",
      "goal amendment class is unsupported",
    ),
    base_goal_revision: positiveInteger(
      proposal.base_goal_revision,
      "goal_amendment_proposal.base_goal_revision",
    ),
    base_intent_digest: intentDigest(
      proposal.base_intent_digest,
      "goal_amendment_proposal.base_intent_digest",
    ),
    retained: boundedStatementArray(proposal.retained, "goal_amendment_proposal.retained", {
      minimum: 1,
    }),
    changed: boundedStatementArray(proposal.changed, "goal_amendment_proposal.changed", {
      minimum: 1,
    }),
    stopped: boundedStatementArray(proposal.stopped, "goal_amendment_proposal.stopped", {
      minimum: 0,
    }),
    evidence_refs: decodeEvidenceRefs(proposal.evidence_refs),
    affected_todo_ids: decodeAffectedTodoIds(proposal.affected_todo_ids),
    replan_obligation_id: replanObligationId,
  };
}

function positiveInteger(value: unknown, label: string): number {
  const decoded = requireInteger(value, label);
  if (decoded < 1) {
    throw new EffectRuntimeRequestError(`${label} must be a positive integer`);
  }
  return decoded;
}

function decodeDerivedBasis(value: unknown): DerivedGoalBasisFacts {
  const raw = requireJsonObject(value, "goal_amendment_proposal.derived_basis");
  const revisionBasis = requireStringLiteral(
    raw.revision_basis,
    REVISION_BASIS_VALUES,
    "goal_amendment_proposal.derived_basis.revision_basis",
    "goal amendment derived revision_basis is unsupported",
  );
  const goalRevision = requireInteger(
    raw.goal_revision,
    "goal_amendment_proposal.derived_basis.goal_revision",
  );
  if (goalRevision < 0) {
    throw new EffectRuntimeRequestError(
      "goal_amendment_proposal.derived_basis.goal_revision must be non-negative",
    );
  }
  if (revisionBasis === "state_event_log" && goalRevision < 1) {
    throw new EffectRuntimeRequestError(
      "goal_amendment_proposal.derived_basis.goal_revision must be a positive event append sequence when revision_basis is state_event_log",
    );
  }
  if (revisionBasis === "markdown_active_state" && goalRevision !== 0) {
    throw new EffectRuntimeRequestError(
      "goal_amendment_proposal.derived_basis.goal_revision must be 0 when revision_basis is markdown_active_state",
    );
  }
  return {
    goal_revision: goalRevision,
    revision_basis: revisionBasis,
    intent_digest: intentDigest(
      raw.intent_digest,
      "goal_amendment_proposal.derived_basis.intent_digest",
    ),
  };
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (typeof value !== "object" || value === null) return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
      .map(([key, child]) => [key, stableValue(child)]),
  );
}

function canonicalDigest(value: unknown): string {
  // Same recipe as the Python adapter's _canonical_digest and
  // governed_capability.ts: sorted keys, compact separators, no ASCII
  // escaping, so the digest is identical across both runtimes.
  const encoded = JSON.stringify(stableValue(value));
  if (encoded === undefined) {
    throw new EffectRuntimeRequestError(
      "goal amendment proposal is not JSON-compatible",
    );
  }
  return `sha256:${createHash("sha256").update(encoded, "utf8").digest("hex")}`;
}

function admissionOutcome(
  proposal: GoalAmendmentProposal,
  derived: DerivedGoalBasisFacts,
): { admission: GoalAmendmentAdmission; facts: GoalAmendmentAdmissionFact[] } {
  if (derived.revision_basis === "markdown_active_state") {
    // No event log to compare against: report unverifiable, never a
    // fabricated stale verdict (same policy as Stage 1).
    return {
      admission: "admitted",
      facts: ["base_revision_unverifiable"],
    };
  }
  if (proposal.base_goal_revision > derived.goal_revision) {
    throw new EffectRuntimeRequestError(
      "goal amendment proposal base_goal_revision is ahead of the derived goal head",
    );
  }
  if (proposal.base_goal_revision < derived.goal_revision) {
    // Stale bases stay admitted as retained facts with a needs_rebase
    // marker; admission never silently drops or merges them (RFC §7).
    return {
      admission: "needs_rebase",
      facts: ["base_revision_behind_derived_head"],
    };
  }
  return { admission: "admitted", facts: [] };
}

export function decodeGoalAmendmentProposalRequest(
  value: unknown,
): GoalAmendmentProposalRequest {
  const request = requireJsonObject(value, "goal amendment proposal request");
  if (
    request.schema_version !== GOAL_AMENDMENT_PROPOSAL_REQUEST_SCHEMA_VERSION
  ) {
    throw new EffectRuntimeRequestError(
      "goal amendment proposal request schema mismatch",
    );
  }
  return {
    schema_version: GOAL_AMENDMENT_PROPOSAL_REQUEST_SCHEMA_VERSION,
    proposal: decodeProposal(request.proposal),
    derived_basis: decodeDerivedBasis(request.derived_basis),
  };
}

/** Validate one proposal and emit its non-authoritative admission record. */
export function admitGoalAmendmentProposal(
  value: unknown,
): GoalAmendmentProposalAdmission {
  const request = decodeGoalAmendmentProposalRequest(value);
  const { proposal } = request;
  const outcome = admissionOutcome(proposal, request.derived_basis);
  return {
    schema_version: GOAL_AMENDMENT_PROPOSAL_ADMISSION_SCHEMA_VERSION,
    proposal_id: proposal.proposal_id,
    goal_id: proposal.goal_id,
    proposer_agent_id: proposal.proposer_agent_id,
    amendment_class: proposal.amendment_class,
    proposal_digest: canonicalDigest(proposal),
    base_goal_revision: proposal.base_goal_revision,
    base_intent_digest: proposal.base_intent_digest,
    retained: proposal.retained,
    changed: proposal.changed,
    stopped: proposal.stopped,
    evidence_refs: proposal.evidence_refs,
    affected_todo_ids: proposal.affected_todo_ids,
    replan_obligation_id: proposal.replan_obligation_id,
    admission: outcome.admission,
    admission_facts: outcome.facts,
    canonical_effect: "none",
  };
}
