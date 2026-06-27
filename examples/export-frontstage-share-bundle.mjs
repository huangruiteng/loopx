#!/usr/bin/env node
// Build a public-safe static frontstage bundle for demos and future Pages hosting.

import { spawnSync } from "node:child_process";
import { copyFile, mkdir, readdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardDir = resolve(repoRoot, "apps/dashboard");
const defaultOutDir = resolve("/tmp", "loopx-frontstage-share-bundle");
const statusFileName = "status.frontstage-share.json";
const manifestFileName = "frontstage-share-manifest.json";
const showcaseCatalogPath = "docs/showcases/showcase-catalog.json";
const projectionFixturePath = "examples/goal-channel-frontstage-fixture.py";

function parseArgs(argv) {
  const args = {
    base: "/",
    outDir: defaultOutDir,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--base") {
      args.base = argv[++index];
    } else if (token === "--out-dir") {
      args.outDir = resolve(argv[++index]);
    } else if (token === "--help" || token === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${token}`);
    }
  }
  if (!args.base.startsWith("/")) {
    throw new Error("--base must be an absolute browser path such as / or /loopx/");
  }
  if (!args.base.endsWith("/")) {
    args.base = `${args.base}/`;
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node examples/export-frontstage-share-bundle.mjs [--out-dir DIR] [--base /path/]

Builds apps/dashboard into a public-safe static bundle, writes a sanitized
goal_channel_projection_v0 status fixture, and creates /frontstage/index.html
for direct static hosting.

Defaults:
  --out-dir ${defaultOutDir}
  --base /
`);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? repoRoot,
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: ["/opt/homebrew/bin", "/usr/local/bin", process.env.PATH].filter(Boolean).join(":"),
    },
    stdio: options.capture ? ["ignore", "pipe", "pipe"] : "inherit",
  });
  if (result.status !== 0) {
    const detail = options.capture ? `${result.stderr}\n${result.stdout}`.trim() : "";
    throw new Error(`Command failed: ${command} ${args.join(" ")}${detail ? `\n${detail}` : ""}`);
  }
  return result.stdout ?? "";
}

async function copyIndexForFrontstage(siteDir) {
  const indexPath = resolve(siteDir, "index.html");
  const frontstageDir = resolve(siteDir, "frontstage");
  await mkdir(frontstageDir, { recursive: true });
  const html = await readFile(indexPath, "utf8");
  await writeFile(resolve(frontstageDir, "index.html"), html);
}

function validateInteractivePagePath(path) {
  if (typeof path !== "string") {
    throw new Error(`interactive_page must be a string: ${JSON.stringify(path)}`);
  }
  if (!path.startsWith("docs/showcases/") || !path.endsWith(".html") || path.includes("..")) {
    throw new Error(`interactive_page must stay under docs/showcases/*.html: ${path}`);
  }
  return path;
}

async function copyInteractiveCasePages(siteDir) {
  const catalog = JSON.parse(await readFile(resolve(repoRoot, showcaseCatalogPath), "utf8"));
  const interactivePages = new Set();
  for (const item of catalog.cases ?? []) {
    if (item.interactive_page) {
      interactivePages.add(validateInteractivePagePath(item.interactive_page));
    }
  }

  for (const pagePath of interactivePages) {
    const sourcePath = resolve(repoRoot, pagePath);
    const targetPath = resolve(siteDir, pagePath);
    await mkdir(dirname(targetPath), { recursive: true });
    await copyFile(sourcePath, targetPath);
  }
  return Array.from(interactivePages).sort();
}

async function removeCopiedLiveStatusFiles(siteDir) {
  for (const entry of await readdir(siteDir, { withFileTypes: true })) {
    if (!entry.isFile()) {
      continue;
    }
    if (/^status\..*\.json$/i.test(entry.name) && entry.name !== statusFileName) {
      await rm(resolve(siteDir, entry.name), { force: true });
    }
  }
}

function sanitizeProjectionForShare(projection) {
  return {
    ...projection,
    source_warnings: (projection.source_warnings ?? []).map((warning) => ({
      kind: warning.kind ?? "raw_or_private_material_omitted",
      message: warning.message ?? "raw/private-looking fields were omitted from this public demo projection",
    })),
  };
}

function buildStatusFixture(projection) {
  return {
    ok: true,
    registry: "public-safe fixture",
    runtime_root: "omitted",
    goal_count: 1,
    run_count: projection.recent_events.length,
    generated_at: "2026-06-20T13:30:00Z",
    status_contract: {
      schema_version: 2,
      minimum_dashboard_schema_version: 2,
      producer: "examples/export-frontstage-share-bundle.mjs",
      reload_hint: "rebuild this bundle from the public fixture",
    },
    contract: {
      ok: true,
      summary: { checks: 2, errors: 0, warnings: 0 },
      checks: [
        "public-safe goal_channel_projection_v0 fixture",
        "static frontstage route exported for direct hosting",
      ],
      errors: [],
      warnings: [],
    },
    attention_queue: {
      available: true,
      item_count: 1,
      needs_user_or_controller: projection.decision_frame.user_action_required ? 1 : 0,
      needs_controller: 0,
      needs_codex: projection.decision_frame.agent_action_required ? 1 : 0,
      watching_external_evidence: 0,
      items: [
        {
          goal_id: projection.goal_id,
          status: projection.latest_status,
          waiting_on: projection.waiting_on,
          severity: projection.decision_frame.user_action_required ? "action" : "watch",
          recommended_action: projection.next_action,
          source: "frontstage-share-bundle-fixture",
          goal_channel_projection: projection,
        },
      ],
    },
  };
}

