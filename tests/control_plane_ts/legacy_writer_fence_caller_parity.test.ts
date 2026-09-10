import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

import type { JsonObject } from "../../loopx/control_plane/effect_program.ts";
import { legacyCoordinationWriterFencePath } from "../../loopx/control_plane/coordination/legacy_writer_fence.ts";
import { GOAL, normalize, observeRow, TS_ROWS, type ParityRow } from "./legacy_writer_fence_caller_parity_support.ts";

/**
 * Data-driven sibling-caller parity for fenced legacy writes.
 *
 * Every row compares the complete envelope, the exclusion-free effect snapshot
 * of the runtime root, the declared after-state of named files, and (for
 * fence-close rows) the identical retry against the literal expectation in the
 * fixture after normalizing temporary roots and Node's optional EISDIR path.
 * Nothing is matched by prefix or substring, so a truncated
 * remediation, a fabricated receipt, a drifted settlement kind, or a skipped
 * guard each fails exactly one row.
 */

interface FixtureRow {
  id: string;
  surface: "ts_entry" | "cli";
  caller: ParityRow["caller"];
  fence_state: ParityRow["fence_state"];
  expect: JsonObject;
  effect: { added: string[]; removed: string[]; changed: string[] };
  retry: JsonObject | null;
  after?: Record<string, JsonObject>;
  baseline: Record<string, unknown> | null;
}

const fixture = JSON.parse(
  readFileSync(new URL("../fixtures/control_plane/legacy_writer_fence_caller_parity_v0.json", import.meta.url), "utf8"),
) as { schema_version: string; rows: FixtureRow[] };
const rows = fixture.rows.filter((row) => row.surface === "ts_entry");

test("EISDIR normalization accepts only the exact fence diagnostic variant", () => {
  const root = "/synthetic-runtime";
  const message = "EISDIR: illegal operation on a directory, read";
  const path = legacyCoordinationWriterFencePath(root, GOAL);
  const legacy = { error: message, write_check: { reason: message }, error_code: "legacy_writer_fence_read_failed" };
  assert.deepEqual(normalize(legacy, root), legacy);
  assert.deepEqual(normalize({
    ...legacy, error: `${message} '${path}'`, write_check: { reason: `${message} '${path}'` },
  }, root), legacy);
  for (const unexpected of [
    `${message} '${path}.wrong'`,
    `${message} '${path}' extra`,
    `${message.replace("EISDIR", "EACCES")} '${path}'`,
  ]) {
    assert.notEqual(normalize({ error: unexpected }, root).error, message);
  }
  assert.notEqual(normalize({ note: `${message} '${path}'` }, root).note, message);
});

function globMatches(pattern: string, path: string): boolean {
  const escaped = pattern.split("*").map((part) => part.replace(/[.+?^${}()|[\]\\]/g, "\\$&")).join("[^/]*");
  return new RegExp(`^${escaped}$`).test(path);
}

function listFiles(root: string, prefix = ""): string[] {
  return readdirSync(join(root, prefix), { withFileTypes: true }).flatMap((entry) => {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    return entry.isDirectory() ? listFiles(root, rel) : [rel];
  });
}

test("the fixture declares every TypeScript entry row exactly once", () => {
  assert.equal(fixture.schema_version, "loopx_legacy_writer_fence_caller_parity_v0");
  assert.deepEqual(rows.map((row) => row.id).sort(), TS_ROWS.map((row) => row.id).sort());
  for (const row of rows) {
    for (const [revision, delta] of Object.entries(row.baseline ?? {})) {
      if (revision === "note") continue;
      assert.notDeepEqual(delta, row.expect, `${row.id}: stale baseline annotation for ${revision}`);
    }
  }
});

for (const row of rows) {
  test(`fence parity: ${row.id}`, async () => {
    const parity = TS_ROWS.find((candidate) => candidate.id === row.id);
    assert.ok(parity, `${row.id} is not an executable row`);
    const observed = await observeRow(parity);
    assert.deepEqual(observed.envelope, row.expect);
    assert.deepEqual(observed.effect, row.effect);
    assert.deepEqual(observed.retry, row.retry);
    const files = listFiles(observed.runtime_root);
    for (const [target, subset] of Object.entries(row.after ?? {})) {
      const matches = files.filter((path) => path === target || globMatches(target, path));
      assert.equal(matches.length, 1, `${row.id}: ${target} matched ${matches.length} files`);
      const record = JSON.parse(readFileSync(join(observed.runtime_root, matches[0]), "utf8")) as JsonObject;
      for (const [key, value] of Object.entries(subset)) {
        assert.deepEqual(record[key], value, `${row.id}: ${target} ${key}`);
      }
    }
  });
}
