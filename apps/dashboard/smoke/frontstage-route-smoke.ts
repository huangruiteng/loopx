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

function sourceBetween(source: string, start: string, end: string, label: string) {
  const startIndex = source.indexOf(start);
  const endIndex = source.indexOf(end, startIndex);
  assert(startIndex >= 0 && endIndex > startIndex, `missing ${label} source bounds`);
  return source.slice(startIndex, endIndex);
}

const routerSource = readFileSync("src/router.tsx", "utf8");
const frontstageSource = readFileSync("src/views/frontstage-page.tsx", "utf8");
const stylesSource = readFileSync("src/styles.css", "utf8");
const dataSource = readFileSync("src/data/goal-channel-frontstage.ts", "utf8");
const statusSource = readFileSync("src/data/status.ts", "utf8");
const catalogSource = readFileSync("../../docs/showcases/showcase-catalog.json", "utf8");
const readmeSource = readFileSync("README.md", "utf8");
const selectionSource = readFileSync("../../docs/dashboard-frontend-selection.md", "utf8");
const packageSource = readFileSync("package.json", "utf8");

includes(routerSource, 'path: "/frontstage"', "frontstage route path");
includes(routerSource, "component: FrontstagePage", "frontstage route component");
includes(routerSource, "frontstageSearchSchema", "frontstage search schema");
includes(routerSource, 'mode: z.enum(["showcase", "ops"]).optional().default("showcase")', "frontstage mode gate");
includes(routerSource, "basepath:", "router basepath option");
includes(routerSource, "import.meta.env.BASE_URL", "Vite base URL router source");
includes(packageSource, '"smoke:frontstage-browser"', "frontstage browser smoke script");
includes(packageSource, '"smoke:frontstage-route"', "frontstage smoke script");

includes(dataSource, 'schema_version: "goal_channel_projection_v0"', "goal channel schema");
includes(dataSource, "goalChannelProjectionSchema", "goal channel zod schema");
includes(dataSource, 'mode: "read_only"', "read-only mode");
includes(dataSource, 'claimed_by: "codex-side-bypass"', "side-agent claim fixture");
includes(dataSource, "raw_or_private_material_omitted", "source warning fixture");
includes(statusSource, "goal_channel_projection: goalChannelProjectionSchema", "status projection parser");