async function writeShareReadme(outDir, base, interactivePages) {
  const siteDir = resolve(outDir, "site");
  const frontstageUrl = `${base}frontstage/`;
  const previewBlock = base === "/"
    ? `## Try It Locally

\`\`\`bash
cd ${relative(process.cwd(), siteDir) || "."}
python3 -m http.server 8080
\`\`\`

Then open:

\`\`\`text
http://127.0.0.1:8080${frontstageUrl}
\`\`\`
`
    : `## Try It Locally

This bundle was built for the non-root browser base \`${base}\`. Upload
\`site/\` to a host that serves it at that base path. For a quick local preview,
rerun the exporter without \`--base\` and open the generated root-base URL.

Hosted entry:

\`\`\`text
${frontstageUrl}
\`\`\`
`;
  const readme = `# LoopX Frontstage Share Bundle

This directory is a generated, public-safe static bundle. It contains the
dashboard build plus a sanitized \`goal_channel_projection_v0\` status fixture.
The public entry opens frontstage showcase mode and does not load \`statusUrl\`
by default.

Primary public story content is rendered from \`${showcaseCatalogPath}\`. The
status fixture only gives the frontstage a read-only control-plane shell for
demo navigation; live local status feeds stay out of this bundle.

${previewBlock}

## Publication Boundary

- Includes: compiled dashboard assets, \`${statusFileName}\`, direct
  \`/frontstage/\` static route support, and catalog-declared interactive
  case pages.
- Primary case source: \`${showcaseCatalogPath}\`.
- Interactive case pages: ${interactivePages.length ? interactivePages.map((path) => `\`${path}\``).join(", ") : "none"}.
- Demo shell fixture: \`${projectionFixturePath} --format json\`.
- Excludes: live registry state, local paths, credentials, raw logs, raw
  benchmark evidence, and write APIs.
`;
  await writeFile(resolve(outDir, "README.md"), readme);
}

async function writeManifest(outDir, base, interactivePages) {
  const manifest = {
    schema_version: "loopx_frontstage_share_bundle_v0",
    base,
    site_dir: "site",
    status_fixture: `site/${statusFileName}`,
    frontstage_entry: "site/frontstage/index.html",
    content_sources: {
      primary_public_story: showcaseCatalogPath,
      interactive_case_pages: interactivePages,
      read_only_control_plane_shell: projectionFixturePath,
      live_status_feed: false,
    },
    public_boundary: {
      primary_content_is_showcase_catalog: true,
      interactive_pages_from_showcase_catalog: true,
      live_registry_state: false,
      write_api: false,
      raw_logs: false,
      local_paths: false,
      credentials: false,
    },
  };
  const text = `${JSON.stringify(manifest, null, 2)}\n`;
  await writeFile(resolve(outDir, manifestFileName), text);
  await writeFile(resolve(outDir, "site", manifestFileName), text);
}

async function collectTextFiles(rootDir) {
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

async function scanPublicBoundary(outDir) {
  const patterns = [
    { label: "macOS user path", pattern: /\/Users\// },
    { label: "private temp path", pattern: /\/private\// },
    { label: "workspace owner name", pattern: new RegExp("byte" + "dance", "i") },
    { label: "internal doc host", pattern: new RegExp("lark" + "office", "i") },
    { label: "private goal state", pattern: new RegExp("\\.codex/goals|\\.goal-" + "harness") },
    { label: "raw internal key", pattern: new RegExp("raw_" + "internal_note") },
    { label: "private key material", pattern: /BEGIN (?:RSA |OPENSSH |EC |)PRIVATE KEY/ },
    { label: "token assignment", pattern: /\b(?:api[_-]?key|auth[_-]?token|access[_-]?token)\s*[:=]/i },
  ];
  const leaks = [];
  for (const path of await collectTextFiles(outDir)) {
    const text = await readFile(path, "utf8");
    for (const { label, pattern } of patterns) {
      if (pattern.test(text)) {
        leaks.push(`${relative(outDir, path)}: ${label}`);
      }
    }
  }
  if (leaks.length) {
    throw new Error(`Public boundary scan failed:\n${leaks.join("\n")}`);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const outDir = args.outDir;
  const siteDir = resolve(outDir, "site");

  if (!existsSync(resolve(dashboardDir, "node_modules"))) {
    throw new Error("apps/dashboard/node_modules is missing; run `npm ci` in apps/dashboard first");
  }

  await rm(outDir, { force: true, recursive: true });
  await mkdir(siteDir, { recursive: true });

  run(process.execPath, [resolve(dashboardDir, "node_modules/typescript/bin/tsc"), "--noEmit"], { cwd: dashboardDir });
  run(process.execPath, [
    resolve(dashboardDir, "node_modules/vite/bin/vite.js"),
    "build",
    "--base",
    args.base,
    "--outDir",
    siteDir,
    "--emptyOutDir",
  ], { cwd: dashboardDir });

  await removeCopiedLiveStatusFiles(siteDir);
  await copyIndexForFrontstage(siteDir);
  const interactivePages = await copyInteractiveCasePages(siteDir);

  const projectionOutput = run("python3", [resolve(repoRoot, "examples/goal-channel-frontstage-fixture.py"), "--format", "json"], {
    capture: true,
    cwd: repoRoot,
  });
  const projection = sanitizeProjectionForShare(JSON.parse(projectionOutput));
  const statusFixture = buildStatusFixture(projection);
  await writeFile(resolve(siteDir, statusFileName), `${JSON.stringify(statusFixture, null, 2)}\n`);
  await writeShareReadme(outDir, args.base, interactivePages);
  await writeManifest(outDir, args.base, interactivePages);
  await scanPublicBoundary(outDir);

  console.log(JSON.stringify({
    ok: true,
    out_dir: outDir,
    site_dir: siteDir,
    frontstage_url: `${args.base}frontstage/`,
    status_fixture: `site/${statusFileName}`,
  }, null, 2));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
