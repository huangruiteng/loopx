// @ts-expect-error The smoke compiler intentionally runs without @types/node.
import { readFileSync } from "node:fs";

function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

function includes(source: string, snippet: string, label: string) {
  assert(source.includes(snippet), `missing ${label}: ${snippet}`);
}

function excludes(source: string, snippet: string, label: string) {
  assert(!source.includes(snippet), `unexpected ${label}: ${snippet}`);
}

const routerSource = readFileSync("src/router.tsx", "utf8");
const frontstageSource = readFileSync("src/views/frontstage-page.tsx", "utf8");
const dataSource = readFileSync("src/data/goal-channel-frontstage.ts", "utf8");
const readmeSource = readFileSync("README.md", "utf8");
const selectionSource = readFileSync("../../docs/dashboard-frontend-selection.md", "utf8");
const packageSource = readFileSync("package.json", "utf8");

includes(routerSource, 'path: "/frontstage"', "frontstage route path");
includes(routerSource, "component: FrontstagePage", "frontstage route component");
includes(packageSource, '"smoke:frontstage-browser"', "frontstage browser smoke script");
includes(packageSource, '"smoke:frontstage-route"', "frontstage smoke script");

includes(dataSource, 'schema_version: "goal_channel_projection_v0"', "goal channel schema");
includes(dataSource, 'mode: "read_only"', "read-only mode");
includes(dataSource, 'claimed_by: "codex-side-bypass"', "side-agent claim fixture");
includes(dataSource, "raw_or_private_material_omitted", "source warning fixture");

includes(frontstageSource, 'data-testid="goal-channel-frontstage-route"', "route test id");
includes(frontstageSource, 'data-testid="frontstage-user-todos"', "user todo lane");
includes(frontstageSource, 'data-testid="frontstage-agent-todos"', "agent todo lane");
includes(frontstageSource, 'data-testid="frontstage-active-claims"', "active claims lane");
includes(frontstageSource, 'data-testid="frontstage-timeline"', "timeline lane");
includes(frontstageSource, "Frontstage channel", "frontstage channel copy");
includes(frontstageSource, "Channel board", "channel board nav");
includes(frontstageSource, "Projection is read-only", "read-only truth copy");
includes(frontstageSource, "Inspired by modern agent boards", "product benchmark copy");
excludes(frontstageSource, "<form", "write form");
excludes(frontstageSource, "method=", "form method");
excludes(frontstageSource, "onclick=", "inline click handler");

includes(readmeSource, "/frontstage", "README frontstage route mention");
includes(selectionSource, "Multica", "Multica benchmark note");
includes(selectionSource, "agent board", "agent board benchmark note");

console.log("frontstage-route smoke ok");
