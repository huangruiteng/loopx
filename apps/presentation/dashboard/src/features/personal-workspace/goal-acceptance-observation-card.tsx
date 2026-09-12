import type { WorkspaceGoal } from "./personal-workspace-model";
import { useWorkspaceI18n } from "./i18n";

export function GoalAcceptanceObservationCard({ goal }: { goal: WorkspaceGoal }) {
  const { t } = useWorkspaceI18n();
  const labels = {
    connected: t("acceptance.connected"), mapped: t("acceptance.mapped"), refreshed: t("acceptance.refreshed"),
    adapter_inspected: t("acceptance.inspected"), run_recorded: t("acceptance.recorded"), reward_judged: t("acceptance.judged"),
    operator_approved: t("acceptance.approved"), controller_ready: t("acceptance.ready"),
    attention_queue: t("acceptance.attentionSource"), agent_vision: t("acceptance.visionSource"),
    todo_projection: t("acceptance.todoSource"), current_run: t("acceptance.runSource"),
  };
  const label = (key: string) => labels[key as keyof typeof labels] ?? t("acceptance.unknown");
  const projection = goal.acceptanceObservation;
  const unavailable = goal.loadState || !projection || projection.goal_id !== goal.goalId || projection.coverage === "unavailable";
  return <section className="personal-detail-card personal-goal-acceptance" aria-label={t("acceptance.title")}>
    <div className="personal-detail-card-title"><h3>{t("acceptance.title")}</h3><em>{t("common.readOnly")}</em></div>
    <p role="status">{t(unavailable ? "acceptance.unavailable" : "acceptance.partial")}</p>
    {!unavailable && projection ? <>
      <h4>{t("acceptance.gaps")}</h4>
      {projection.acceptance_gaps.length ? projection.acceptance_gaps.map((gap, index) => <div className="personal-acceptance-observation" key={`${gap.kind}:${gap.owner}:${index}`}>
        <p>{gap.reason ?? t("acceptance.reasonUnknown")}</p>
        <dl><div><dt>{t("common.owner")}</dt><dd>{gap.owner ?? t("acceptance.unknown")}</dd></div>
          <div><dt>{t("acceptance.required")}</dt><dd>{gap.evidence_required ?? t("acceptance.unknown")}</dd></div>
          <div><dt>{t("acceptance.observed")}</dt><dd>{gap.observed_at ?? t("acceptance.unknown")}</dd></div></dl>
      </div>) : <p>{t("acceptance.noGaps")}</p>}
      <h4>{t("acceptance.guards")}</h4>
      {projection.guards.length ? projection.guards.map((guard, index) => <div className="personal-acceptance-observation" key={`${guard.todo_id}:${index}`}>
        <p>{guard.reason ?? t("acceptance.reasonUnknown")}</p>
        <dl><div><dt>{t("common.owner")}</dt><dd>{guard.owner ?? t("acceptance.unknown")}</dd></div>
          {guard.blocks_agent ? <div><dt>{t("common.agent")}</dt><dd>{guard.blocks_agent}</dd></div> : null}
          {guard.todo_id ? <div><dt>{t("common.task")}</dt><dd>{guard.todo_id}</dd></div> : null}
          <div><dt>{t("acceptance.required")}</dt><dd>{guard.evidence_required ?? t("acceptance.unknown")}</dd></div>
          <div><dt>{t("acceptance.scope")}</dt><dd>{guard.decision_scope ?? t("acceptance.unknown")}</dd></div></dl>
      </div>) : <p>{t("acceptance.noGuards")}</p>}
      <h4>{t("acceptance.next")}</h4><p>{projection.next_action ?? t("acceptance.unknown")}</p>
      <details><summary>{t("acceptance.historical_progress")} · {projection.historical_progress.length}</summary>
        <p>{t("acceptance.historical")}</p>
        {projection.historical_progress.map((observation) => <p key={observation.kind}><strong>{label(observation.kind)}</strong> · {observation.observed_at ?? t("acceptance.unknown")} {observation.evidence_refs.join(", ")}</p>)}
      </details>
      {projection.missing_sources.length ? <p>{t("acceptance.missing")} {projection.missing_sources.map(label).join(", ")}</p> : null}
      {projection.truncated ? <p>{t("acceptance.truncated")}</p> : null}
    </> : null}
  </section>;
}
