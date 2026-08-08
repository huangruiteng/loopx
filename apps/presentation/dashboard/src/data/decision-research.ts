import { z } from "zod";

import type { PresentationSurface } from "./status";

const researchDecisionSchema = z.enum([
  "selected",
  "rejected",
  "insufficient_evidence",
  "blocked",
  "superseded",
]);

const researchConfidenceSchema = z.enum(["high", "medium", "low"]);
const researchToneSchema = z.enum(["neutral", "success", "warning", "info", "danger"]);
const researchLayerStateSchema = z.enum([
  "supported",
  "partial",
  "rejected",
  "insufficient_evidence",
  "blocked",
  "pending",
]);
const researchGateStateSchema = z.enum([
  "passed",
  "failed",
  "pending",
  "blocked",
  "insufficient_evidence",
  "partial",
]);
const researchEventStateSchema = z.enum([
  "pending",
  "partially_adjudicated",
  "selected",
  "rejected",
  "insufficient_evidence",
  "blocked",
  "superseded",
]);

const researchMetricSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  value: z.string().min(1),
  detail: z.string().min(1),
  tone: researchToneSchema,
}).strict();

const researchSummarySchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  title: z.string().min(1),
  summary: z.string().min(1),
  tone: researchToneSchema,
  destination_anchor: z.string().regex(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/),
}).strict();

const researchLayerSchema = z.object({
  id: z.string().min(1),
  order: z.number().int().positive(),
  label: z.string().min(1),
  status: researchLayerStateSchema,
  summary: z.string().min(1),
  evidence_points: z.array(z.string().min(1)).min(1).max(12),
}).strict();

const researchObservationSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  kind: z.enum([
    "observation_range",
    "current_fact",
    "historical_fact",
    "management_guidance",
    "analyst_estimate",
    "agent_inference",
  ]),
  value: z.string().min(1),
  as_of: z.string().min(1),
  source_ref: z.string().min(1),
  source_type: z.enum([
    "company_filing",
    "company_guidance",
    "regulator",
    "exchange",
    "market_data",
    "industry_source",
    "high_quality_media",
    "community_signal",
    "agent_analysis",
  ]),
  confidence: researchConfidenceSchema,
  invalidation: z.string().min(1),
}).strict();

const researchScenarioSchema = z.object({
  scenario: z.enum(["bull", "base", "bear"]),
  label: z.string().min(1),
  value: z.string().min(1),
  horizon: z.string().min(1),
  probability: z.number().min(0).max(1),
  assumptions: z.array(z.string().min(1)).min(1).max(8),
}).strict();

const researchEntitySchema = z.object({
  entity_id: z.string().min(1),
  symbol: z.string().min(1),
  display_name: z.string().min(1),
  classification: z.string().min(1),
  status: researchDecisionSchema,
  confidence: researchConfidenceSchema,
  inference: z.string().min(1),
  observations: z.array(researchObservationSchema).min(1).max(20),
  scenario_estimates: z.array(researchScenarioSchema).length(3),
  counterevidence: z.array(z.string().min(1)).min(1).max(12),
  thesis_breakers: z.array(z.string().min(1)).min(1).max(12),
  next_events: z.array(z.string().min(1)).max(12),
}).strict().superRefine((entity, context) => {
  const scenarioNames = new Set(entity.scenario_estimates.map((item) => item.scenario));
  if (
    scenarioNames.size !== 3
    || !scenarioNames.has("bull")
    || !scenarioNames.has("base")
    || !scenarioNames.has("bear")
  ) {
    context.addIssue({
      code: "custom",
      message: "scenario_estimates must contain bull, base and bear",
      path: ["scenario_estimates"],
    });
  }
  const probability = entity.scenario_estimates.reduce(
    (sum, item) => sum + item.probability,
    0,
  );
  if (Math.abs(probability - 1) > 0.000001) {
    context.addIssue({
      code: "custom",
      message: "scenario_estimates probabilities must sum to 1",
      path: ["scenario_estimates"],
    });
  }
});

const researchLedgerSchema = z.object({
  case_id: z.string().min(1),
  label: z.string().min(1),
  gate_states: z.array(z.object({
    gate_id: z.string().min(1),
    label: z.string().min(1),
    status: researchGateStateSchema,
    summary: z.string().min(1),
  }).strict()).min(1).max(16),
  decision: researchDecisionSchema,
  summary: z.string().min(1),
  evidence_refs: z.array(z.string().min(1)).min(1).max(20),
}).strict();

const researchArtifactSchema = z.object({
  artifact_id: z.string().min(1),
  kind: z.enum([
    "research_packet",
    "evidence_matrix",
    "event_gate_packet",
    "methodology_note",
  ]),
  label: z.string().min(1),
  summary: z.string().min(1),
  artifact_ref: z.string().min(1),
  evidence_refs: z.array(z.string().min(1)).min(1).max(20),
}).strict();

