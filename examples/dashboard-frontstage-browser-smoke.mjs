#!/usr/bin/env node
// Browser-level smoke for the read-only goal channel frontstage route.

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/dashboard");
const fixtureName = "status.frontstage.browser-smoke.json";
const fixturePath = resolve(dashboardDir, "public", fixtureName);
const privateTrapFixtureName = "status.frontstage.private-trap.json";
const privateTrapFixturePath = resolve(dashboardDir, "public", privateTrapFixtureName);
const privateTrapSourcePath = resolve(repoRoot, "examples/fixtures/frontstage-private-status-trap.public.json");
const visualOutputDir = resolve(repoRoot, "output/playwright/dashboard-frontstage-visual-acceptance");
const port = Number(process.env.LOOPX_DASHBOARD_FRONTSTAGE_SMOKE_PORT ?? "5197");
const fakePrivateTrapMarkers = [
  "GH_FAKE_PRIVATE_STATUS_ALPHA",
  "GH_FAKE_PRIVATE_PLAN_SUMMARY_ALPHA",
  "GH_FAKE_LIVE_STATUS_FEED_BETA",
  "GH_FAKE_PRIVATE_REGISTRY_SUMMARY_GAMMA",
  "GH_FAKE_PRIVATE_TODO_GAMMA",
  "GH_FAKE_PRIVATE_EVENT_DELTA",
  "GH_FAKE_PRIVATE_LEDGER_SOURCE_EPSILON",
  "GH_FAKE_PRIVATE_SPEND_POLICY_ZETA",
  "GH_FAKE_PRIVATE_ARTIFACT_ETA",
  "GH_FAKE_PRIVATE_RUNTIME_ROOT_THETA",
  "GH_FAKE_PRIVATE_ARTIFACT_PATH_IOTA",
];

function projectionFor(goalId, displayName, claimedBy, todoTitle) {
  return {
    schema_version: "goal_channel_projection_v0",
    mode: "read_only",
    goal_id: goalId,
    display_name: displayName,
    generated_at: "2026-06-20T09:00:00Z",
    latest_status: "live_fixture_loaded",
    waiting_on: "codex",
    next_action: `${displayName} live next action for FAKE_PRIVATE_STATUS_ALPHA`,
    source_refs: {
      status_generated_at: "2026-06-20T09:00:00Z",
      event_ledger_source: "browser-smoke-fixture",
      private_marker: "FAKE_INTERNAL_TABLE_BETA",
    },
    decision_frame: {
      user_action_required: false,
      agent_action_required: true,
      quiet_noop_allowed: false,
    },
    quota: {
      allowed_slots: 10,
      spend_policy: "spend after validated live writeback",
      spent_slots: 3,
      state: "eligible",
    },
    user_todos: [
      {
        todo_id: `${goalId}_user_gate`,
        priority: "P0",
        status: "open",
        task_class: "user_gate",
        title: `Review live handoff gate before delivery for ${displayName}.`,
      },
      {
        todo_id: `${goalId}_user_evidence`,
        priority: "P1",
        status: "open",
        task_class: "evidence_review",
        title: `Confirm external evidence packet for ${displayName}.`,
      },
    ],
    agent_todos: [
      {
        todo_id: `${goalId}_todo`,
        priority: "P1",
        status: "open",
        claimed_by: claimedBy,
        action_kind: "frontstage_render",
        task_class: "advancement_task",
        title: `${todoTitle} FAKE_PRIVATE_TODO_GAMMA`,
      },
      {
        todo_id: `${goalId}_todo_filter`,
        priority: "P2",
        status: "open",
        claimed_by: claimedBy,
        action_kind: "frontstage_filter",
        task_class: "productization_task",
        title: `Document filtered ops route for ${displayName}.`,
      },
    ],
    open_gates: [
      {
        gate_id: `${goalId}_gate`,
        kind: "user_channel",
        status: "clear",
        blocks: [],
      },
    ],
    active_leases: [
      {
        owner_agent: claimedBy,
        status: "soft_claim",
        todo_id: `${goalId}_todo`,
      },
    ],
    artifacts: [
      {
        kind: "fixture",
        label: "browser smoke statusUrl",
        path: "docs/showcases/showcase-catalog.json",
      },
    ],
    recent_events: [
      {
        generated_at: "2026-06-20T09:00:00Z",
        classification: "live_fixture_event",
        summary: `${displayName} rendered from statusUrl with FAKE_PRIVATE_EVENT_DELTA`,
      },
    ],
    source_warnings: [
      {
        kind: "browser_smoke_public_fixture",
        message: "fixture contains compact public-safe fields only",
      },
    ],
    truth_contract: {
      event_ledger_is_source_of_truth: true,
      projection_is_writable: false,
      recompute_rule: "reload statusUrl and parse attention_queue.items[].goal_channel_projection",
      write_authority: "none",
    },
  };
}

