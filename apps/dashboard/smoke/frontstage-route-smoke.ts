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
const mainSource = readFileSync("src/main.tsx", "utf8");
const frontstageDeveloperSource = readFileSync("src/views/frontstage-developer-page.tsx", "utf8");
const frontstageSource = readFileSync("src/views/frontstage-page.tsx", "utf8");
const stylesSource = readFileSync("src/styles.css", "utf8");
const dataSource = readFileSync("src/data/goal-channel-frontstage.ts", "utf8");
const localStatusQuerySource = readFileSync("src/data/local-status-query.ts", "utf8");
const statusSource = readFileSync("src/data/status.ts", "utf8");
const catalogSource = readFileSync("../../docs/showcases/showcase-catalog.json", "utf8");
const privateTrapFixtureSource = readFileSync("../../examples/fixtures/frontstage-private-status-trap.public.json", "utf8");
const readmeSource = readFileSync("README.md", "utf8");
const selectionSource = readFileSync("../../docs/dashboard-frontend-selection.md", "utf8");
const packageSource = readFileSync("package.json", "utf8");

includes(routerSource, 'path: "/frontstage"', "frontstage route path");
includes(routerSource, "component: FrontstagePage", "frontstage route component");
includes(routerSource, 'path: "/frontstage/developer"', "frontstage developer route path");
includes(routerSource, "component: FrontstageDeveloperPage", "frontstage developer route component");
includes(routerSource, "frontstageDeveloperRoute", "frontstage developer route export");
includes(routerSource, "frontstageSearchSchema", "frontstage search schema");
includes(routerSource, 'mode: z.enum(["showcase", "developer", "ops"]).optional().default("showcase")', "frontstage mode gate");
includes(routerSource, 'todoLane: z.enum(["all", "user", "agent"]).optional().default("all")', "frontstage todo lane filter search param");
includes(routerSource, 'todoQuery: z.string().optional().default("")', "frontstage todo search param");
includes(routerSource, "basepath:", "router basepath option");
includes(routerSource, "import.meta.env.BASE_URL", "Vite base URL router source");
includes(packageSource, '"smoke:frontstage-browser"', "frontstage browser smoke script");
includes(packageSource, '"smoke:frontstage-route"', "frontstage smoke script");
includes(privateTrapFixtureSource, "GH_FAKE_PRIVATE_PLAN_SUMMARY_ALPHA", "fake-private status trap plan marker");
includes(privateTrapFixtureSource, "GH_FAKE_LIVE_STATUS_FEED_BETA", "fake-private live status trap marker");
includes(privateTrapFixtureSource, "GH_FAKE_PRIVATE_TODO_GAMMA", "fake-private todo trap marker");
includes(packageSource, '"@tanstack/react-query"', "TanStack Query dependency");

includes(mainSource, "QueryClientProvider", "TanStack Query provider");
includes(mainSource, "new QueryClient", "query client construction");
includes(mainSource, "refetchOnWindowFocus: false", "query focus refetch policy");
includes(mainSource, "staleTime: 15_000", "query freshness window");

includes(dataSource, 'schema_version: "goal_channel_projection_v0"', "goal channel schema");
includes(dataSource, "goalChannelProjectionSchema", "goal channel zod schema");
includes(dataSource, 'mode: "read_only"', "read-only mode");
includes(dataSource, 'claimed_by: "codex-side-bypass"', "side-agent claim fixture");
includes(dataSource, "raw_or_private_material_omitted", "source warning fixture");
includes(statusSource, "goal_channel_projection: goalChannelProjectionSchema", "status projection parser");
includes(statusSource, "local_dashboard_api", "local dashboard API status parser");

includes(localStatusQuerySource, "resolveFrontstageOpsStatusUrl", "frontstage status URL resolver");
includes(localStatusQuerySource, "fetchFrontstageStatusPayload", "frontstage status query fetcher");
includes(localStatusQuerySource, "parseStatusPayload", "status payload parser in query helper");
includes(localStatusQuerySource, "statusContractFreshnessIssue", "status contract freshness helper");
includes(localStatusQuerySource, "localDashboardApiCapabilities", "local dashboard API capability helper");
includes(localStatusQuerySource, "expectedStatusContractSchemaVersion", "schema freshness gate");
includes(localStatusQuerySource, "fallbackStatusContractReloadHint", "stale daemon repair hint");
includes(localStatusQuerySource, "isLoopbackHostname", "loopback source guard");
includes(localStatusQuerySource, "Ops statusUrl must be relative or loopback", "ops status URL guard copy");

