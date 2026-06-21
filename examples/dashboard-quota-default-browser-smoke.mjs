#!/usr/bin/env node
// Browser-level smoke for dashboard quota defaults derived from the status contract.

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/dashboard");
const fixtureName = "status.quota-default.browser-smoke.json";
const fixturePath = resolve(dashboardDir, "public", fixtureName);
const playwrightCliOutputDir = resolve(repoRoot, ".playwright-cli");
const port = Number(process.env.LOOPX_DASHBOARD_QUOTA_DEFAULT_SMOKE_PORT ?? "5193");
const session = `ghqd${process.pid}`;
const pwcli = process.env.PWCLI ?? resolve(homedir(), ".codex/skills/playwright/scripts/playwright_cli.sh");

const goalId = "quota-default-fixture";

const statusFixture = {
  ok: true,
  registry: "./fixtures/registry.json",
  runtime_root: "./fixtures/runtime",
  goal_count: 1,
  run_count: 1,
  contract: {
    ok: true,
    summary: { errors: 0, warnings: 0, checks: 1 },
    errors: [],
    warnings: [],
    checks: ["public-safe quota default dashboard fixture"],
  },
  attention_queue: {
    available: true,
    item_count: 1,
    needs_user_or_controller: 0,
    needs_controller: 0,
    needs_codex: 1,
    watching_external_evidence: 0,
    items: [
      {
        goal_id: goalId,
        status: "state_refreshed",
        waiting_on: "codex",
        severity: "action",
        recommended_action: "continue fixture after quota default check",
        source: "fixture",
        lifecycle_phase: "refreshed",
        lifecycle_flags: ["refreshed"],
        quota: {
          compute: 0.5,
          window_hours: 24,
          slot_minutes: 1,
          spent_slots: 12,
          state: "eligible",
          reason: "0.5 compute quota; eligible for the next automatic agent turn",
        },
      },
    ],
  },
  run_history: {
    available: true,
    goal_count: 1,
    run_count: 1,
    goals: [
      {
        id: goalId,
        domain: "quota-fixture",
        status: "active",
        lifecycle_phase: "refreshed",
        lifecycle_flags: ["refreshed"],
        registry_member: true,
        legacy_runtime_goal: false,
        adapter_kind: "read_only_project_map_v0",
        adapter_status: "connected-read-only",
        quota: {
          compute: 1,
          window_hours: 24,
          spent_slots: 12,
          state: "eligible",
          reason: "1 compute quota; eligible for the next automatic agent turn",
        },
        index_exists: true,
        raw_index_records: 1,
        unique_runs: 1,
        latest_runs: [
          {
            generated_at: "2026-01-01T00:00:00+00:00",
            goal_id: goalId,
            classification: "state_refreshed",
            lifecycle_phase: "refreshed",
            lifecycle_flags: ["refreshed"],
            recommended_action: "continue fixture after quota default check",
            health_check: "fixture 1/1",
          },
        ],
      },
    ],
    recent_runs: [
      {
        generated_at: "2026-01-01T00:00:00+00:00",
        goal_id: goalId,
        classification: "state_refreshed",
        lifecycle_phase: "refreshed",
        lifecycle_flags: ["refreshed"],
        recommended_action: "continue fixture after quota default check",
        health_check: "fixture 1/1",
      },
    ],
  },
};

function runPw(args, { allowFailure = false } = {}) {
  const result = spawnSync("bash", [pwcli, ...args], {
    cwd: repoRoot,
    encoding: "utf-8",
    env: { ...process.env, PLAYWRIGHT_CLI_SESSION: session },
  });
  if (!allowFailure && result.status !== 0) {
    throw new Error([
      `playwright-cli ${args.join(" ")} failed with ${result.status}`,
      result.stdout,
      result.stderr,
    ].filter(Boolean).join("\n"));
  }
  return result;
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

async function removeWithRetry(path) {
  let lastError;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      await rm(path, { recursive: true, force: true });
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolveTimeout) => setTimeout(resolveTimeout, 200));
    }
  }
  throw lastError;
}

async function main() {
  if (!existsSync(pwcli)) {
    throw new Error(`Playwright CLI wrapper not found: ${pwcli}`);
  }

  await writeFile(fixturePath, JSON.stringify(statusFixture, null, 2) + "\n", "utf-8");

  const server = spawn("npm", ["run", "dev", "--", "--port", String(port), "--strictPort"], {
    cwd: dashboardDir,
    env: process.env,
    stdio: "ignore",
  });

  try {
    const baseUrl = `http://127.0.0.1:${port}`;
    await waitForDashboard(baseUrl);
    runPw(["open", `${baseUrl}/?statusUrl=/${fixtureName}&goalId=${goalId}&actionKind=all`]);
    runPw(["resize", "1280", "900"]);
    runPw([
      "run-code",
      String.raw`async (page) => {
        await page.waitForLoadState("networkidle");
        await page.getByText("User Actions").waitFor();
        const body = await page.locator("body").innerText();
        const required = [
          "1 actions",
          "Quota 0.5",
          "Eligible; 12/720 slots",
        ];
        const missing = required.filter((text) => !body.includes(text));
        if (missing.length) {
          throw new Error("Missing dashboard text: " + missing.join(", "));
        }
        const forbidden = [
          "12/24 slots",
          "Quota 1\nEligible; 12/24 slots",
        ];
        const present = forbidden.filter((text) => body.includes(text));
        if (present.length) {
          throw new Error("Dashboard used stale quota defaults: " + present.join(", "));
        }
        return {
          ok: true,
          bodyIncludesDerivedQuota: body.includes("Eligible; 12/720 slots"),
        };
      }`,
    ]);
    console.log("dashboard-quota-default-browser-smoke ok");
  } finally {
    server.kill("SIGTERM");
    await rm(fixturePath, { force: true });
    runPw(["close"], { allowFailure: true });
    await removeWithRetry(playwrightCliOutputDir);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
