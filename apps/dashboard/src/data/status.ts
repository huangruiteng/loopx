import rawStatus from "../../../../examples/status.example.json";
import { z } from "zod";

export const queueItemSchema = z.object({
  goal_id: z.string(),
  status: z.string(),
  waiting_on: z.string(),
  severity: z.string(),
  recommended_action: z.string(),
  source: z.string().optional(),
  controller_stage: z.string().optional().nullable(),
  missing_gates: z.array(z.string()).optional().default([]),
  next_handoff_condition: z.string().optional().nullable(),
});

export const humanRewardSchema = z.object({
  recorded_at: z.string().optional().nullable(),
  decision: z.string().optional().nullable(),
  reward: z.string().optional().nullable(),
  reason_summary: z.string().optional().nullable(),
  follow_up: z.string().optional().nullable(),
});

export const controllerReadinessGateSchema = z.object({
  id: z.string().optional().nullable(),
  ok: z.boolean().optional().nullable(),
  review: z.string().optional().nullable(),
});

export const controllerReadinessSchema = z.object({
  classification: z.string().optional().nullable(),
  read_only_observer_ready: z.boolean().optional().nullable(),
  decision_advisor_ready: z.boolean().optional().nullable(),
  write_controller_ready: z.boolean().optional().nullable(),
  missing_gates: z.array(z.string()).optional().default([]),
  review_judgment: z.string().optional().nullable(),
  next_handoff_condition: z.string().optional().nullable(),
  gates: z.array(controllerReadinessGateSchema).optional().default([]),
});

export const runRecordSchema = z.object({
  generated_at: z.string(),
  goal_id: z.string(),
  classification: z.string().optional().nullable(),
  recommended_action: z.string().optional().nullable(),
  health_check: z.string().optional().nullable(),
  active_task_count: z.number().optional().nullable(),
  active_priorities: z.record(z.string(), z.unknown()).optional().nullable(),
  cache_check: z.string().optional().nullable(),
  json_exists: z.boolean().optional().default(false),
  markdown_exists: z.boolean().optional().default(false),
  human_reward: humanRewardSchema.optional().nullable(),
  controller_readiness: controllerReadinessSchema.optional().nullable(),
});

export const runGoalSchema = z.object({
  id: z.string(),
  domain: z.string().optional().nullable(),
  status: z.string().optional().nullable(),
  registry_member: z.boolean().optional().default(false),
  legacy_runtime_goal: z.boolean().optional().default(false),
  adapter_kind: z.string().optional().nullable(),
  adapter_status: z.string().optional().nullable(),
  index_exists: z.boolean().optional().default(false),
  raw_index_records: z.number().optional().default(0),
  unique_runs: z.number().optional().default(0),
  latest_runs: z.array(runRecordSchema).optional().default([]),
});

export const runHistorySchema = z.object({
  available: z.boolean(),
  goal_count: z.number().optional().default(0),
  run_count: z.number().optional().default(0),
  goals: z.array(runGoalSchema).optional().default([]),
  recent_runs: z.array(runRecordSchema).optional().default([]),
});

export const statusPayloadSchema = z.object({
  ok: z.boolean(),
  registry: z.string(),
  runtime_root: z.string(),
  goal_count: z.number(),
  run_count: z.number(),
  contract: z.object({
    ok: z.boolean(),
    summary: z.object({
      errors: z.number(),
      warnings: z.number(),
      checks: z.number(),
    }),
    errors: z.array(z.string()),
    warnings: z.array(z.string()),
    checks: z.array(z.string()).optional().default([]),
  }),
  attention_queue: z.object({
    available: z.boolean(),
    item_count: z.number(),
    needs_user_or_controller: z.number(),
    needs_controller: z.number().optional().default(0),
    needs_codex: z.number(),
    watching_external_evidence: z.number(),
    items: z.array(queueItemSchema),
  }),
  run_history: runHistorySchema.optional().default({
    available: false,
    goal_count: 0,
    run_count: 0,
    goals: [],
    recent_runs: [],
  }),
});

export const rewardDryRunResponseSchema = z.object({
  ok: z.boolean(),
  dry_run: z.boolean().optional().default(true),
  appended: z.boolean().optional().default(false),
  goal_id: z.string().optional().nullable(),
  raw_index_records_before: z.number().optional().nullable(),
  selected_run: z.object({
    generated_at: z.string().optional().nullable(),
    classification: z.string().optional().nullable(),
    recommended_action: z.string().optional().nullable(),
    json_exists: z.boolean().optional().nullable(),
    markdown_exists: z.boolean().optional().nullable(),
  }).optional().nullable(),
  human_reward: humanRewardSchema.optional().nullable(),
  error: z.string().optional().nullable(),
});

export type StatusPayload = z.infer<typeof statusPayloadSchema>;
export type QueueItem = z.infer<typeof queueItemSchema>;
export type HumanReward = z.infer<typeof humanRewardSchema>;
export type ControllerReadiness = z.infer<typeof controllerReadinessSchema>;
export type RunGoal = z.infer<typeof runGoalSchema>;
export type RunRecord = z.infer<typeof runRecordSchema>;
export type RewardDryRunResponse = z.infer<typeof rewardDryRunResponseSchema>;

export function parseStatusPayload(payload: unknown): StatusPayload {
  return statusPayloadSchema.parse(payload);
}

export function parseRewardDryRunResponse(payload: unknown): RewardDryRunResponse {
  return rewardDryRunResponseSchema.parse(payload);
}

export function formatStatusError(error: unknown): string {
  if (error instanceof z.ZodError) {
    return error.issues.map((issue) => `${issue.path.join(".") || "root"}: ${issue.message}`).join("; ");
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export const exampleStatusPayload = parseStatusPayload(rawStatus);
