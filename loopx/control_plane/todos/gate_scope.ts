/** Addressed permission scope is independent of execution ownership. */
export interface GateScope {
  global: boolean;
  blocks: string | null;
  claim: string | null;
}

export function gateAddressesAgent(gate: GateScope, agent: string | null): boolean {
  if (gate.global) return true;
  if (gate.blocks) return gate.blocks === agent;
  return !gate.claim || gate.claim === agent;
}
