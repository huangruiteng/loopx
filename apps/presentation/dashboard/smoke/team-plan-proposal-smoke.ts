/**
 * A validated steward team plan must survive the transport and read as lanes.
 *
 * Before the `team.plan` kind existed in the dashboard schema, the transport
 * rejected the proposal outright, so an owner could never confirm the preview
 * the steward had already validated.
 */

import { typedActionKindSchema, typedActionProposalSchema } from "../src/data/chat.js";
import { teamPlanFields, teamPlanGoalId, teamPlanLaneCount } from "../src/features/personal-workspace/team-plan-preview.js";

const GOAL_ID = "team-plan-smoke-goal";

function check(condition: boolean, message: string) {
  if (!condition) {
    console.error(`FAIL ${message}`);
    process.exitCode = 1;
  }
}

check(typedActionKindSchema.safeParse("team.plan").success, "transport accepts the steward team plan kind");
check(!typedActionKindSchema.safeParse("team.plans").success, "the kind stays exact");

const plan = {
  schema_version: "steward_team_plan_preview_v0",
  kind: "steward_team_plan_preview",
  goal_id: GOAL_ID,
  objective: "Ship the steward team intake",
  lanes: [
    {
      lane_id: "lane_backend",
      agent_id: "agent-backend",
      acceptance: "the bounded Todo is created through the canonical owner",
      staffing: "ready",
      first_todo: {
        text: "Implement the bounded intake",
        priority: "P1",
        task_class: "advancement_task",
        action_kind: "implement",
      },
    },
    {
      lane_id: "lane_review",
      agent_id: "agent-reviewer",
      acceptance: "the review receipt is recorded",
      staffing: "gap",
      gap_reason_code: "agent_not_registered",
      declined_first_todo: {
        text: "Independently review the intake",
        priority: "P1",
        task_class: "advancement_task",
        action_kind: "validate",
      },
    },
  ],
  gaps: [{ lane_id: "lane_review", reason_code: "agent_not_registered" }],
  quota_envelope: { slots: 4, window: "1d" },
  stop_condition: "every lane reports a typed outcome or a stated gap",
  applies: false,
};

const proposal = typedActionProposalSchema.parse({
  schema_version: "loopx_chat_action_proposal_v1",
  proposal_id: "proposal_team_plan_smoke",
  action_kind: "team.plan",
  summary: "Staff a two-lane team",
  normalized_parameters: { goal_id: GOAL_ID, plan, requested_by: "owner" },
  context: { goal_id: GOAL_ID },
  expected_state_fingerprint: "sha256:team-plan-smoke",
  permission_classification: "durable_write",
  validation_evidence: [
    "every ready lane names an Agent this Goal registers",
    "the plan names the Goal it staffs",
  ],
  available_transitions: ["apply", "cancel"],
  status: "preview_ready",
  receipt: null,
  stale: null,
  created_at: "2026-09-16T12:00:00Z",
  updated_at: "2026-09-16T12:00:00Z",
});

check(proposal.action_kind === "team.plan", "the proposal keeps the team plan kind");
check(teamPlanGoalId(proposal.normalized_parameters) === GOAL_ID, "the card names the Goal the plan staffs");
check(teamPlanLaneCount(proposal.normalized_parameters) === 2, "the card counts the previewed lanes");

const translate = (key: string, values?: Record<string, string | number>) => {
  const table: Record<string, string> = {
    "proposal.field.goalId": "Goal",
    "proposal.field.objective": "Objective",
    "proposal.field.laneGaps": "Unstaffed lanes",
    "proposal.field.quotaEnvelope": "Quota envelope",
    "proposal.field.stopCondition": "Stop condition",
    "proposal.teamPlan.acceptanceShort": "acceptance",
    "proposal.teamPlan.gapLane": "unstaffed",
    "proposal.teamPlan.laneUnstaffed": "staffing gap, no first Todo",
  };
  const template = table[key] ?? key;
  return Object.entries(values ?? {}).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    template,
  );
};

const fields = teamPlanFields(proposal.normalized_parameters, translate as never);
const byKey = new Map(fields.map((field) => [field.key, field]));
const readyLane = byKey.get("lane_lane_backend");
const gapLane = byKey.get("lane_lane_review");

check(readyLane?.label === "agent-backend", "a ready lane names the Agent that runs it");
check(
  readyLane?.value.includes("P1") === true
  && readyLane?.value.includes("Implement the bounded intake") === true
  && readyLane?.value.includes("acceptance: the bounded Todo is created through the canonical owner") === true,
  "a ready lane shows its first bounded Todo, its priority and its acceptance signal",
);
check(
  gapLane?.value.startsWith("unstaffed · agent_not_registered") === true
  && gapLane?.value.includes("Independently review the intake") === true,
  "a gap lane says it is unstaffed, names the reason and keeps the work it did not staff",
);
check(byKey.get("lane_gaps")?.value === "lane_review: agent_not_registered", "the gap summary joins lane and reason");
check(byKey.get("quota_envelope")?.value === "slots: 4 · window: 1d", "the quota envelope is shown as data");
check(
  byKey.get("stop_condition")?.value === "every lane reports a typed outcome or a stated gap",
  "the stop condition is shown",
);
check(
  fields.some((field) => field.value.includes("agent-") === true && field.value.includes("ready") === true) === false,
  "the card never renders a lane as already created",
);

if (process.exitCode !== 1) console.log("team plan proposal smoke ok");