includes(frontstageSource, 'data-testid="goal-channel-frontstage-route"', "route test id");
includes(frontstageSource, 'data-testid="frontstage-live-source-panel"', "live source panel");
includes(frontstageSource, 'data-testid="frontstage-public-boundary-note"', "public boundary note");
includes(frontstageSource, "Showcase mode ignores statusUrl", "public mode statusUrl guard copy");
includes(frontstageSource, 'if (!liveMode)', "live status feed requires ops mode");
includes(frontstageSource, 'data-testid="frontstage-operations-strip"', "operations signal strip");
includes(frontstageSource, 'data-testid="frontstage-goal-select"', "goal selector");
includes(frontstageSource, "parseStatusPayload", "status payload parser");
includes(frontstageSource, 'data-testid="frontstage-user-todos"', "user todo lane");
includes(frontstageSource, 'data-testid="frontstage-agent-todos"', "agent todo lane");
includes(frontstageSource, 'data-testid="frontstage-role-map"', "role map lane");
includes(frontstageSource, 'data-testid="frontstage-active-claims"', "active claims lane");
includes(frontstageSource, 'data-testid="frontstage-timeline"', "timeline lane");
includes(frontstageSource, "Frontstage channel", "frontstage channel copy");
includes(frontstageSource, "Channel board", "channel board nav");
includes(frontstageSource, "Always-on agent operations", "always-on operations copy");
includes(frontstageSource, "Goal Harness Showcase Frontstage", "showcase-first hero title");
includes(frontstageSource, "Always-on agent teams, governed by human judgment", "showcase-first hero copy");
includes(frontstageSource, 'data-testid="frontstage-public-showcase-contract"', "public showcase contract panel");
includes(frontstageSource, "Local status URLs stay behind the explicit Ops live switch", "ops-only live status copy");
includes(frontstageSource, "human judgment kept in the control plane", "human judgment control-plane copy");
includes(frontstageSource, "Role Map", "role map copy");
includes(frontstageSource, "claim owners", "claim owner role signal");
includes(frontstageSource, "claimed lanes", "claimed lane signal");
includes(frontstageSource, "evidence loop", "evidence loop signal");
includes(frontstageSource, 'data-testid="frontstage-efficiency-evidence"', "efficiency evidence panel");
includes(frontstageSource, "Efficiency Evidence", "efficiency evidence copy");
includes(frontstageSource, "showcaseCatalog", "showcase catalog import");
includes(frontstageSource, "estimated_developer_days", "efficiency baseline range");
includes(frontstageSource, "single_engineer_calendar_compression", "efficiency compression range");
includes(frontstageSource, "maturity-adjusted", "maturity adjusted copy");
includes(frontstageSource, 'data-testid="frontstage-state-flow-hero"', "showcase state-flow hero");
includes(frontstageSource, "State flow control plane", "state-flow hero label");
includes(frontstageSource, "The work moves. Judgment stays visible.", "state-flow hero punchline");
includes(frontstageSource, "showcaseStateFlow", "state-flow nodes");
includes(frontstageSource, 'data-testid="frontstage-showcase-cases"', "showcase case cards panel");
includes(frontstageSource, 'data-testid="frontstage-showcase-discovery"', "showcase discovery controls");
includes(frontstageSource, 'data-testid="frontstage-showcase-search"', "showcase catalog search control");
includes(frontstageSource, 'data-testid="frontstage-showcase-domain-filter"', "showcase domain filter");
includes(frontstageSource, 'data-testid="frontstage-showcase-result-count"', "showcase result count");
includes(frontstageSource, "Showcase Cases", "showcase cases copy");
includes(frontstageSource, "Search public showcases", "showcase search accessible label");
includes(frontstageSource, "Showing {filteredCases.length} of {frontstageShowcases.length} public-safe cases", "showcase count copy");
includes(frontstageSource, "No public showcase matched the current filters.", "showcase empty state");
includes(frontstageSource, "frontstageShowcases", "catalog-driven showcase cases");
includes(frontstageSource, 'data-testid="frontstage-showcase-motion"', "showcase motion panel");
includes(frontstageSource, 'data-testid="frontstage-showcase-journey-rail"', "showcase journey rail");
includes(frontstageSource, 'data-testid="frontstage-showcase-spotlight"', "showcase spotlight panel");
includes(frontstageSource, 'data-testid="frontstage-showcase-motion-card"', "showcase motion card control");
includes(frontstageSource, "Showcase Motion", "showcase motion copy");
includes(frontstageSource, "Case-driven motion board", "case-driven motion board copy");
includes(frontstageSource, "Asynchronous agent rhythm", "showcase asynchronous rhythm copy");
includes(frontstageSource, "Always-on agent teams can keep safe work moving", "showcase always-on agent copy");
includes(frontstageSource, "Evidence boundary:", "showcase spotlight evidence boundary copy");
includes(frontstageSource, "docs/showcases/showcase-catalog.json", "showcase catalog source copy");
includes(frontstageSource, "Open case page", "case page outbound link");
includes(frontstageSource, "github.com/huangruiteng/goal-harness/blob/main", "public GitHub case page links");
includes(frontstageSource, "Projection is read-only", "read-only truth copy");
includes(frontstageSource, "Inspired by modern agent boards", "product benchmark copy");
excludes(frontstageSource, "<form", "write form");
excludes(frontstageSource, "method=", "form method");
excludes(frontstageSource, "onclick=", "inline click handler");

includes(catalogSource, '"efficiency_model"', "showcase catalog efficiency model");
includes(catalogSource, '"2026-06-19-goal-harness-self-iteration"', "self-iteration showcase case");
includes(catalogSource, '"2026-06-17-blocked-p0-safe-rotation"', "blocked P0 showcase case");
includes(catalogSource, '"2026-06-20-creator-operator-case-spec"', "creator operator showcase case");

