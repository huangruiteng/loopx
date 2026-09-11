/** Synthetic fixed-live-state qualification; no live goals or external services. */
import { mkdtemp, readdir, rm, stat } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { performance } from "node:perf_hooks";
import { SqliteAuthorityStore } from "../../loopx/control_plane/coordination/sqlite_authority_store.ts";

const directory = await mkdtemp(join(tmpdir(), "loopx-sqlite-capacity-"));
const store = new SqliteAuthorityStore(directory, "synthetic-capacity");
const projection = {goal_id: "synthetic-capacity", payload: "x".repeat(4096)};
const percentile = (samples: number[]) => {
  samples.sort((a, b) => a - b);
  return {p50_ms: samples[Math.floor(samples.length * .5)], p95_ms: samples[Math.floor(samples.length * .95)]};
};
async function measure(operation: () => Promise<unknown>) {
  const samples: number[] = [];
  for (let i = 0; i < 100; i++) { const start = performance.now(); await operation(); samples.push(performance.now() - start); }
  return percentile(samples);
}
try {
  let revision: string | null = null;
  let commits: number[] = [];
  const reports = [];
  for (let i = 1; i <= 100000; i++) {
    const start = performance.now();
    const result = await store.commitAuthority({expected_provider_revision: revision, operation_id: `op-${i}`,
      next_projection: projection, events: [{kind: "synthetic"}], receipts: [{operation_id: `op-${i}`}]});
    if (result.status !== "applied") throw new Error(JSON.stringify(result));
    commits.push(performance.now() - start); revision = result.provider_revision;
    if (i === 10000 || i === 100000) {
      const bytes = (await Promise.all((await readdir(directory)).map(async name => (await stat(join(directory, name))).size))).reduce((a, b) => a + b, 0);
      reports.push({operations: i, bytes, commit: percentile(commits),
        head_read: await measure(async () => {if ((await store.loadAuthority()).status !== "loaded") throw new Error("head missing");}),
        receipt_lookup: await measure(async () => {if ((await store.readReceipt("op-5000")).status !== "found") throw new Error("receipt missing");}),
        scan_100: await measure(async () => {const page = await store.scanCommitted(String(i - 100), 100); if (page.status !== "page" || page.transactions.length !== 100) throw new Error("scan failed");})});
      commits = [];
    }
  }
  process.stdout.write(JSON.stringify({node: process.version, platform: process.platform, journal: "WAL", synchronous: "FULL", live_payload_bytes: 4096, ten_day_soak: "not_evaluated", reports}, null, 2) + "\n");
} finally { await rm(directory, {recursive: true, force: true}); }
