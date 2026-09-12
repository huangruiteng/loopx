import { test } from "node:test";
import assert from "node:assert/strict";
import { parseProjectionDelivery, projectionDelivery } from "../../loopx/control_plane/todos/projection_delivery.ts";

test("projection delivery maps mutation and no-op outcomes", () => {
  assert.equal(projectionDelivery(true), "pending");
  assert.equal(projectionDelivery(false), "not_required");
});

test("projection delivery parser accepts provider readback states", () => {
  for (const value of ["pending", "delivered", "current", "not_required"]) {
    assert.equal(parseProjectionDelivery(value), value);
  }
  assert.throws(() => parseProjectionDelivery("unknown"));
});