includes(frontstageSource, 'data-testid="goal-channel-frontstage-route"', "route test id");
includes(frontstageSource, 'data-frontstage-surface={isOpsMode ? "ops-control-plane" : "showcase-homepage"}', "frontstage surface split marker");
includes(frontstageSource, 'data-testid={isOpsMode ? "frontstage-ops-workspace-shell" : "frontstage-showcase-workspace-shell"}', "frontstage workspace shell marker");
includes(frontstageSource, 'data-testid="frontstage-live-source-panel"', "live source panel");
includes(frontstageSource, 'data-testid="frontstage-public-boundary-note"', "public boundary note");
includes(frontstageSource, "Showcase mode ignores statusUrl", "public mode statusUrl guard copy");
includes(frontstageSource, 'if (!liveMode)', "live status feed requires ops mode");
includes(frontstageSource, "useQuery", "frontstage uses TanStack Query");
includes(frontstageSource, 'queryKey: ["frontstage-ops-status"', "frontstage query key");
includes(frontstageSource, "fetchFrontstageStatusPayload", "frontstage status query function");
includes(frontstageSource, 'data-testid="frontstage-stale-daemon-repair"', "frontstage stale daemon repair panel");
includes(frontstageSource, 'data-testid="frontstage-local-api-capabilities"', "frontstage local API capability panel");
includes(frontstageSource, "local_dashboard_api:", "local dashboard API copy");
includes(frontstageSource, "read-only default", "read-only default copy");
includes(frontstageSource, "Write affordances require explicit loopback opt-in", "loopback opt-in copy");
includes(frontstageSource, "TanStack Query", "TanStack Query copy");
includes(frontstageSource, 'data-testid="frontstage-operations-strip"', "operations signal strip");
includes(frontstageSource, 'data-testid="frontstage-goal-select"', "goal selector");
includes(frontstageSource, "resolveFrontstageOpsStatusUrl", "ops status URL resolver");
includes(frontstageSource, "statusContractFreshnessIssue", "schema freshness gate");
includes(frontstageSource, "localDashboardApiCapabilities", "local capability projection");
includes(frontstageSource, "Ops statusUrl accepts only relative or loopback sources.", "ops source guard helper copy");
includes(frontstageSource, 'data-testid="frontstage-user-todos"', "user todo lane");
includes(frontstageSource, 'data-testid="frontstage-agent-todos"', "agent todo lane");
includes(frontstageSource, 'data-testid="frontstage-todo-discovery"', "todo discovery controls");
includes(frontstageSource, 'data-testid="frontstage-ops-command-strip"', "ops command strip");
includes(frontstageSource, 'data-testid="frontstage-todo-search"', "todo search control");
includes(frontstageSource, 'data-testid="frontstage-todo-lane-filter"', "todo lane filter control");
includes(frontstageSource, 'data-testid="frontstage-todo-result-count"', "todo filter result count");
includes(frontstageSource, "todoSearchText", "todo search index helper");
includes(frontstageSource, "filterTodosByQuery", "todo query filter helper");
includes(frontstageSource, "Showing {visibleTodoCount} of {totalTodoCount} projected todos", "todo result count copy");
includes(frontstageSource, 'data-testid="frontstage-role-map"', "role map lane");
includes(frontstageSource, 'data-testid="frontstage-active-claims"', "active claims lane");
includes(frontstageSource, 'data-testid="frontstage-open-gates"', "open gates lane");
includes(frontstageSource, 'data-testid="frontstage-artifacts"', "artifacts lane");
includes(frontstageSource, 'data-testid="frontstage-timeline"', "timeline lane");
includes(frontstageSource, "Frontstage channel", "frontstage channel copy");
includes(frontstageSource, "Channel board", "channel board nav");
includes(frontstageSource, "Developer cockpit", "developer cockpit nav");
includes(frontstageSource, "Always-on agent operations", "always-on operations copy");
includes(frontstageSource, "LoopX Showcase Frontstage", "showcase-first hero title");
includes(frontstageSource, "Async agent teams, governed by human judgment", "showcase-first hero copy");
includes(frontstageSource, "Developer Onboarding Frontstage", "developer mode hero title");
includes(frontstageSource, 'data-testid="frontstage-developer-onboarding"', "developer onboarding panel");
includes(frontstageSource, "Start the loop from one TUI message", "developer one-message start copy");
includes(frontstageSource, "workspace_guard blocks side-agent edits", "developer workspace guard copy");
includes(frontstageSource, "Developer mode ignores statusUrl", "developer public statusUrl guard");
includes(frontstageSource, 'data-testid="frontstage-public-showcase-contract"', "public showcase contract panel");
includes(frontstageSource, "Local status URLs stay behind explicit Ops live URLs", "ops-only live status copy");
includes(frontstageSource, 'data-testid="frontstage-ops-entry-hint"', "explicit ops entry hint");
includes(frontstageSource, "Use mode=ops with statusUrl.", "wrapped ops entry hint copy");
excludes(frontstageSource, 'data-testid="frontstage-enable-ops-live"', "in-page ops live switch");
includes(frontstageSource, "human judgment kept in the control plane", "human judgment control-plane copy");
includes(frontstageSource, "Role Map", "role map copy");
includes(frontstageSource, "claim owners", "claim owner role signal");
includes(frontstageSource, "claimed lanes", "claimed lane signal");
includes(frontstageSource, "evidence loop", "evidence loop signal");
includes(frontstageSource, "No open gates in this projection.", "open gates empty state");
includes(frontstageSource, "No compact artifacts projected.", "artifacts empty state");
includes(frontstageSource, "artifactDisplayValue", "artifact value truncation helper");
includes(frontstageSource, 'data-testid="frontstage-efficiency-evidence"', "efficiency evidence panel");
includes(frontstageSource, "Efficiency Evidence", "efficiency evidence copy");
includes(frontstageSource, "showcaseCatalog", "showcase catalog import");
includes(frontstageSource, "showcaseCaseHref", "central showcase case page link helper");
includes(frontstageSource, "estimated_developer_days", "efficiency baseline range");
includes(frontstageSource, "single_engineer_calendar_compression", "efficiency compression range");
includes(frontstageSource, "maturity-adjusted", "maturity adjusted copy");
includes(frontstageSource, 'data-testid="frontstage-state-flow-hero"', "showcase state-flow hero");
includes(frontstageSource, "State flow control plane", "state-flow hero label");
includes(frontstageSource, "Work keeps moving. Judgment stays in charge.", "state-flow hero punchline");
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
includes(frontstageSource, 'data-testid="frontstage-showcase-kinetic-strip"', "showcase kinetic case strip");
includes(frontstageSource, 'data-testid="frontstage-showcase-kinetic-card"', "showcase kinetic case card");
includes(frontstageSource, "Async Work Loop", "showcase motion copy");
includes(frontstageSource, "Case-driven motion board", "case-driven motion board copy");
includes(frontstageSource, "Agent lanes run across turns; the human control plane decides what ships.", "showcase kinetic strip copy");
includes(frontstageSource, "Asynchronous agent rhythm", "showcase asynchronous rhythm copy");
includes(frontstageSource, "Agent teams work across turns and off-hours", "showcase async agent copy");
includes(frontstageSource, "Evidence boundary:", "showcase spotlight evidence boundary copy");
includes(frontstageSource, 'data-testid="frontstage-showcase-spotlight-case-page"', "showcase spotlight case page link");
includes(frontstageSource, "Open selected case page", "showcase spotlight case page copy");
includes(frontstageSource, "docs/showcases/showcase-catalog.json", "showcase catalog source copy");
includes(frontstageSource, "Open case page", "case page outbound link");
includes(frontstageSource, "github.com/huangruiteng/loopx/blob/main", "public GitHub case page links");
includes(frontstageSource, "Projection is read-only", "read-only truth copy");
includes(frontstageSource, "Inspired by modern agent boards", "product benchmark copy");
excludes(frontstageSource, "<form", "write form");
excludes(frontstageSource, "method=", "form method");
excludes(frontstageSource, "onclick=", "inline click handler");

