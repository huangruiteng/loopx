import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  legacyCoordinationWriterFencePath,
  loadLegacyCoordinationWriterFence,
} from "../../loopx/control_plane/coordination/legacy_writer_fence.ts";

test("fence reader removes the filesystem error path without dropping the diagnostic", async t => {
  const root = await fs.mkdtemp(join(tmpdir(), "loopx-fence-read-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const path = legacyCoordinationWriterFencePath(root, "synthetic-goal");
  const reason = "EACCES: permission denied, open";

  for (const withPath of [true, false]) {
    await t.test(withPath ? "path-bearing error" : "error without path", async () => {
      // ENOENT returns missing before this branch, so it cannot test cleanup.
      const error = Object.assign(new Error(withPath ? `${reason} '${path}'` : reason), {
        code: "EACCES",
        ...(withPath ? { path } : {}),
      });
      const read = t.mock.method(fs, "readFile", async () => { throw error; });
      syncBuiltinESMExports();
      try {
        assert.deepEqual(await loadLegacyCoordinationWriterFence(root, "synthetic-goal"), {
          status: "failed",
          reason_code: "legacy_writer_fence_read_failed",
          reason,
        });
        assert.equal(read.mock.callCount(), 1);
        assert.deepEqual(read.mock.calls[0].arguments, [path, "utf8"]);
      } finally {
        read.mock.restore();
        syncBuiltinESMExports();
      }
    });
  }
});

test("fence reader distinguishes a missing file from a real directory read failure", async t => {
  const root = await fs.mkdtemp(join(tmpdir(), "loopx-fence-read-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const path = legacyCoordinationWriterFencePath(root, "synthetic-goal");
  assert.deepEqual(await loadLegacyCoordinationWriterFence(root, "synthetic-goal"), { status: "missing" });

  await fs.mkdir(path, { recursive: true });
  const result = await loadLegacyCoordinationWriterFence(root, "synthetic-goal");
  assert.equal(result.status, "failed");
  if (result.status !== "failed") assert.fail("directory read must fail closed");
  assert.equal(result.reason_code, "legacy_writer_fence_read_failed");
  assert.match(result.reason, /EISDIR/);
  assert.equal(result.reason.includes(path), false);
  assert.equal((await fs.stat(path)).isDirectory(), true);
});
