import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  DEFAULT_EFFECT_RUNTIME_IDLE_MS,
  MAX_EFFECT_RUNTIME_IDLE_MS,
  effectRuntimeIdleMs,
} from "../../loopx/control_plane/effect_runtime_config.ts";

interface IdleFixture {
  default_ms: number;
  maximum_ms: number;
  valid: Array<{ raw: string | null; value: number }>;
  invalid: string[];
}

const fixture = JSON.parse(readFileSync(
  new URL("../fixtures/effect_runtime_idle_ms.json", import.meta.url),
  "utf8",
)) as IdleFixture;

test("Effect runtime idle timeout matches the shared valid fixture", () => {
  assert.equal(DEFAULT_EFFECT_RUNTIME_IDLE_MS, fixture.default_ms);
  assert.equal(MAX_EFFECT_RUNTIME_IDLE_MS, fixture.maximum_ms);
  for (const { raw, value } of fixture.valid) {
    assert.equal(effectRuntimeIdleMs(raw ?? undefined), value);
  }
});

for (const value of fixture.invalid) {
  test(`Effect runtime idle timeout rejects '${value}'`, () => {
    assert.throws(
      () => effectRuntimeIdleMs(value),
      /LOOPX_EFFECT_RUNTIME_IDLE_MS/u,
    );
  });
}
