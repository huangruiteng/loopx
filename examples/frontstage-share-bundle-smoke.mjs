#!/usr/bin/env node
// Smoke-test the public-safe frontstage static export bundle.

import { spawnSync } from "node:child_process";
import { readFile, readdir, rm, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = resolve("/tmp", "loopx-frontstage-share-bundle-smoke");
const privateTrapFixturePath = resolve(repoRoot, "examples/fixtures/frontstage-private-status-trap.public.json");

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
    new RegExp("byte" + "dance", "i"),
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

function collectFakePrivateMarkers(text) {
  return Array.from(new Set(text.match(/GH_FAKE_[A-Z0-9_]+/g) ?? [])).sort();
}

async function collectGeneratedTextFiles(rootDir) {
  const files = [];
  async function visit(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const path = resolve(dir, entry.name);
      if (entry.isDirectory()) {
        await visit(path);
      } else if (entry.isFile()) {
        const info = await stat(path);
        if (info.size <= 2_000_000 && /\.(css|html|js|json|md|txt)$/i.test(path)) {
          files.push(path);
        }
      }
    }
  }
  await visit(rootDir);
  return files;
}

await rm(outDir, { force: true, recursive: true });
run(process.execPath, [
  resolve(repoRoot, "examples/export-frontstage-share-bundle.mjs"),
  "--out-dir",
  outDir,
  "--base",
  "/loopx/",
]);

const siteDir = resolve(outDir, "site");
assertExists(resolve(siteDir, "index.html"));
assertExists(resolve(siteDir, "frontstage/index.html"));
assertExists(resolve(siteDir, "status.frontstage-share.json"));
assertExists(resolve(outDir, "README.md"));
assertExists(resolve(outDir, "frontstage-share-manifest.json"));

const routerSource = await readFile(resolve(repoRoot, "apps/dashboard/src/router.tsx"), "utf8");
if (!routerSource.includes("basepath:") || !routerSource.includes("import.meta.env.BASE_URL")) {
  throw new Error("dashboard router must derive basepath from Vite BASE_URL for GitHub Pages");
}

const status = JSON.parse(await readFile(resolve(siteDir, "status.frontstage-share.json"), "utf8"));
if (status.attention_queue?.items?.[0]?.goal_channel_projection?.schema_version !== "goal_channel_projection_v0") {
  throw new Error("share fixture did not include goal_channel_projection_v0");
}
if (status.attention_queue.items[0].goal_channel_projection.truth_contract.projection_is_writable !== false) {
  throw new Error("share fixture must stay read-only");
}

const manifest = JSON.parse(await readFile(resolve(outDir, "frontstage-share-manifest.json"), "utf8"));
if (manifest.base !== "/loopx/") {
  throw new Error(`manifest base mismatch: ${manifest.base}`);
}
if (manifest.public_boundary.write_api !== false || manifest.public_boundary.live_registry_state !== false) {
  throw new Error(`manifest public boundary is too permissive: ${JSON.stringify(manifest.public_boundary)}`);
}
if (manifest.public_boundary.primary_content_is_showcase_catalog !== true) {
  throw new Error("manifest must declare showcase catalog as the primary public content source");
}
if (manifest.content_sources?.primary_public_story !== "docs/showcases/showcase-catalog.json") {
  throw new Error(`manifest primary content source mismatch: ${JSON.stringify(manifest.content_sources)}`);
}
if (manifest.content_sources?.live_status_feed !== false) {
  throw new Error("public share bundle must not declare a live status feed content source");
}

const fakePrivateTrapFixture = await readFile(privateTrapFixturePath, "utf8");
const fakePrivateTrapMarkers = collectFakePrivateMarkers(fakePrivateTrapFixture);
if (fakePrivateTrapMarkers.length < 6) {
  throw new Error("fake-private frontstage trap fixture is too weak");
}
for (const path of await collectGeneratedTextFiles(outDir)) {
  const text = await readFile(path, "utf8");
  assertNoLeak(text, path);
  const leakedTrapMarkers = fakePrivateTrapMarkers.filter((marker) => text.includes(marker));
  if (leakedTrapMarkers.length) {
    throw new Error(`${path} leaked fake-private frontstage trap markers: ${leakedTrapMarkers.join(", ")}`);
  }
}

const readmeText = await readFile(resolve(outDir, "README.md"), "utf8");
if (readmeText.includes("?statusUrl=")) {
  throw new Error("share bundle README must not publish a statusUrl-loaded frontstage link");
}
if (!readmeText.includes("docs/showcases/showcase-catalog.json")) {
  throw new Error("share bundle README must name the showcase catalog as the primary story source");
}
if (!readmeText.includes("frontstage/")) {
  throw new Error("share bundle README must publish the frontstage showcase entry");
}

console.log("frontstage-share-bundle-smoke: ok");