includes(catalogSource, '"efficiency_model"', "showcase catalog efficiency model");
includes(catalogSource, '"2026-06-19-loopx-self-iteration"', "self-iteration showcase case");
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
includes(motionSource, "Agent teams work across turns and off-hours", "motion board async-agent copy");
includes(motionSource, 'data-testid="frontstage-showcase-motion-beam"', "motion board animated beam");
includes(motionSource, 'aria-hidden="true"', "motion board decorative motion hidden from assistive tech");
excludes(motionSource, "projection", "motion board live projection dependency");
excludes(motionSource, "payload", "motion board live payload dependency");
includes(stylesSource, ".frontstage-showcase-motion-rail", "motion board rail CSS");
includes(stylesSource, ".frontstage-showcase-motion-beam", "motion board beam CSS");
includes(stylesSource, "@keyframes frontstage-case-traffic", "motion board case traffic keyframes");

const kineticStripSource = sourceBetween(frontstageSource, "function ShowcaseKineticCaseStrip", "function FrontstageRoute", "showcase kinetic strip");
includes(kineticStripSource, "frontstageShowcases", "kinetic strip catalog source");
includes(kineticStripSource, "showcaseCaseHref", "kinetic strip case links");
includes(kineticStripSource, "uniqueShowcaseDomains", "kinetic strip domain count");
includes(kineticStripSource, "stripCases", "kinetic strip duplicated marquee cases");
includes(kineticStripSource, "human control plane decides what ships", "kinetic strip product copy");
excludes(kineticStripSource, "projection", "kinetic strip live projection dependency");
excludes(kineticStripSource, "payload", "kinetic strip live payload dependency");
excludes(kineticStripSource, "statusUrl", "kinetic strip local status dependency");
includes(stylesSource, ".frontstage-showcase-kinetic-viewport", "kinetic strip viewport CSS");
includes(stylesSource, ".frontstage-showcase-kinetic-track", "kinetic strip track CSS");
includes(stylesSource, ".frontstage-showcase-kinetic-card", "kinetic strip card CSS");
includes(stylesSource, "@keyframes frontstage-kinetic-strip", "kinetic strip keyframes");

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