const statusFixture = {
  ok: true,
  registry: "./fixtures/registry.global.json",
  runtime_root: "./fixtures/runtime",
  goal_count: 2,
  run_count: 2,
  status_contract: {
    schema_version: 2,
    minimum_dashboard_schema_version: 2,
    producer: "loopx status",
    reload_hint: "scripts/macos-dashboard-launchagent.sh restart",
  },
  local_dashboard_api: {
    source: "serve-status",
    reward_dry_run_url: "/reward/dry-run",
    reward_append_url: null,
    reward_write_enabled: false,
    configure_goal_dry_run_url: "/control-plane/configure-goal/dry-run",
    configure_goal_apply_url: null,
    control_plane_write_enabled: false,
  },
  contract: {
    ok: true,
    summary: { errors: 0, warnings: 0, checks: 1 },
    errors: [],
    warnings: [],
    checks: ["public-safe frontstage browser fixture"],
  },
  attention_queue: {
    available: true,
    item_count: 2,
    needs_user_or_controller: 0,
    needs_controller: 0,
    needs_codex: 2,
    watching_external_evidence: 0,
    autonomous_backlog_candidates: null,
    items: [
      {
        goal_id: "live-goal-a",
        status: "frontstage_live_fixture",
        waiting_on: "codex",
        severity: "action",
        recommended_action: "render live goal A",
        source: "fixture",
        goal_channel_projection: projectionFor(
          "live-goal-a",
          "Live Goal Channel",
          "codex-side-bypass",
          "Render live statusUrl channel projection.",
        ),
      },
      {
        goal_id: "live-goal-b",
        status: "frontstage_live_fixture",
        waiting_on: "codex",
        severity: "watch",
        recommended_action: "render live goal B",
        source: "fixture",
        goal_channel_projection: projectionFor(
          "live-goal-b",
          "Second Live Channel",
          "codex-main-control",
          "Keep second live channel selectable.",
        ),
      },
    ],
  },
};

