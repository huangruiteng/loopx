import type { JsonObject } from "../effect_program.ts";
import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import { requireJsonObject } from "../runtime_decode.ts";
import { DELIVERY_OUTCOMES, isTurnScopedSettlementOutcome, type DeliveryOutcome } from "./delivery_outcome.ts";

const TURN_KINDS = [
  "contract_only_preparation", "compact_evidence", "blocker_writeback",
  "product_path_execution", "outcome_gap", "unknown",
] as const;
type TurnKind = typeof TURN_KINDS[number];
type BatchScale = "test_only" | "single_surface" | "multi_surface" | "implementation" | "unknown";
type OutcomeSignal = DeliveryOutcome | "unknown" | "not_configured";

interface DeliveryRun {
  delivery_outcome: string;
  delivery_batch_scale: string;
  delivery_turn_kind: string;
  todo_id: string;
  replan_obligation_id: string;
  outcome_followthrough_required: boolean;
  progress_observation: JsonObject | null;
}

interface DeliverySignal extends JsonObject {
  delivery_outcome: OutcomeSignal;
  delivery_batch_scale: BatchScale;
  delivery_turn_kind: TurnKind;
  outcome_followthrough: JsonObject | null;
}

function decodeRun(value: unknown): DeliveryRun {
  const raw = requireJsonObject(value, "delivery run");
  const text = (key: string): string => {
    if (typeof raw[key] !== "string") throw new EffectRuntimeRequestError(`delivery run.${key} must be a string`);
    return raw[key] as string;
  };
  if (typeof raw.outcome_followthrough_required !== "boolean") {
    throw new EffectRuntimeRequestError("delivery run.outcome_followthrough_required must be a boolean");
  }
  return {
    delivery_outcome: text("delivery_outcome"),
    delivery_batch_scale: text("delivery_batch_scale"),
    delivery_turn_kind: text("delivery_turn_kind"),
    todo_id: text("todo_id"),
    replan_obligation_id: text("replan_obligation_id"),
    outcome_followthrough_required: raw.outcome_followthrough_required,
    progress_observation: raw.progress_observation === null ? null : requireJsonObject(raw.progress_observation, "progress_observation"),
  };
}

function batchScale(raw: string): BatchScale {
  switch (raw.trim()) {
    case "single_segment": case "bounded_segment": case "single_surface": return "single_surface";
    case "test_only": return "test_only";
    case "multi_surface": return "multi_surface";
    case "implementation": return "implementation";
    default: return "unknown";
  }
}

function outcomeSignal(raw: string, floorConfigured: boolean): OutcomeSignal {
  const value = raw.trim();
  const explicit = DELIVERY_OUTCOMES.find((candidate) => candidate === value);
  return explicit ?? (value || floorConfigured ? "unknown" : "not_configured");
}

function turnKind(run: DeliveryRun, outcome: OutcomeSignal): TurnKind {
  const explicit = run.delivery_turn_kind.trim();
  // An unsupported explicit kind stays unknown; narrative is never a fallback.
  if (explicit) return TURN_KINDS.find((kind) => kind === explicit) ?? "unknown";
  const binding = Boolean(run.todo_id) !== Boolean(run.replan_obligation_id)
    ? (run.todo_id || run.replan_obligation_id).trim() : null;
  if (outcome === "outcome_gap" && isTurnScopedSettlementOutcome(outcome, run.progress_observation, binding)) {
    return "blocker_writeback";
  }
  switch (outcome) {
    case "primary_goal_outcome": return "product_path_execution";
    case "outcome_progress": return "compact_evidence";
    case "surface_only": return "contract_only_preparation";
    case "outcome_gap": return "outcome_gap";
    default: return "unknown";
  }
}

function needsFollowthrough(outcome: OutcomeSignal): boolean {
  return outcome === "surface_only" || outcome === "outcome_gap";
}

function followthrough(run: DeliveryRun, outcome: OutcomeSignal, kind: TurnKind): JsonObject | null {
  if (outcome === "primary_goal_outcome") return null;
  if (!run.outcome_followthrough_required && (
    kind === "blocker_writeback" || (!needsFollowthrough(outcome) && kind !== "contract_only_preparation")
  )) return null;
  return {
    source: "post_handoff_latest_run",
    required: true,
    latest_delivery_outcome: outcome === "unknown" || outcome === "not_configured" ? null : outcome,
    latest_delivery_turn_kind: kind,
    obligation: "advance_primary_outcome_or_write_blocker",
    accepted_resolution_kinds: ["product_path_execution", "compact_evidence", "blocker_writeback"],
    spend_policy: "do not spend for another contract/preparation-only slice; spend only after validated goal-outcome evidence or a precise blocker writeback",
  };
}

function prefixLength<T>(items: readonly T[], matches: (item: T) => boolean): number {
  const boundary = items.findIndex((item) => !matches(item));
  return boundary < 0 ? items.length : boundary;
}

/** One pure batch projection. History selection/order remains the caller's job;
 * this read model grants neither progress nor a durable settlement receipt. */
export function projectDeliveryHistory(value: unknown): JsonObject {
  const input = requireJsonObject(value, "delivery history");
  if (input.schema_version !== "delivery_history_request_v0" || !Array.isArray(input.runs)
    || typeof input.outcome_floor_configured !== "boolean") {
    throw new EffectRuntimeRequestError("invalid delivery_history_request_v0");
  }
  const floorConfigured = input.outcome_floor_configured;
  const runs: DeliverySignal[] = input.runs.map(decodeRun).map((run) => {
    const outcome = outcomeSignal(run.delivery_outcome, floorConfigured);
    const kind = turnKind(run, outcome);
    return {
      delivery_outcome: outcome,
      delivery_batch_scale: batchScale(run.delivery_batch_scale),
      delivery_turn_kind: kind,
      outcome_followthrough: followthrough(run, outcome, kind),
    };
  });
  return {
    schema_version: "delivery_history_v0",
    runs,
    small_scale_streak: prefixLength(runs, (run) => ["test_only", "single_surface"].includes(run.delivery_batch_scale)),
    outcome_gap_streak: floorConfigured ? prefixLength(runs, (run) => needsFollowthrough(run.delivery_outcome)) : 0,
  };
}
