#!/usr/bin/env node
// Browser-level smoke for the read-only goal channel frontstage route.

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/dashboard");
const visualOutputDir = resolve(repoRoot, "output/playwright/dashboard-frontstage-visual-acceptance");
const port = Number(process.env.GOAL_HARNESS_DASHBOARD_FRONTSTAGE_SMOKE_PORT ?? "5197");

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

async function captureFrontstage(page, url, label) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="goal-channel-frontstage-route"]', { timeout: 10_000 });

  const body = await page.locator("body").innerText();
  const required = [
    "Goal Harness",
    "Frontstage channel",
    "Demo Goal Channel",
    "goal_channel_projection_v0",
    "Projection is read-only",
    "Decision Frame",
    "Quota Guard",
    "Source Freshness",
    "User Todo Lane",
    "Agent Todo Lane",
    "Run Timeline",
    "Active Claims",
    "Truth Contract",
    "Boundary Warnings",
    "codex-main-control",
    "codex-side-bypass",
    "Render the productization frontstage fixture",
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
      await captureFrontstage(desktopPage, `${baseUrl}/frontstage`, "desktop-frontstage");
    } finally {
      await desktopPage.close();
    }

    const mobilePage = await browser.newPage({
      isMobile: true,
      viewport: { width: 390, height: 900 },
    });
    mobilePage.on("pageerror", (error) => pageErrors.push(`mobile: ${error.message}`));
    try {
      await captureFrontstage(mobilePage, `${baseUrl}/frontstage`, "mobile-frontstage");
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
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