function loadPlaywright() {
  const candidates = [
    process.env.LOOPX_PLAYWRIGHT_PACKAGE,
    resolve(homedir(), ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"),
  ].filter(Boolean);

  try {
    return require("playwright");
  } catch {
    // Try explicit or bundled local packages below.
  }

  for (const candidate of candidates) {
    if (!candidate || !existsSync(candidate)) {
      continue;
    }
    try {
      return require(candidate);
    } catch {
      // Keep looking.
    }
  }

  throw new Error("Playwright package not found; install playwright or set LOOPX_PLAYWRIGHT_PACKAGE");
}

async function launchBrowser(chromium) {
  try {
    return await chromium.launch({ channel: "chrome", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

async function waitForDashboard(url) {
  const deadline = Date.now() + 20_000;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveTimeout) => setTimeout(resolveTimeout, 250));
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
}

function startDashboardServer() {
  const viteBin = resolve(dashboardDir, "node_modules/vite/bin/vite.js");
  if (!existsSync(viteBin)) {
    throw new Error(`Vite package not installed: ${viteBin}`);
  }
  const nodeBin = [
    process.env.LOOPX_NODE_BIN,
    "/opt/homebrew/bin/node",
    "/usr/local/bin/node",
    process.execPath,
  ].find((candidate) => candidate && existsSync(candidate));
  return spawn(nodeBin, [viteBin, "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
    cwd: dashboardDir,
    env: {
      ...process.env,
      PATH: ["/opt/homebrew/bin", "/usr/local/bin", process.env.PATH].filter(Boolean).join(":"),
    },
    stdio: "ignore",
  });
}

function formatOverflowOffender(offender) {
  const id = offender.testid ? `[data-testid="${offender.testid}"]` : offender.tag;
  return `${id} left=${offender.left} right=${offender.right} width=${offender.width} "${offender.text}"`;
}

async function assertNoHorizontalOverflow(page, label) {
  const report = await page.evaluate(() => {
    const viewportWidth = window.innerWidth;
    const root = document.documentElement;
    const body = document.body;
    const scrollWidth = Math.max(root.scrollWidth, body?.scrollWidth ?? 0);
    const offenders = [];
    for (const element of Array.from(document.body.querySelectorAll("*"))) {
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
        continue;
      }
      const rect = element.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) {
        continue;
      }
      if (rect.left < -2 || rect.right > viewportWidth + 2) {
        offenders.push({
          tag: element.tagName.toLowerCase(),
          testid: element.getAttribute("data-testid"),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          text: (element.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 90),
        });
      }
      if (offenders.length >= 8) {
        break;
      }
    }
    return {
      viewportWidth,
      scrollWidth,
      overflowPx: Math.max(0, scrollWidth - viewportWidth),
      offenders,
    };
  });
  if (report.overflowPx > 2) {
    const offenders = report.offenders.map(formatOverflowOffender).join(" | ");
    throw new Error(`${label} horizontal overflow: viewport=${report.viewportWidth} scroll=${report.scrollWidth} offenders=${offenders || "none"}`);
  }
}

async function captureFrontstage(page, url, label, requiredText = [], options = {}) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector(options.rootSelector ?? '[data-testid="goal-channel-frontstage-route"]', { timeout: 10_000 });

  const body = await page.locator("body").innerText();
  const frontstageRequired = [
    "LoopX",
    "Efficiency Evidence",
    "AI-ASSISTED BASELINE",
    "SINGLE-ENGINEER COMPRESSION",
    "maturity-adjusted",
    "PUBLIC GIT FACTS",
    "Async Work Loop",
    "Case-driven motion board",
    "Case source",
    "docs/showcases/showcase-catalog.json",
    "multiple worker lanes converging through one shared control plane",
    "Showcase Cases",
    "Public-safe case pack",
    "Blocked P0 with safe P1/P2 rotation",
    "LoopX self-iteration loop",
    "Dynamic workflow for hardware-agent development",
  ];
  const required = options.includeFrontstageRequired === false
    ? requiredText
    : [...frontstageRequired, ...requiredText];
  const missing = required.filter((text) => !body.includes(text));
  if (missing.length) {
    throw new Error(`Missing frontstage text: ${missing.join(", ")}`);
  }

  const forbidden = [
    "[plugin:vite:oxc]",
    "Transform failed",
    "onclick=",
    "method=",
  ];
  const present = forbidden.filter((text) => body.includes(text));
  if (present.length) {
    throw new Error(`Frontstage leaked debug/write text: ${present.join(", ")}`);
  }

  const forms = await page.locator("form").count();
  if (forms !== 0) {
    throw new Error(`Read-only frontstage should not render forms; found ${forms}`);
  }

  await assertNoHorizontalOverflow(page, label);
  await page.screenshot({
    path: resolve(visualOutputDir, `${label}.png`),
    fullPage: true,
    animations: "disabled",
  });
}

async function captureDeveloperFrontstage(page, url, label) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="goal-channel-frontstage-route"]', { timeout: 10_000 });
  await page.waitForSelector('[data-testid="frontstage-developer-onboarding"]', { timeout: 10_000 });

  const body = await page.locator("body").innerText();
  const required = [
    "Developer Onboarding Frontstage",
    "Start the loop from one TUI message",
    "developer mode",
    "Developer mode ignores statusUrl",
    "Developer Onboarding",
    "Open the project and send one LoopX bootstrap message in Codex CLI.",
    "workspace_guard blocks side-agent edits",
    "quota/status agree on user todos",
    "TUI steering stays visible",
    "Public Boundary",
    "None in browser",
  ];
  const missing = required.filter((text) => !body.includes(text));
  if (missing.length) {
    throw new Error(`Missing developer frontstage text: ${missing.join(", ")}`);
  }

  const forbidden = [
    "Live Goal Channel",
    "Second Live Channel",
    "Render live statusUrl channel projection",
    "FAKE_PRIVATE_STATUS_ALPHA",
    "FAKE_INTERNAL_TABLE_BETA",
    "FAKE_PRIVATE_TODO_GAMMA",
    "FAKE_PRIVATE_EVENT_DELTA",
    "[plugin:vite:oxc]",
    "Transform failed",
  ];
  const present = forbidden.filter((text) => body.includes(text));
  if (present.length) {
    throw new Error(`Developer frontstage loaded live/debug text: ${present.join(", ")}`);
  }

  const forms = await page.locator("form").count();
  if (forms !== 0) {
    throw new Error(`Read-only developer frontstage should not render forms; found ${forms}`);
  }

  await assertNoHorizontalOverflow(page, label);
  await page.screenshot({
    path: resolve(visualOutputDir, `${label}.png`),
    fullPage: true,
    animations: "disabled",
  });
}

