import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import { requireJsonObject } from "../runtime_decode.ts";
import type { JsonObject } from "../effect_program.ts";

export const DELIVERY_OUTCOMES = [
  "surface_only",
  "outcome_gap",
  "outcome_progress",
  "primary_goal_outcome",
] as const;

export const MATERIAL_DELIVERY_OUTCOMES = [
  "outcome_gap",
  "outcome_progress",
  "primary_goal_outcome",
] as const;

export type DeliveryOutcome = (typeof DELIVERY_OUTCOMES)[number];
export type MaterialDeliveryOutcome =
  (typeof MATERIAL_DELIVERY_OUTCOMES)[number];

export type DeliveryClaimConflict =
  | "progress_with_preparation_only"
  | "primary_outcome_with_blocker"
  | "primary_outcome_with_followthrough";

/** Validate combinations, not prose or evidence truth. Historical readers use
 * these same codes without rewriting already committed records or receipts. */
export function diagnoseDeliveryClaim(raw: JsonObject): DeliveryClaimConflict[] {
  const outcome = String(raw.delivery_outcome ?? "").trim();
  const kind = String(raw.delivery_turn_kind ?? "").trim();
  const conflicts: DeliveryClaimConflict[] = [];
  if ((outcome === "outcome_progress" || outcome === "primary_goal_outcome")
    && kind === "contract_only_preparation") conflicts.push("progress_with_preparation_only");
  const observation = jsonObject(raw.progress_observation);
  if (outcome === "primary_goal_outcome" && (kind === "blocker_writeback"
    || (observation?.schema_version === "typed_progress_observation_v0" && observation.result_class === "blocked"))) {
    conflicts.push("primary_outcome_with_blocker");
  }
  if (outcome === "primary_goal_outcome" && raw.outcome_followthrough_required === true) {
    conflicts.push("primary_outcome_with_followthrough");
  }
  return conflicts;
}

export function validateDeliveryClaim(value: unknown): JsonObject {
  const conflicts = diagnoseDeliveryClaim(requireJsonObject(value, "delivery claim"));
  return { schema_version: "delivery_claim_validation_v0", valid: conflicts.length === 0, conflicts };
}

const STABLE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;
const PROGRESS_DELIVERY_OUTCOMES = new Set<DeliveryOutcome>([
  "outcome_progress",
  "primary_goal_outcome",
]);

function jsonObject(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function stableIdentifier(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const candidate = String(value).trim();
  return candidate && STABLE_ID_PATTERN.test(candidate) ? candidate : null;
}

export function isTurnScopedSettlementOutcome(
  deliveryOutcome: unknown,
  progressObservation: unknown,
  expectedSettlementBindingId: string | null,
): boolean {
  const normalizedOutcome = String(deliveryOutcome ?? "").trim() as DeliveryOutcome;
  if (PROGRESS_DELIVERY_OUTCOMES.has(normalizedOutcome)) return true;
  if (
    normalizedOutcome !== "outcome_gap" ||
    expectedSettlementBindingId === null
  ) {
    return false;
  }
  const observation = jsonObject(progressObservation);
  if (
    !observation ||
    observation.schema_version !== "typed_progress_observation_v0" ||
    observation.result_class !== "blocked" ||
    stableIdentifier(observation.work_item_id) !== expectedSettlementBindingId ||
    stableIdentifier(observation.blocker_id) === null ||
    !Array.isArray(observation.evidence_ids) ||
    observation.evidence_ids.length === 0
  ) {
    return false;
  }
  return observation.evidence_ids.every(
    (evidenceId) => stableIdentifier(evidenceId) !== null,
  );
}

export function decodeOptionalDeliveryOutcome(
  value: unknown,
  label = "delivery_outcome",
): DeliveryOutcome | null {
  if (value === null || value === undefined || value === "") return null;
  if (DELIVERY_OUTCOMES.some((candidate) => candidate === value)) {
    return value as DeliveryOutcome;
  }
  throw new EffectRuntimeRequestError(`${label} is unsupported`);
}

export function decodeOptionalMaterialDeliveryOutcome(
  value: unknown,
  label = "delivery_outcome",
): MaterialDeliveryOutcome | null {
  const outcome = decodeOptionalDeliveryOutcome(value, label);
  if (
    outcome === null ||
    MATERIAL_DELIVERY_OUTCOMES.some((candidate) => candidate === outcome)
  ) {
    return outcome as MaterialDeliveryOutcome | null;
  }
  throw new EffectRuntimeRequestError(`${label} is not a material delivery outcome`);
}

export function isMaterialDeliveryOutcome(
  value: DeliveryOutcome | null,
): value is MaterialDeliveryOutcome {
  return MATERIAL_DELIVERY_OUTCOMES.some((candidate) => candidate === value);
}
