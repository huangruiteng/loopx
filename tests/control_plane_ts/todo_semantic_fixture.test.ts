import test from "node:test";
import assert from "node:assert/strict";

import {productionScaleCoordinationFixture} from "./production_scale_coordination_fixture.ts";

test("production-scale fixture carries cross-RFC semantic edge cases", () => {
  const fixture = productionScaleCoordinationFixture("fixture-goal");
  const cases = fixture.semantic_cases;
  assert.equal(cases.title_only_monitor.title, "Observe dependency health");
  assert.equal(cases.title_only_monitor.text, "");
  assert.equal(cases.excluded_unclaimed_advancement.claimed_by, null);
  assert.deepEqual(cases.excluded_unclaimed_advancement.excluded_agents, ["agent-a"]);
  assert.equal(cases.global_gate_without_goal_binding.global_gate, true);
  assert.equal(cases.global_gate_without_goal_binding.goal_bound, false);
  assert.equal(cases.expired_lease.lease_epoch, 7);
});