const casePackSource = sourceBetween(frontstageSource, "function ShowcaseCasePackPanel", "const showcaseStateFlow", "showcase case pack");
includes(casePackSource, "showcaseSearchText", "case pack catalog search index");
includes(casePackSource, "uniqueShowcaseDomains", "case pack catalog domain filter");
includes(casePackSource, "filteredCases", "case pack filtered render list");
excludes(casePackSource, "projection", "case pack live projection dependency");
excludes(casePackSource, "payload", "case pack live payload dependency");

includes(readmeSource, "/frontstage", "README frontstage route mention");
includes(readmeSource, "operations strip", "README operations strip explanation");
includes(readmeSource, "Role Map", "README role map explanation");
includes(readmeSource, "Efficiency Evidence", "README efficiency evidence explanation");
includes(readmeSource, "Async Work Loop", "README showcase motion explanation");
includes(readmeSource, "Showcase Cases", "README showcase cases explanation");
includes(readmeSource, "read-only projection", "README read-only projection boundary");
includes(readmeSource, "write authority", "README write authority boundary");
includes(selectionSource, "Multica", "Multica benchmark note");
includes(selectionSource, "agent board", "agent board benchmark note");

includes(frontstageDeveloperSource, 'data-testid="frontstage-developer-cockpit"', "developer cockpit route test id");
includes(frontstageDeveloperSource, "LoopX Projection Developer Cockpit", "developer cockpit title");
includes(frontstageDeveloperSource, "Status Contract Explorer", "status contract explorer panel");
includes(frontstageDeveloperSource, 'data-testid="developer-contract-explorer"', "developer contract explorer test id");
includes(frontstageDeveloperSource, "Projection Diffing", "projection diffing panel");
includes(frontstageDeveloperSource, 'data-testid="developer-projection-diffing"', "projection diffing test id");
includes(frontstageDeveloperSource, "Fixture Generation", "fixture generation panel");
includes(frontstageDeveloperSource, 'data-testid="developer-fixture-generation"', "fixture generation test id");
includes(frontstageDeveloperSource, "Smoke Checklist", "smoke checklist panel");
includes(frontstageDeveloperSource, 'data-testid="developer-smoke-checklist"', "smoke checklist test id");
includes(frontstageDeveloperSource, "Component Examples", "component examples panel");
includes(frontstageDeveloperSource, 'data-testid="developer-component-examples"', "component examples test id");
includes(frontstageDeveloperSource, "Extension Boundary", "extension boundary panel");
includes(frontstageDeveloperSource, 'data-testid="developer-extension-boundary"', "extension boundary test id");
includes(frontstageDeveloperSource, "apps/dashboard/src/data/status.ts", "status parser source pointer");
includes(frontstageDeveloperSource, "apps/dashboard/src/data/goal-channel-frontstage.ts", "projection source pointer");
includes(frontstageDeveloperSource, "examples/status.example.json", "fixture source pointer");
includes(frontstageDeveloperSource, "loopx check --scan-path apps/dashboard", "boundary check command");
includes(frontstageDeveloperSource, "reverse-engineering the large operator page", "developer cockpit purpose");
includes(frontstageDeveloperSource, "live status feeds, registry files, and browser write APIs stay outside", "developer cockpit boundary");
excludes(frontstageDeveloperSource, "<form", "developer cockpit write form");
excludes(frontstageDeveloperSource, "method=", "developer cockpit form method");

console.log("frontstage-route smoke ok");