const motionSource = sourceBetween(frontstageSource, "function ShowcaseMotionBoard", "function ShowcaseCasePackPanel", "showcase motion board");
includes(motionSource, "frontstageShowcases", "motion board catalog source");
includes(motionSource, "journeySegments", "motion board journey summary");
includes(motionSource, "activeCaseId", "motion board active case state");
includes(motionSource, "setActiveCaseId", "motion board case selection");
includes(motionSource, "visual_metaphor", "motion board visual metaphor field");
includes(motionSource, "story_beats", "motion board story beats field");
includes(motionSource, "evidence_boundary", "motion board evidence boundary field");
includes(motionSource, "Always-on agent teams", "motion board always-on copy");
includes(motionSource, 'data-testid="frontstage-showcase-motion-beam"', "motion board animated beam");
includes(motionSource, 'aria-hidden="true"', "motion board decorative motion hidden from assistive tech");
excludes(motionSource, "projection", "motion board live projection dependency");
excludes(motionSource, "payload", "motion board live payload dependency");
includes(stylesSource, ".frontstage-showcase-motion-rail", "motion board rail CSS");
includes(stylesSource, ".frontstage-showcase-motion-beam", "motion board beam CSS");
includes(stylesSource, "@keyframes frontstage-case-traffic", "motion board case traffic keyframes");

const stateFlowHeroSource = sourceBetween(frontstageSource, "function ShowcaseStateFlowHero", "function PublicShowcaseBoundaryPanel", "showcase state-flow hero");
includes(stateFlowHeroSource, "showcaseStateFlow", "state-flow hero source");
includes(stateFlowHeroSource, "animate-ping", "state-flow hero pulse");
includes(stateFlowHeroSource, 'data-testid="frontstage-state-flow-track"', "state-flow animated track");
includes(stateFlowHeroSource, 'data-testid="frontstage-state-flow-beam"', "state-flow animated beam");
includes(stateFlowHeroSource, 'aria-hidden="true"', "state-flow decorative motion hidden from assistive tech");
excludes(stateFlowHeroSource, "projection", "state-flow hero live projection dependency");
excludes(stateFlowHeroSource, "payload", "state-flow hero live payload dependency");
includes(stylesSource, ".frontstage-state-flow-track", "state-flow track CSS");
includes(stylesSource, ".frontstage-state-flow-beam", "state-flow beam CSS");
includes(stylesSource, "@keyframes frontstage-flow-scan", "state-flow scan keyframes");
includes(stylesSource, "@media (prefers-reduced-motion: reduce)", "state-flow reduced-motion fallback");

const casePackSource = sourceBetween(frontstageSource, "function ShowcaseCasePackPanel", "function PublicShowcaseBoundaryPanel", "showcase case pack");
includes(casePackSource, "showcaseSearchText", "case pack catalog search index");
includes(casePackSource, "uniqueShowcaseDomains", "case pack catalog domain filter");
includes(casePackSource, "filteredCases", "case pack filtered render list");
excludes(casePackSource, "projection", "case pack live projection dependency");
excludes(casePackSource, "payload", "case pack live payload dependency");

includes(readmeSource, "/frontstage", "README frontstage route mention");
includes(readmeSource, "operations strip", "README operations strip explanation");
includes(readmeSource, "Role Map", "README role map explanation");
includes(readmeSource, "Efficiency Evidence", "README efficiency evidence explanation");
includes(readmeSource, "Showcase Motion", "README showcase motion explanation");
includes(readmeSource, "Showcase Cases", "README showcase cases explanation");
includes(readmeSource, "read-only projection", "README read-only projection boundary");
includes(readmeSource, "write authority", "README write authority boundary");
includes(selectionSource, "Multica", "Multica benchmark note");
includes(selectionSource, "agent board", "agent board benchmark note");

console.log("frontstage-route smoke ok");
