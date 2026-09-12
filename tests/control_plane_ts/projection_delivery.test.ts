import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { isProjectionDelivery, parseProjectionDelivery, projectionDelivery } from "../../loopx/control_plane/todos/projection_delivery.ts";

test("projection delivery maps mutation and no-op outcomes", () => {
  assert.equal(projectionDelivery(true), "pending");
  assert.equal(projectionDelivery(false), "not_required");
});

test("projection delivery parser accepts provider readback states", () => {
  for (const value of ["pending", "delivered", "current", "not_required"]) {
    assert.equal(parseProjectionDelivery(value), value);
  }
  assert.throws(() => parseProjectionDelivery("unknown"));
  assert.equal(isProjectionDelivery("delivered"), true);
  assert.equal(isProjectionDelivery("DELIVERED"), false);
  assert.equal(isProjectionDelivery(null), false);
});

test("composition fixture keeps mutation and provider states distinct", async () => {
  const fixture = JSON.parse(await readFile("tests/fixtures/control_plane/projection_delivery_composition_v0.json", "utf8"));
  for (const item of fixture.cases) {
    const actual = item.changed === undefined ? parseProjectionDelivery(item.readback) : projectionDelivery(item.changed);
    assert.equal(actual, item.expected, item.name);
    assert.equal(item.requires_ack, actual === "delivered" || actual === "current", item.name);
  }
});
