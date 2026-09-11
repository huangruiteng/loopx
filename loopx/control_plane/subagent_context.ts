/** multi_subagent owns its workflow guidance; the hook mechanism stays generic. */
import { AGENT_CONTEXT_PHASES, projectAgentContext, type AgentContextProvider } from "./agent_context.ts";
import type { JsonObject } from "./effect_program.ts";
import { jsonObject, requireJsonObject } from "./runtime_decode.ts";

export const subagentContextProvider: AgentContextProvider = {
  hookId: "multi_subagent.coordinator", capabilityId: "multi_subagent", revision: "v1",
  phases: AGENT_CONTEXT_PHASES,
  produce(input, config) {
    const guidance = {
      before_plan: [
        "For read-heavy tasks, prefer parallel delegation of multiple fresh, independent evidence questions, including within one Todo, up to the configured child limit. Actively look for useful splits before keeping the research serial; avoid duplicate reads or concurrency for its own sake.",
        "For native child tools, read loopx agent-context with the current --goal-id and --agent-id at --phase before_delegate and --phase after_delegate_result. These read-only calls do not start turns or spend quota.",
        "Keep useful work with the coordinator. Verify decisive sources, resolve disagreements and integrate results into the plan; child opinions are not independent evidence.",
      ],
      before_delegate: [
        "Give each child a bounded question, sources, read/write limits, expected evidence and stopping condition. Reuse prior findings; reserve integration for the coordinator.",
        "Explicitly pass the configured model and reasoning effort when the host supports them. Check host availability; never silently substitute. Preferences are not execution receipts.",
      ],
      after_delegate_result: [
        "Check returned sources, omissions and contradictions against the question. Missing or rejected receipts do not establish completed work.",
        "Record accept/defer/reject with reasons and link accepted evidence to the plan and deliverable. Run the parent validation gate before writeback; do not merely concatenate child summaries.",
      ],
    }[input.phase];
    const facts: JsonObject = {
      max_children: config.max_children,
      model_preference: jsonObject(config.model_config),
    };
    const count = input.observations.child_count;
    if (Number.isInteger(count) && Number(count) >= 0) facts.child_count = count;
    if (input.phase === "after_delegate_result") {
      const counts = jsonObject(input.observations.reconciliation_counts);
      facts.receipt_observation = counts ? "host_reconciled" : "not_supplied";
      if (counts) facts.reconciliation_counts = Object.fromEntries(
        Object.entries(counts).filter(([key, item]) =>
          /^[a-z_]{1,40}$/u.test(key) && Number.isInteger(item) && Number(item) >= 0),
      );
    }
    return { guidance, facts, source_refs: [
      "goal_boundary.orchestration", "docs/integrations/codex-subagent-orchestration.md",
    ] };
  },
};

export function evaluateSubagentContext(value: unknown): JsonObject | null {
  const input = requireJsonObject(value, "subagent context");
  const policy = jsonObject(input.orchestration) ?? {};
  const enabled = policy.mode === "multi_subagent" && policy.spawn_allowed === true
    && Number.isInteger(policy.max_children) && Number(policy.max_children) > 0;
  return projectAgentContext({
    phase: input.phase, scope: input.scope, observations: input.observations ?? {},
    capabilities: { multi_subagent: { ...policy, enabled } },
  }, [subagentContextProvider]);
}


export function describeSubagentContext(): JsonObject {
  return { supported_phases: [...subagentContextProvider.phases],
    target: "coordinator", activation: "with_capability", receipt_required: true };
}
