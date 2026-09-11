import { z } from "zod";

const nullableText = z.string().nullable();
export const goalArtifactLifecycleSchema = z.object({
  schema_version: z.literal("goal_artifact_lifecycle_projection_v0"),
  goal_id: z.string(),
  read_only: z.literal(true),
  acceptance_assessed: z.literal(false),
  coverage: z.enum(["partial", "unavailable"]),
  missing_sources: z.array(z.string()),
  truncated: z.boolean(),
  milestones: z.array(z.object({ kind: z.string(), observed_at: nullableText, source: z.string(), evidence_refs: z.array(z.string()) })),
  acceptance_gaps: z.array(z.object({ kind: z.string(), owner: nullableText, reason: nullableText, evidence_required: nullableText, observed_at: nullableText, source: z.string() })),
  guards: z.array(z.object({ kind: z.string(), todo_id: nullableText, blocks_agent: nullableText, owner: nullableText, reason: nullableText, evidence_required: nullableText, decision_scope: nullableText })),
  next_action: nullableText,
  next_action_source: nullableText,
});
export type GoalArtifactLifecycle = z.infer<typeof goalArtifactLifecycleSchema>;