const researchEventGateSchema = z.object({
  event_id: z.string().min(1),
  label: z.string().min(1),
  status: researchEventStateSchema,
  observation_window: z.string().min(1),
  frozen_hypothesis: z.string().min(1),
  observables: z.array(z.string().min(1)).min(1).max(16),
  current_evidence: z.array(z.string().min(1)).max(16),
  supports: z.array(z.string().min(1)).min(1).max(12),
  refutes: z.array(z.string().min(1)).min(1).max(12),
  thesis_breakers: z.array(z.string().min(1)).min(1).max(12),
  next_review: z.string().min(1),
}).strict();

export const decisionResearchViewSchema = z.object({
  identity: z.object({
    title: z.string().min(1),
    subtitle: z.string().min(1),
    as_of: z.string().min(1),
    evidence_cutoff: z.string().min(1),
  }).strict(),
  adjudication: z.object({
    status: researchDecisionSchema,
    label: z.string().min(1),
    summary: z.string().min(1),
    confidence: researchConfidenceSchema,
  }).strict(),
  metrics: z.array(researchMetricSchema).min(1).max(12),
  dashboard_summaries: z.array(researchSummarySchema).max(3),
  layers: z.array(researchLayerSchema).min(1).max(12),
  entities: z.array(researchEntitySchema).max(24),
  research_ledger: z.array(researchLedgerSchema).max(40),
  artifacts: z.array(researchArtifactSchema).max(20).optional().default([]),
  event_gates: z.array(researchEventGateSchema).max(32),
  method_state: z.object({
    revision: z.string().min(1),
    lifecycle_state: z.string().min(1),
    active_method_changed: z.boolean(),
    summary: z.string().min(1),
  }).strict(),
  boundary: z.object({
    research_aid_only: z.literal(true),
    investment_advice: z.literal(false),
    trading_allowed: z.literal(false),
    raw_provider_payload_recorded: z.literal(false),
    private_source_content_read: z.literal(false),
  }).strict(),
}).strict();

export const presentationProjectionEnvelopeSchema = z.object({
  schema_version: z.literal("extension_projection_surface_v0"),
  extension_id: z.string().min(1),
  extension_revision: z.string().min(1),
  surface_id: z.string().min(1),
  surface_kind: z.string().min(1),
  view_schema: z.literal("decision_research_dashboard_v0"),
  visibility: z.literal("public-safe"),
  goal_id: z.string().min(1),
  generated_at: z.string().min(1),
  review_due_at: z.string().min(1).nullable(),
  lineage: z.record(z.string(), z.unknown()).optional(),
  view: decisionResearchViewSchema,
  payload_sha256: z.string().regex(/^[0-9a-f]{64}$/),
}).strict();

export const presentationProjectionResponseSchema = z.object({
  ok: z.literal(true),
  projection: presentationProjectionEnvelopeSchema,
}).strict();

export type DecisionResearchView = z.infer<typeof decisionResearchViewSchema>;
export type PresentationProjectionEnvelope = z.infer<
  typeof presentationProjectionEnvelopeSchema
>;

export function parsePresentationProjection(
  payload: unknown,
): PresentationProjectionEnvelope {
  return presentationProjectionResponseSchema.parse(payload).projection;
}

export async function fetchPresentationProjection(
  detailUrl: string,
  surface: PresentationSurface,
): Promise<PresentationProjectionEnvelope> {
  if (surface.state !== "ready" && surface.state !== "review_due") {
    throw new Error("surface has no published projection to fetch");
  }
  if (surface.visibility !== "public-safe") {
    throw new Error("rich projection rendering requires public-safe visibility");
  }
  const target = new URL(detailUrl);
  if (
    !["http:", "https:"].includes(target.protocol)
    || !["127.0.0.1", "localhost", "::1", "[::1]"].includes(target.hostname)
  ) {
    throw new Error("projection detail URL must use a loopback host");
  }
  target.searchParams.set("extension_id", surface.detail_ref.extension_id);
  target.searchParams.set("surface_id", surface.detail_ref.surface_id);
  target.searchParams.set("extension_revision", surface.detail_ref.extension_revision);
  target.searchParams.set("payload_sha256", surface.detail_ref.payload_sha256);
  const response = await fetch(target.toString(), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} while loading projection`);
  }
  const projection = parsePresentationProjection(await response.json());
  const expectedIdentity = surface.detail_ref;
  if (
    projection.extension_id !== expectedIdentity.extension_id
    || projection.surface_id !== expectedIdentity.surface_id
    || projection.extension_revision !== expectedIdentity.extension_revision
    || projection.payload_sha256 !== expectedIdentity.payload_sha256
    || projection.view_schema !== surface.view_schema
    || projection.surface_kind !== surface.surface_kind
  ) {
    throw new Error("projection response does not match the requested detail_ref");
  }
  return projection;
}
