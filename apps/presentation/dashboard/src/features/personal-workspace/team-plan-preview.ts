/**
 * Present a validated steward team plan for owner confirmation.
 *
 * The reducer owns no action authority: it reads the preview the host already
 * validated and shows, per lane, the Agent that runs it, that lane's first
 * bounded Todo, its acceptance signal, and whether the lane is a declared
 * staffing gap. Confirming the card is what asks the canonical owners to create
 * the lanes, so the card states what confirming does and never claims a lane
 * already exists.
 */

import type { WorkspaceTranslate } from "./i18n.js";

export type TeamPlanPreviewField = { key: string; label: string; value: string };

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? value as Record<string, unknown> : {};
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function teamPlanFields(
  parameters: Record<string, unknown>,
  t: WorkspaceTranslate,
): TeamPlanPreviewField[] {
  const plan = asRecord(parameters.plan);
  const fields: TeamPlanPreviewField[] = [];
  const goalId = asText(parameters.goal_id) || asText(plan.goal_id);
  if (goalId) {
    fields.push({ key: "goal_id", label: t("proposal.field.goalId"), value: goalId });
  }
  const objective = asText(plan.objective);
  if (objective) {
    fields.push({ key: "objective", label: t("proposal.field.objective"), value: objective });
  }
  const lanes = Array.isArray(plan.lanes) ? plan.lanes : [];
  lanes.forEach((rawLane, index) => {
    const lane = asRecord(rawLane);
    const laneId = asText(lane.lane_id) || `lane-${index + 1}`;
    const agentId = asText(lane.agent_id);
    const acceptance = asText(lane.acceptance);
    if (asText(lane.staffing) === "gap") {
      // A gap lane keeps the work it did not staff and creates nothing.
      const declined = asRecord(lane.declined_first_todo);
      fields.push({
        key: `lane_${laneId}`,
        label: agentId || laneId,
        value: [
          t("proposal.teamPlan.gapLane"),
          asText(lane.gap_reason_code),
          asText(declined.text),
        ].filter(Boolean).join(" · "),
      });
      return;
    }
    const todo = asRecord(lane.first_todo);
    const laneValue = [
      asText(todo.priority),
      asText(todo.action_kind),
      asText(todo.text),
    ].filter(Boolean).join(" · ");
    fields.push({
      key: `lane_${laneId}`,
      label: agentId || laneId,
      value: [
        laneValue || t("proposal.teamPlan.laneUnstaffed"),
        acceptance ? `${t("proposal.teamPlan.acceptanceShort")}: ${acceptance}` : "",
      ].filter(Boolean).join(" · "),
    });
  });
  const gaps = Array.isArray(plan.gaps) ? plan.gaps : [];
  if (gaps.length > 0) {
    fields.push({
      key: "lane_gaps",
      label: t("proposal.field.laneGaps"),
      value: gaps
        .map((rawGap) => {
          const gap = asRecord(rawGap);
          return [asText(gap.lane_id), asText(gap.reason_code)].filter(Boolean).join(": ");
        })
        .filter(Boolean)
        .join(" · "),
    });
  }
  const envelope = asRecord(plan.quota_envelope);
  const envelopeEntries = Object.entries(envelope);
  if (envelopeEntries.length > 0) {
    fields.push({
      key: "quota_envelope",
      label: t("proposal.field.quotaEnvelope"),
      value: envelopeEntries.map(([key, value]) => `${key}: ${String(value ?? "")}`).join(" · "),
    });
  }
  const stopCondition = asText(plan.stop_condition);
  if (stopCondition) {
    fields.push({
      key: "stop_condition",
      label: t("proposal.field.stopCondition"),
      value: stopCondition,
    });
  }
  return fields;
}

export function teamPlanLaneCount(parameters: Record<string, unknown>): number {
  const plan = asRecord(parameters.plan);
  return Array.isArray(plan.lanes) ? plan.lanes.length : 0;
}

export function teamPlanGoalId(parameters: Record<string, unknown>): string {
  const plan = asRecord(parameters.plan);
  return asText(parameters.goal_id) || asText(plan.goal_id);
}
