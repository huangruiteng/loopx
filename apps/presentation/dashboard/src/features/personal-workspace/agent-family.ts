/**
 * Presentation-side host family resolution.
 *
 * Mirrors the backend rule in `loopx/chat_actions.py`: the family token must be
 * the whole id or end at a `-` delimiter. A substring match displayed an
 * unrelated `kiroscope-worker` as "Kiro CLI" even after the backend correctly
 * kept it independent, which is wrong owner attribution wherever the label is
 * rendered — diagnostics, run timelines, evidence and report cards.
 *
 * A capability row's typed `display_name` / `adapter_kind` stays authoritative;
 * this module is the fallback used when no row is in scope.
 */

export const AGENT_FAMILY_ROOTS = [
  "codex",
  "claude",
  "kiro",
  "trae",
  "coco",
  "openai",
  "anthropic",
] as const;

export type AgentFamilyRoot = (typeof AGENT_FAMILY_ROOTS)[number];

/** Return the bounded family root for an id, or the normalized id itself. */
export function agentFamily(agentId: string): string {
  const token = agentId.trim().toLowerCase().replace(/_/gu, "-");
  for (const root of AGENT_FAMILY_ROOTS) {
    if (token === root || token.startsWith(`${root}-`)) {
      return root;
    }
  }
  return token;
}

/**
 * Resolve the family a capability row should be presented as, preferring the
 * typed adapter kind over the operator-chosen id when the row carries one.
 */
export function presentedAgentFamily(
  agentId: string,
  adapterKind?: string | null,
): string {
  const typed = adapterKind?.trim().toLowerCase() ?? "";
  if (typed.length > 0 && typed !== "status_projection") {
    return agentFamily(typed);
  }
  return agentFamily(agentId);
}
