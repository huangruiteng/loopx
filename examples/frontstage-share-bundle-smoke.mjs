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
assertExists(resolve(siteDir, "site-assets/home.css"));
assertExists(resolve(siteDir, "site-assets/home.js"));
assertExists(resolve(siteDir, "site-assets/evidence/long-running-loop-openviking-trajectory.png"));
assertExists(resolve(siteDir, "site-assets/evidence/long-running-loop-ml-experiment-trajectory.png"));
assertExists(resolve(siteDir, "status.frontstage-share.json"));
assertExists(resolve(outDir, "README.md"));
assertExists(resolve(outDir, "frontstage-share-manifest.json"));

const routerSource = await readFile(resolve(repoRoot, "apps/presentation/dashboard/src/router.tsx"), "utf8");
if (!routerSource.includes("basepath:") || !routerSource.includes("import.meta.env.BASE_URL")) {
  throw new Error("dashboard router must derive basepath from Vite BASE_URL for GitHub Pages");
}

const homepageHtml = await readFile(resolve(siteDir, "index.html"), "utf8");
if (!homepageHtml.includes("Your agents keep") || !homepageHtml.includes('class="button button-secondary" href="#showcases"')) {
  throw new Error("homepage root is missing the LoopX hero or curated evidence CTA");
}
if (!homepageHtml.includes('data-hero-wave="progress"') || !homepageHtml.includes('data-hero-wave="judgment"')) {
  throw new Error("homepage hero must retain the finite semantic keyword wave");
}
if (!homepageHtml.includes('class="hero-phrase"')) {
  throw new Error("homepage hero must keep sentence punctuation with the animated phrase");
}
if (!homepageHtml.includes('href="/loopx/frontstage/"')) {
  throw new Error("homepage footer must retain the Frontstage entry");
}
if (!homepageHtml.includes('href="/loopx/docs/"')) {
  throw new Error("homepage navigation must link to the hosted docs portal");
}
for (const developerBookContract of [
  'href="/loopx/docs/book/en/"',
  'data-devbook-base="/loopx/docs/book"',
  'data-devbook-path="/"',
  'data-devbook-path="/chapters/01-from-session-to-loop"',
  'data-devbook-path="/chapters/05-connect-existing-project"',
  'data-devbook-path="/chapters/source-protocol-map"',
]) {
  if (!homepageHtml.includes(developerBookContract)) {
    throw new Error(`homepage is missing the monorepo Developer Book contract: ${developerBookContract}`);
  }
}
if (homepageHtml.includes("cocolord.github.io/loopx-book")) {
  throw new Error("homepage must not depend on the retired external Developer Book publication");
}
if (homepageHtml.includes('https://github.com/huangruiteng/loopx/tree/main/docs')) {
  throw new Error("homepage Docs links must not bypass the hosted docs portal");
}
if (!homepageHtml.includes('data-copy-key="agentSetup"') || !homepageHtml.includes("One message to your current agent") || !homepageHtml.includes('href="#quickstart"')) {
  throw new Error("homepage must make the localized agent setup prompt the primary first-run path");
}
if (!homepageHtml.includes("scripts/install-from-github.sh | bash") || !homepageHtml.includes("loopx connect") || !homepageHtml.includes("Inspect installer")) {
  throw new Error("homepage must retain the official manual setup fallback");
}
if (!homepageHtml.includes("provider-neutral") || !homepageHtml.includes("stateful control plane") || !homepageHtml.includes("data-language-toggle")) {
  throw new Error("homepage must publish the official provider-neutral stateful positioning and language switch");
}
if (!homepageHtml.includes("Evidence from real loops") || !homepageHtml.includes("data-evidence-dialog")) {
  throw new Error("homepage must publish the curated evidence terminal and full-screen evidence viewer");
}
for (const terminalContract of [
  "data-terminal-showcase",
  'data-terminal-tab="issue"',
  'data-terminal-tab="ml"',
  "data-terminal-control",
  "data-terminal-last",
  "Curated replay from public evidence",
  "Redacted owner-run showcase",
  "not a production result, company or employer endorsement, or independently reproducible evidence",
]) {
  if (!homepageHtml.includes(terminalContract)) {
    throw new Error(`homepage evidence terminal is missing contract: ${terminalContract}`);
  }
}
for (const assetName of [
  "long-running-loop-openviking-trajectory.png",
  "long-running-loop-ml-experiment-trajectory.png",
]) {
  if (!homepageHtml.includes(`/loopx/site-assets/evidence/${assetName}`)) {
    throw new Error(`homepage evidence asset did not resolve against the GitHub Pages base: ${assetName}`);
  }
}
const homepageScript = await readFile(resolve(siteDir, "site-assets/home.js"), "utf8");
if (!homepageScript.includes('"hero.eyebrow": "开放 · 有状态 · Provider-neutral"') || !homepageScript.includes('requestedLanguage === "zh" ? "zh" : "en"')) {
  throw new Error("homepage language switch must include the public-safe Chinese locale and default to English");
}
if (
  !homepageScript.includes("developerBookTargets")
  || !homepageScript.includes('language === "zh" ? "" : "/en"')
) {
  throw new Error("homepage language switch must route the Developer Book to the matching locale");
}
for (const promptContract of [
  "Connect the current project to LoopX",
  "Do not clone LoopX",
  "README Quick Start",
  "no-clone installer",
  "loopx doctor",
  "loopx connect/bootstrap",
  "project connection status, current user gate, top agent todo",
  "next safe action, and available commands",
  "/loopx <complex task>",
  "/loopx <goal text>",
  "concise ordered plan",
  "P0/P1/P2 todos",
  "把当前项目接入 LoopX",
  "下一步安全动作是什么",
]) {
  if (!homepageScript.includes(promptContract)) {
    throw new Error(`homepage agent setup prompt is missing contract: ${promptContract}`);
  }
}
const setupPromptMatch = homepageScript.match(/const setupPrompts = \{\s+en: `([\s\S]*?)`,\s+zh: `([\s\S]*?)`,\s+\};/);
if (!setupPromptMatch) {
  throw new Error("homepage must expose concise English and Chinese setup prompts");
}
for (const [language, prompt] of [["English", setupPromptMatch[1]], ["Chinese", setupPromptMatch[2]]]) {
  if (prompt.length < 300 || prompt.length > 1_000) {
    throw new Error(`${language} homepage setup prompt must stay concise and complete; received ${prompt.length} characters`);
  }
}
if (!homepageScript.includes('document.createElement("textarea")') || !homepageScript.includes('document.execCommand("copy")')) {
  throw new Error("homepage setup prompt must keep a clipboard fallback for non-secure preview origins");
}
if (!homepageScript.includes("Math.min(200, Math.max(50, nextZoom))") || !homepageScript.includes('addEventListener("pointerdown"')) {
  throw new Error("homepage evidence viewer must retain bounded zoom and drag-to-pan controls");
}
if (!homepageScript.includes("trigger.dataset.evidenceTitle") || !homepageHtml.includes("data-evidence-title=")) {
  throw new Error("homepage evidence viewer must retain localized, evidence-specific dialog titles");
}
for (const terminalMotionContract of [
  "playTerminalPanel",
  'addEventListener("animationend"',
  'event.key !== "ArrowLeft"',
  'window.matchMedia("(prefers-reduced-motion: reduce)")',
]) {
  if (!homepageScript.includes(terminalMotionContract)) {
    throw new Error(`homepage evidence terminal motion is missing contract: ${terminalMotionContract}`);
  }
}
if (!homepageScript.includes("prepareHeroWaves") || !homepageScript.includes('span.style.setProperty("--char-delay"')) {
  throw new Error("homepage hero must split localized keywords into accessible staggered characters");
}
const homepageCss = await readFile(resolve(siteDir, "site-assets/home.css"), "utf8");
if (!homepageCss.includes("@media (prefers-reduced-motion: reduce)") || !homepageCss.includes("animation-iteration-count: 1 !important")) {
  throw new Error("homepage motion must expose a static reduced-motion state");
}
if (!homepageCss.includes("@keyframes terminal-line-in") || !homepageCss.includes(".terminal-demo-panel.is-paused") || !homepageCss.includes(".terminal-playback { display: none; }")) {
  throw new Error("homepage evidence terminal must support finite replay, pause, and a static reduced-motion state");
}
if (!homepageCss.includes("@keyframes hero-word-wave") || !homepageCss.includes("var(--char-delay, 0ms)") || !homepageCss.includes("animation: none !important; color: inherit")) {
  throw new Error("homepage hero keyword wave must be staggered, finite, and reduced-motion safe");
}
if (!homepageHtml.includes('href="/loopx/site-assets/home.css"') || homepageHtml.includes("__LOOPX_BASE__")) {
  throw new Error("homepage assets did not resolve against the GitHub Pages base");
}
const frontstageHtml = await readFile(resolve(siteDir, "frontstage/index.html"), "utf8");
if (!frontstageHtml.includes('/loopx/assets/')) {
  throw new Error("frontstage entry did not retain the compiled dashboard assets");
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
if (
  manifest.homepage_entry !== "site/index.html" ||
  manifest.frontstage_entry !== "site/frontstage/index.html"
) {
  throw new Error(`manifest entries mismatch: ${JSON.stringify(manifest)}`);
}
if (manifest.content_sources?.public_homepage !== "apps/presentation/site") {
  throw new Error(`manifest homepage source mismatch: ${JSON.stringify(manifest.content_sources)}`);
}
const homepageEvidenceAssets = manifest.content_sources?.homepage_evidence_assets ?? [];
for (const assetPath of [
  "docs/assets/long-running-loop-openviking-trajectory.png",
  "docs/assets/long-running-loop-ml-experiment-trajectory.png",
]) {
  if (!homepageEvidenceAssets.includes(assetPath)) {
    throw new Error(`manifest homepage evidence source mismatch: ${JSON.stringify(homepageEvidenceAssets)}`);
  }
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
const interactivePages = manifest.content_sources?.interactive_case_pages ?? [];
if (!interactivePages.includes("docs/showcases/cases/0619-dynamic-workflow-hardware-agent.html")) {
  throw new Error(`share bundle did not include the hardware-agent interactive page: ${JSON.stringify(interactivePages)}`);
}
for (const pagePath of [
  "docs/showcases/index.html",
  "docs/showcases/index.en.html",
  "docs/showcases/cases/0624-pr-issue-auto-fix.html",
  "docs/showcases/cases/0624-pr-issue-auto-fix.en.html",
  "docs/showcases/cases/0619-dynamic-workflow-hardware-agent.en.html",
]) {
  if (!interactivePages.includes(pagePath)) {
    throw new Error(`share bundle did not include expected showcase page ${pagePath}: ${JSON.stringify(interactivePages)}`);
  }
  assertExists(resolve(siteDir, pagePath));
}
assertExists(resolve(siteDir, "docs/showcases/cases/0619-dynamic-workflow-hardware-agent.html"));
const hardwareCaseHtml = await readFile(resolve(siteDir, "docs/showcases/cases/0619-dynamic-workflow-hardware-agent.html"), "utf8");
if (!hardwareCaseHtml.includes("loopx 在芯片开发任务上的实践") || !hardwareCaseHtml.includes("VeeR EH1")) {
  throw new Error("copied hardware-agent interactive page is missing expected public case content");
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
