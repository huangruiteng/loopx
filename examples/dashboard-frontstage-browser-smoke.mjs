#!/usr/bin/env node
// Browser-level smoke for the read-only goal channel frontstage route.

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/dashboard");
const fixtureName = "status.frontstage.browser-smoke.json";
const fixturePath = resolve(dashboardDir, "public", fixtureName);
const visualOutputDir = resolve(repoRoot, "output/playwright/dashboard-frontstage-visual-acceptance");
const port = Number(process.env.GOAL_HARNESS_DASHBOARD_FRONTSTAGE_SMOKE_PORT ?? "5197");

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
    user_todos: [],
    agent_todos: [
      {
        todo_id: `${goalId}_todo`,
        priority: "P1",
        status: "open",
        claimed_by: claimedBy,
        task_class: "advancement_task",
        title: `${todoTitle} FAKE_PRIVATE_TODO_GAMMA`,
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
    producer: "goal-harness status",
    reload_hint: "scripts/macos-dashboard-launchagent.sh restart",
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
    process.env.GOAL_HARNESS_PLAYWRIGHT_PACKAGE,
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

  throw new Error("Playwright package not found; install playwright or set GOAL_HARNESS_PLAYWRIGHT_PACKAGE");
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
    process.env.GOAL_HARNESS_NODE_BIN,
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

async function captureFrontstage(page, url, label, requiredText = []) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="goal-channel-frontstage-route"]', { timeout: 10_000 });

  const body = await page.locator("body").innerText();
  const required = [
    "Goal Harness",
    "Frontstage channel",
    "Projection is read-only",
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
    "Goal Harness self-iteration loop",
    "Creator-operator long-running agent case",
    "Boundary Warnings",
    ...requiredText,
  ];
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

async function main() {
  const { chromium } = loadPlaywright();
  await writeFile(fixturePath, JSON.stringify(statusFixture, null, 2) + "\n", "utf-8");
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
        "Goal Harness Showcase Frontstage",
        "Async agent teams, governed by human judgment",
        "public cases",
        "story beats",
        "showcase mode",
        "Showcase mode ignores statusUrl",
        "STATE FLOW CONTROL PLANE",
        "Work keeps moving. Judgment stays in charge.",
        "safe work moves",
        "ASYNCHRONOUS AGENT RHYTHM",
        "Agent teams work across turns and off-hours",
        "SEARCH PUBLIC SHOWCASES",
        "Showing 4 of 4 public-safe cases",
        "Public Boundary",
        "Ops live only",
        "None in browser",
      ]);
      const stateFlowTrackCount = await desktopPage.locator('[data-testid="frontstage-state-flow-track"]').count();
      const stateFlowBeamBox = await desktopPage.locator('[data-testid="frontstage-state-flow-beam"]').boundingBox();
      if (stateFlowTrackCount !== 1 || !stateFlowBeamBox || stateFlowBeamBox.width < 20) {
        throw new Error("Showcase state-flow animation rail did not render");
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
        .filter({ hasText: "Creator-operator long-running agent case" })
        .click();
      await desktopPage.waitForFunction(() =>
        document
          .querySelector('[data-testid="frontstage-showcase-spotlight"]')
          ?.textContent?.includes("Creator-operator long-running agent case"),
      );
      const creatorSpotlightText = await spotlight.innerText();
      if (!creatorSpotlightText.includes("Synthetic case spec only")) {
        throw new Error("Showcase spotlight did not expose the selected case evidence boundary");
      }
      const spotlightCaseHref = await desktopPage
        .locator('[data-testid="frontstage-showcase-spotlight-case-page"]')
        .getAttribute("href");
      if (!spotlightCaseHref?.includes("github.com/huangruiteng/goal-harness/blob/main/docs/showcases/")) {
        throw new Error(`Showcase spotlight case link points outside public showcases: ${spotlightCaseHref}`);
      }
      await desktopPage.locator('[data-testid="frontstage-showcase-search"]').fill("self-iteration");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("Showing 1 of 4 public-safe cases"));
      const filteredCaseText = await desktopPage.locator('[data-testid="frontstage-showcase-cases"]').innerText();
      if (!filteredCaseText.includes("Goal Harness self-iteration loop")) {
        throw new Error("Showcase search did not keep the self-iteration case visible");
      }
      if (filteredCaseText.includes("Blocked P0 with safe P1/P2 rotation")) {
        throw new Error("Showcase search did not filter unrelated cases");
      }
      await desktopPage.locator('[data-testid="frontstage-showcase-search"]').fill("no-matching-showcase");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("No public showcase matched the current filters."));
      await desktopPage.locator('[data-testid="frontstage-showcase-search"]').fill("");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("Showing 4 of 4 public-safe cases"));
      await captureFrontstage(
        desktopPage,
        `${baseUrl}/frontstage?statusUrl=/${fixtureName}&goalId=live-goal-a`,
        "desktop-frontstage-showcase-ignores-status-url",
        [
          "Goal Harness Showcase Frontstage",
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
      await captureFrontstage(
        desktopPage,
        `${baseUrl}/frontstage?mode=ops&statusUrl=/${fixtureName}&goalId=live-goal-a`,
        "desktop-frontstage-live",
        [
          "ops live",
          "live status feed",
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
          "live-goal-a_gate",
          "browser smoke statusUrl",
          "browser_smoke_public_fixture",
        ],
      );
      await desktopPage.locator('[data-testid="frontstage-goal-select"]').selectOption("live-goal-b");
      await desktopPage.waitForFunction(() => document.body.innerText.includes("Second Live Channel"));
      const selectedUrl = new URL(desktopPage.url());
      if (selectedUrl.searchParams.get("goalId") !== "live-goal-b") {
        throw new Error(`Goal selector did not update URL: ${desktopPage.url()}`);
      }
      await captureFrontstage(desktopPage, `${baseUrl}/frontstage`, "desktop-frontstage-after-ops-reset", [
        "Goal Harness Showcase Frontstage",
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
        "Goal Harness Showcase Frontstage",
        "Async agent teams, governed by human judgment",
        "showcase mode",
        "Showcase mode ignores statusUrl",
        "Public Boundary",
        "Ops live only",
      ]);
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
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
