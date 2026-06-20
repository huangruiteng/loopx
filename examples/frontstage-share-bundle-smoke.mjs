#!/usr/bin/env node
// Smoke-test the public-safe frontstage static export bundle.

import { spawnSync } from "node:child_process";
import { readFile, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = resolve("/tmp", "goal-harness-frontstage-share-bundle-smoke");

function run(command, args, cwd = repoRoot) {
  const result = spawnSync(command, args, {
    cwd,
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: ["/opt/homebrew/bin", "/usr/local/bin", process.env.PATH].filter(Boolean).join(":"),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.status !== 0) {
    throw new Error(`Command failed: ${command} ${args.join(" ")}\n${result.stderr}\n${result.stdout}`);
  }
  return result.stdout;
}

function assertExists(path) {
  if (!existsSync(path)) {
    throw new Error(`Missing expected file: ${path}`);
  }
}

function assertNoLeak(text, label) {
  const forbidden = [
    /\/Users\//,
    /\/private\//,
    /bytedance/i,
    new RegExp("lark" + "office", "i"),
    new RegExp("\\.codex/goals|\\.goal-" + "harness"),
    new RegExp("raw_" + "internal_note"),
    /BEGIN (?:RSA |OPENSSH |EC |)PRIVATE KEY/,
    /\b(?:api[_-]?key|auth[_-]?token|access[_-]?token)\s*[:=]/i,
  ];
  const hit = forbidden.find((pattern) => pattern.test(text));
  if (hit) {
    throw new Error(`${label} leaked forbidden pattern: ${hit}`);
  }
}

await rm(outDir, { force: true, recursive: true });
run(process.execPath, [
  resolve(repoRoot, "examples/export-frontstage-share-bundle.mjs"),
  "--out-dir",
  outDir,
  "--base",
  "/goal-harness/",
]);

const siteDir = resolve(outDir, "site");
assertExists(resolve(siteDir, "index.html"));
assertExists(resolve(siteDir, "frontstage/index.html"));
assertExists(resolve(siteDir, "status.frontstage-share.json"));
assertExists(resolve(outDir, "README.md"));
assertExists(resolve(outDir, "frontstage-share-manifest.json"));

const status = JSON.parse(await readFile(resolve(siteDir, "status.frontstage-share.json"), "utf8"));
if (status.attention_queue?.items?.[0]?.goal_channel_projection?.schema_version !== "goal_channel_projection_v0") {
  throw new Error("share fixture did not include goal_channel_projection_v0");
}
if (status.attention_queue.items[0].goal_channel_projection.truth_contract.projection_is_writable !== false) {
  throw new Error("share fixture must stay read-only");
}

const manifest = JSON.parse(await readFile(resolve(outDir, "frontstage-share-manifest.json"), "utf8"));
if (manifest.base !== "/goal-harness/") {
  throw new Error(`manifest base mismatch: ${manifest.base}`);
}
if (manifest.public_boundary.write_api !== false || manifest.public_boundary.live_registry_state !== false) {
  throw new Error(`manifest public boundary is too permissive: ${JSON.stringify(manifest.public_boundary)}`);
}

for (const [label, path] of Object.entries({
  readme: resolve(outDir, "README.md"),
  status: resolve(siteDir, "status.frontstage-share.json"),
  manifest: resolve(outDir, "frontstage-share-manifest.json"),
})) {
  assertNoLeak(await readFile(path, "utf8"), label);
}

console.log("frontstage-share-bundle-smoke: ok");