async function main() {
  const { chromium } = loadPlaywright();
  await writeFile(fixturePath, JSON.stringify(statusFixture, null, 2) + "\n", "utf-8");
  await writeFile(privateTrapFixturePath, await readFile(privateTrapSourcePath, "utf8"), "utf-8");
  await mkdir(visualOutputDir, { recursive: true });

  const server = startDashboardServer();
  let browser;
  const pageErrors = [];
  try {
    const baseUrl = `http://127.0.0.1:${port}`;
    await waitForDashboard(baseUrl);
    browser = await launchBrowser(chromium);

    const desktopPage = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    desktopPage.on("pageerror", (error) => pageErrors.push(error.message));
    try {
      await captureFrontstage(desktopPage, `${baseUrl}/frontstage`, "desktop-frontstage", [
        "Loop engineering for long-running AI agents",
        "Public cases first. Live registry state stays behind explicit ops mode.",
        "Explore cases",
        "Quick Start",
        "Share feedback",
        "public cases",
        "story beats",
        "showcase mode",
        "Showcase mode ignores statusUrl",
        "STATE FLOW CONTROL PLANE",
        "Work keeps moving. Judgment stays in charge.",
        "safe work moves",
        "Self-Iteration Timeline",
        "Three-lane control-plane story",
        "Primary control",
        "Product capability",
        "Implementation lane",
        "human gate: decision_frontstage_to_implementation_lane",
        "INFERRED DISPLAY BRIDGE",
        "Truth source: event ledger",
        "ASYNCHRONOUS AGENT RHYTHM",
        "Agent teams work across turns and off-hours",
        "SEARCH PUBLIC SHOWCASES",
        "Showing 3 of 3 public-safe cases",
        "Public Boundary",
        "Ops live only",
        "None in browser",
      ]);
      const publicShellSidebars = await desktopPage
        .locator('[data-testid="frontstage-live-source-panel"], [data-testid="frontstage-source-warnings"]')
        .count();
      if (publicShellSidebars !== 0) {
        throw new Error(`Showcase homepage rendered ops side panels: ${publicShellSidebars}`);
      }
      const stateFlowTrackCount = await desktopPage.locator('[data-testid="frontstage-state-flow-track"]').count();
      const stateFlowBeamBox = await desktopPage.locator('[data-testid="frontstage-state-flow-beam"]').boundingBox();
      if (stateFlowTrackCount !== 1 || !stateFlowBeamBox || stateFlowBeamBox.width < 20) {
        throw new Error("Showcase state-flow animation rail did not render");
      }
      const selfIterationLaneCount = await desktopPage
        .locator('[data-testid="frontstage-self-iteration-lane"]')
        .count();
      if (selfIterationLaneCount !== 3) {
        throw new Error(`Self-iteration timeline should render three lanes; saw ${selfIterationLaneCount}`);
      }
      const selfIterationEventCount = await desktopPage
        .locator('[data-testid="frontstage-self-iteration-event"]')
        .count();
      if (selfIterationEventCount < 6) {
        throw new Error(`Self-iteration timeline should render at least six events; saw ${selfIterationEventCount}`);
      }
      const selfIterationBridgeCount = await desktopPage
        .locator('[data-testid="frontstage-self-iteration-dashed-bridge"]')
        .count();
      if (selfIterationBridgeCount < 1) {
        throw new Error("Self-iteration timeline did not render the inferred dashed bridge");
      }
      const showcaseMotionBeamBox = await desktopPage
        .locator('[data-testid="frontstage-showcase-motion-beam"]')
        .boundingBox();
      if (!showcaseMotionBeamBox || showcaseMotionBeamBox.width < 20) {
        throw new Error("Showcase motion traffic beam did not render");
      }
      const spotlight = desktopPage.locator('[data-testid="frontstage-showcase-spotlight"]');
      const initialSpotlightText = await spotlight.innerText();
      if (!initialSpotlightText.includes("Blocked P0 with safe P1/P2 rotation")) {
        throw new Error("Showcase spotlight did not default to the first public case");
      }
      await desktopPage
        .locator('[data-testid="frontstage-showcase-motion-card"]')
        .filter({ hasText: "Dynamic workflow for hardware-agent development" })
        .click();
      await desktopPage.waitForFunction(() =>
        document
          .querySelector('[data-testid="frontstage-showcase-spotlight"]')
          ?.textContent?.includes("Dynamic workflow for hardware-agent development"),
      );
      const hardwareSpotlightText = await spotlight.innerText();
      if (!hardwareSpotlightText.includes("Public-safe interactive artifact")) {
        throw new Error("Showcase spotlight did not expose the selected hardware-agent evidence boundary");
      }
      const spotlightCaseHref = await desktopPage
        .locator('[data-testid="frontstage-showcase-spotlight-case-page"]')
        .getAttribute("href");
      if (!spotlightCaseHref?.includes("huangruiteng.github.io/loopx/docs/showcases/")) {
        throw new Error(`Showcase spotlight case link points outside public showcases: ${spotlightCaseHref}`);
      }
      await desktopPage.locator('[data-testid="frontstage-showcase-search"]').fill("self-iteration");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("Showing 1 of 3 public-safe cases"));
      const filteredCaseText = await desktopPage.locator('[data-testid="frontstage-showcase-cases"]').innerText();
      if (!filteredCaseText.includes("LoopX self-iteration loop")) {
        throw new Error("Showcase search did not keep the self-iteration case visible");
      }
      if (filteredCaseText.includes("Blocked P0 with safe P1/P2 rotation")) {
        throw new Error("Showcase search did not filter unrelated cases");
      }
      await desktopPage.locator('[data-testid="frontstage-showcase-search"]').fill("no-matching-showcase");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("No public showcase matched the current filters."));
      await desktopPage.locator('[data-testid="frontstage-showcase-search"]').fill("");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("Showing 3 of 3 public-safe cases"));
      await captureFrontstage(
        desktopPage,
        `${baseUrl}/frontstage?statusUrl=/${fixtureName}&goalId=live-goal-a`,
        "desktop-frontstage-showcase-ignores-status-url",
        [
          "Loop engineering for long-running AI agents",
          "showcase mode",
          "Showcase mode ignores statusUrl",
          "statusUrl ignored",
          "Public Boundary",
          "Ops live only",
        ],
      );
      const publicModeText = await desktopPage.locator("body").innerText();
      const publicModeForbidden = [
        "Live Goal Channel",
        "Second Live Channel",
        "Render live statusUrl channel projection",
        "FAKE_PRIVATE_STATUS_ALPHA",
        "FAKE_INTERNAL_TABLE_BETA",
        "FAKE_PRIVATE_TODO_GAMMA",
        "FAKE_PRIVATE_EVENT_DELTA",
      ];
      const publicModePresent = publicModeForbidden.filter((text) => publicModeText.includes(text));
      if (publicModePresent.length) {
        throw new Error(`Showcase frontstage loaded live statusUrl text: ${publicModePresent.join(", ")}`);
      }
      await captureDeveloperFrontstage(
        desktopPage,
        `${baseUrl}/frontstage?mode=developer&statusUrl=/${fixtureName}&goalId=live-goal-a`,
        "desktop-frontstage-developer",
      );
      await captureFrontstage(
        desktopPage,
        `${baseUrl}/frontstage?statusUrl=/${privateTrapFixtureName}&goalId=fake-private-trap-goal`,
        "desktop-frontstage-showcase-private-trap-ignored",
        [
          "Loop engineering for long-running AI agents",
          "showcase mode",
          "Showcase mode ignores statusUrl",
          "statusUrl ignored",
          "Public Boundary",
          "docs/showcases",
        ],
      );
      const privateTrapPublicText = await desktopPage.locator("body").innerText();
      const leakedTrapMarkers = fakePrivateTrapMarkers.filter((text) => privateTrapPublicText.includes(text));
      if (leakedTrapMarkers.length) {
        throw new Error(`Showcase mode rendered fake-private status trap markers: ${leakedTrapMarkers.join(", ")}`);
      }
      await captureFrontstage(
        desktopPage,
        `${baseUrl}/frontstage?mode=ops&statusUrl=/${privateTrapFixtureName}&goalId=fake-private-trap-goal`,
        "desktop-frontstage-ops-private-trap-explicit",
        [
          "ops live",
          "live status feed",
          "Fake Private Trap Goal",
          "GH_FAKE_PRIVATE_PLAN_SUMMARY_ALPHA",
          "GH_FAKE_PRIVATE_TODO_GAMMA",
          "GH_FAKE_PRIVATE_EVENT_DELTA",
        ],
      );
      const privateTrapOpsText = await desktopPage.locator("body").innerText();
      for (const marker of [
        "GH_FAKE_PRIVATE_PLAN_SUMMARY_ALPHA",
        "GH_FAKE_PRIVATE_TODO_GAMMA",
        "GH_FAKE_PRIVATE_EVENT_DELTA",
      ]) {
        if (!privateTrapOpsText.includes(marker)) {
          throw new Error(`Explicit ops mode did not render fake-private status trap marker: ${marker}`);
        }
      }
      await captureFrontstage(
        desktopPage,
        `${baseUrl}/frontstage/developer`,
        "desktop-frontstage-developer-cockpit",
        [
          "LoopX Projection Developer Cockpit",
          "Status Contract Explorer",
          "Projection Diffing",
          "Fixture Generation",
          "Smoke Checklist",
          "Component Examples",
          "Extension Boundary",
          "apps/dashboard/src/data/status.ts",
          "apps/dashboard/src/data/goal-channel-frontstage.ts",
          "examples/status.example.json",
          "loopx check --scan-path apps/dashboard",
          "read-only contributor workbench",
          "live status feeds, registry files, and browser write APIs stay outside",
        ],
        {
          includeFrontstageRequired: false,
          rootSelector: '[data-testid="frontstage-developer-cockpit"]',
        },
      );
      await captureFrontstage(
        desktopPage,
        `${baseUrl}/frontstage?mode=ops&statusUrl=/${fixtureName}&goalId=live-goal-a`,
        "desktop-frontstage-live",
        [
          "ops live",
          "live status feed",
          "TanStack Query",
          "read-only default",
          "local_dashboard_api: serve-status",
          "reward dry-run advertised; append disabled",
          "control-plane dry-run advertised; apply disabled",
          "Write affordances require explicit loopback opt-in",
          "Ops statusUrl accepts only relative or loopback sources.",
          "Live Goal Channel",
          "goal_channel_projection_v0",
          "Always-on agent operations",
          "Render live statusUrl channel projection",
          "Decision Frame",
          "Quota Guard",
          "Source Freshness",
          "User Todo Lane",
          "Agent Todo Lane",
          "Run Timeline",
          "Role Map",
          "Active Claims",
          "Open Gates",
          "Artifacts",
          "Truth Contract",
          "CLAIMED LANES",
          "EVIDENCE LOOP",
          "SEARCH TODO PROJECTION",
          "Showing 4 of 4 projected todos",
          "Review live handoff gate before delivery",
          "Document filtered ops route",
          "live-goal-a_gate",
          "browser smoke statusUrl",
          "browser_smoke_public_fixture",
        ],
      );
      await desktopPage.locator('[data-testid="frontstage-todo-search"]').fill("filtered ops");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("Showing 1 of 4 projected todos"));
      const filteredTodoText = await desktopPage.locator('[data-testid="frontstage-agent-todos"]').innerText();
      if (!filteredTodoText.includes("Document filtered ops route")) {
        throw new Error("Todo search did not keep the matching agent todo visible");
      }
      const filteredUserTodoText = await desktopPage.locator('[data-testid="frontstage-user-todos"]').innerText();
      if (!filteredUserTodoText.includes("No user todos match the current filters.")) {
        throw new Error("Todo search did not show the user-lane empty state");
      }
      const filteredTodoUrl = new URL(desktopPage.url());
      if (filteredTodoUrl.searchParams.get("todoQuery") !== "filtered ops") {
        throw new Error(`Todo search did not update URL: ${desktopPage.url()}`);
      }
      await desktopPage.locator('[data-testid="frontstage-todo-search"]').fill("");
      await desktopPage.locator('[data-testid="frontstage-todo-lane-filter"]').selectOption("user");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("Showing 2 of 4 projected todos"));
      const userLaneText = await desktopPage.locator('[data-testid="frontstage-user-todos"]').innerText();
      const agentLaneText = await desktopPage.locator('[data-testid="frontstage-agent-todos"]').innerText();
      if (!userLaneText.includes("Review live handoff gate before delivery")) {
        throw new Error("User lane filter did not keep user todos visible");
      }
      if (!agentLaneText.includes("No agent todos match the current filters.")) {
        throw new Error("User lane filter did not hide agent todos");
      }
      const filteredLaneUrl = new URL(desktopPage.url());
      if (filteredLaneUrl.searchParams.get("todoLane") !== "user") {
        throw new Error(`Todo lane filter did not update URL: ${desktopPage.url()}`);
      }
      await desktopPage.locator('[data-testid="frontstage-goal-select"]').selectOption("live-goal-b");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("Second Live Channel"));
      const selectedUrl = new URL(desktopPage.url());
      if (selectedUrl.searchParams.get("goalId") !== "live-goal-b") {
        throw new Error(`Goal selector did not update URL: ${desktopPage.url()}`);
      }
      await desktopPage.locator('[data-testid="frontstage-status-url-input"]').fill("https://example.com/status.json");
      await desktopPage.locator('[data-testid="frontstage-load-status-url"]').click();
      const loadErrorText = await desktopPage.locator('[data-testid="frontstage-load-error"]').innerText();
      if (!loadErrorText.includes("Ops statusUrl must be relative or loopback")) {
        throw new Error(`External ops statusUrl was not rejected locally: ${loadErrorText}`);
      }
      await desktopPage.locator('[data-testid="frontstage-reset-demo"]').click();
      await captureFrontstage(desktopPage, `${baseUrl}/frontstage`, "desktop-frontstage-after-ops-reset", [
        "Loop engineering for long-running AI agents",
        "showcase mode",
        "Showcase mode ignores statusUrl",
        "Public Boundary",
      ]);
      const resetText = await desktopPage.locator("body").innerText();
      const resetForbidden = [
        "Live Goal Channel",
        "Second Live Channel",
        "Render live statusUrl channel projection",
        "FAKE_PRIVATE_STATUS_ALPHA",
        "FAKE_INTERNAL_TABLE_BETA",
        "FAKE_PRIVATE_TODO_GAMMA",
        "FAKE_PRIVATE_EVENT_DELTA",
      ];
      const resetPresent = resetForbidden.filter((text) => resetText.includes(text));
      if (resetPresent.length) {
        throw new Error(`Showcase frontstage retained prior ops live text: ${resetPresent.join(", ")}`);
      }
    } finally {
      await desktopPage.close();
    }

    const mobilePage = await browser.newPage({
      isMobile: true,
      viewport: { width: 390, height: 900 },
    });
    mobilePage.on("pageerror", (error) => pageErrors.push(`mobile: ${error.message}`));
    try {
      await captureFrontstage(mobilePage, `${baseUrl}/frontstage`, "mobile-frontstage", [
        "Loop engineering for long-running AI agents",
        "Public cases first. Live registry state stays behind explicit ops mode.",
        "showcase mode",
        "Showcase mode ignores statusUrl",
        "Public Boundary",
        "Ops live only",
      ]);
      await captureDeveloperFrontstage(
        mobilePage,
        `${baseUrl}/frontstage?mode=developer&statusUrl=/${fixtureName}`,
        "mobile-frontstage-developer",
      );
    } finally {
      await mobilePage.close();
    }

    if (pageErrors.length) {
      throw new Error(`Frontstage page errors: ${pageErrors.join(" | ")}`);
    }

    console.log("dashboard-frontstage-browser-smoke ok");
  } finally {
    if (browser) {
      await browser.close();
    }
    server.kill("SIGTERM");
    await rm(fixturePath, { force: true });
    await rm(privateTrapFixturePath, { force: true });
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
