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
const frontstageAutoResearchSource = readFileSync("src/views/frontstage-auto-research-page.tsx", "utf8");
const frontstageDeveloperSource = readFileSync("src/views/frontstage-developer-page.tsx", "utf8");
const frontstageSource = readFileSync("src/views/frontstage-page.tsx", "utf8");
const stylesSource = readFileSync("src/styles.css", "utf8");
const dataSource = readFileSync("src/data/goal-channel-frontstage.ts", "utf8");
const localStatusQuerySource = readFileSync("src/data/local-status-query.ts", "utf8");
const statusSource = readFileSync("src/data/status.ts", "utf8");
const catalogSource = readFileSync("../../docs/showcases/showcase-catalog.json", "utf8");
const autoResearchBoardSource = readFileSync("../../docs/product/auto-research-frontstage-board.public.json", "utf8");
const rolloutProjectionFixtureSource = readFileSync("../../examples/fixtures/frontstage-rollout-projections.public.json", "utf8");
const privateTrapFixtureSource = readFileSync("../../examples/fixtures/frontstage-private-status-trap.public.json", "utf8");
const readmeSource = readFileSync("README.md", "utf8");
const selectionSource = readFileSync("../../docs/dashboard-frontend-selection.md", "utf8");
const packageSource = readFileSync("package.json", "utf8");

includes(routerSource, 'path: "/frontstage"', "frontstage route path");
includes(routerSource, "component: FrontstagePage", "frontstage route component");
includes(routerSource, 'path: "/frontstage/developer"', "frontstage developer route path");
includes(routerSource, "component: FrontstageDeveloperPage", "frontstage developer route component");
includes(routerSource, "frontstageDeveloperRoute", "frontstage developer route export");
includes(routerSource, 'path: "/frontstage/auto-research"', "frontstage auto-research route path");
includes(routerSource, "component: FrontstageAutoResearchPage", "frontstage auto-research route component");
includes(routerSource, "frontstageAutoResearchRoute", "frontstage auto-research route export");
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

const autoResearchBoard = JSON.parse(autoResearchBoardSource);
assert(
  autoResearchBoard.schema_version === "auto_research_frontstage_board_v0",
  "auto-research board schema version",
);
assert(autoResearchBoard.surface.stage === "experimental", "auto-research board remains experimental");
assert(autoResearchBoard.projection_binding.read_only === true, "auto-research board read-only binding");
assert(
  autoResearchBoard.projection_binding.first_screen_policy ===
    "experimental_only_not_first_screen_without_owner_review",
  "auto-research board first-screen policy",
);
assert(autoResearchBoard.lane_contract.topology === "decentralized", "auto-research decentralized topology");
assert(autoResearchBoard.value_metrics.length >= 4, "auto-research board must expose user-value metrics");
assert(
  autoResearchBoard.evidence_graph.best_holdout_metric > autoResearchBoard.evidence_graph.metric.baseline,
  "auto-research board must surface held-out improvement",
);
assert(
  autoResearchBoard.decision_candidates.promotion_candidates.length >= 1,
  "auto-research board promotion candidate",
);
assert(
  autoResearchBoard.decision_candidates.retirement_candidates.length >= 1,
  "auto-research board retirement candidate",
);
assert(autoResearchBoard.user_gates.length >= 4, "auto-research board user gates");
for (const gateId of [
  "first_screen_review_gate",
  "promotion_gate",
  "protected_scope_gate",
  "real_launch_gate",
]) {
  assert(
    autoResearchBoard.user_gates.some((gate: { gate_id: string }) => gate.gate_id === gateId),
    `auto-research board user gate ${gateId}`,
  );
}
for (const forbidden of [
  "/Users/",
  "/private/",
  "/tmp/",
  "lark" + "office",
  "byte" + "dance",
  "Bearer ",
  "api_key",
  "password",
  "secret",
]) {
  excludes(autoResearchBoardSource, forbidden, `auto-research board private marker ${forbidden}`);
}

includes(mainSource, "QueryClientProvider", "TanStack Query provider");
includes(mainSource, "new QueryClient", "query client construction");
includes(mainSource, "refetchOnWindowFocus: false", "query focus refetch policy");
includes(mainSource, "staleTime: 15_000", "query freshness window");

includes(dataSource, 'schema_version: "goal_channel_projection_v0"', "goal channel schema");
includes(dataSource, "goalChannelProjectionSchema", "goal channel zod schema");
includes(dataSource, 'mode: "read_only"', "read-only mode");
includes(dataSource, 'claimed_by: "codex-side-bypass"', "side-agent claim fixture");
includes(dataSource, 'scheduler_rrule: "FREQ=MINUTELY;INTERVAL=3"', "scheduler cadence fixture");
includes(dataSource, 'pause_policy: "control-plane policy only"', "pause policy fixture");
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
includes(frontstageSource, 'data-testid="frontstage-budget-governance"', "budget governance panel");
includes(frontstageSource, "Budget & Governance", "budget governance panel title");
includes(frontstageSource, "Cadence changes, final checks, and monitor-only polls are no-spend.", "no-spend governance copy");
includes(frontstageSource, "Audit through todo ids, run history, and quota spend events.", "budget evidence audit copy");
includes(frontstageSource, 'data-testid="frontstage-goal-select"', "goal selector");
includes(frontstageSource, "resolveFrontstageOpsStatusUrl", "ops status URL resolver");
includes(frontstageSource, "statusContractFreshnessIssue", "schema freshness gate");
includes(frontstageSource, "localDashboardApiCapabilities", "local capability projection");
includes(frontstageSource, "Ops statusUrl accepts only relative or loopback sources.", "ops source guard helper copy");
includes(frontstageSource, 'data-testid="frontstage-management-surface-mock"', "management surface mock");
includes(frontstageSource, 'data-testid={`frontstage-management-${card.id}`}', "management surface card ids");
includes(frontstageSource, "Mission Bar", "management surface mission bar");
includes(frontstageSource, "Team Roster", "management surface team roster");
includes(frontstageSource, "Ticket Board", "management surface ticket board");
includes(frontstageSource, "Gate Inbox", "management surface gate inbox");
includes(frontstageSource, "Cadence / Budget", "management surface cadence budget");
includes(frontstageSource, "Evidence Timeline", "management surface evidence timeline");
includes(frontstageSource, "goal_id + next_action", "management surface mission source");
includes(frontstageSource, "user_todos + agent_todos", "management surface ticket source");
includes(frontstageSource, "quota + scheduler hints", "management surface budget source");
includes(frontstageSource, "recent_events + artifacts", "management surface evidence source");
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
includes(frontstageSource, "Loop engineering for long-running AI agents", "showcase-first hero title");
includes(frontstageSource, "Public cases first. Live registry state stays behind explicit ops mode.", "showcase-first hero copy");
includes(frontstageSource, 'data-testid="frontstage-public-cta-row"', "public homepage CTA row");
includes(frontstageSource, "Explore cases", "public homepage cases CTA");
includes(frontstageSource, "Share feedback", "public homepage feedback CTA");
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
includes(frontstageSource, 'data-testid="frontstage-trajectory-analysis"', "trajectory analysis panel");
includes(frontstageSource, "rolloutProjectionFixture", "rollout projection public fixture import");
includes(frontstageSource, "RolloutProjectionBundle", "rollout projection bundle type");
includes(frontstageSource, 'data-testid="frontstage-rollout-projection-constellation"', "rollout projection constellation");
includes(frontstageSource, 'data-testid="frontstage-rollout-projection-model-contract"', "generic projection model contract");
includes(frontstageSource, 'data-testid="frontstage-rollout-relationship-mesh"', "generic rollout relationship mesh");
includes(frontstageSource, 'data-testid="frontstage-rollout-timeline"', "generic rollout timeline");
includes(frontstageSource, 'data-testid="frontstage-rollout-timeline-scale"', "generic rollout timeline scale");
includes(frontstageSource, 'data-testid="frontstage-rollout-timeline-tick"', "generic rollout timeline ticks");
includes(frontstageSource, 'data-testid="frontstage-rollout-timeline-point"', "generic rollout timeline points");
includes(frontstageSource, 'data-testid="frontstage-rollout-time-milestone"', "generic rollout time milestones");
includes(frontstageSource, 'data-node-time={rolloutNodeTimeLabel(node)}', "generic rollout node time attribute");
includes(frontstageSource, 'data-testid="frontstage-rollout-mesh-node"', "generic rollout mesh nodes");
includes(frontstageSource, 'data-testid="frontstage-rollout-mesh-node-tooltip"', "generic rollout node tooltip");
includes(frontstageSource, 'data-testid="frontstage-rollout-mesh-edge"', "generic rollout mesh edges");
includes(frontstageSource, 'data-testid="frontstage-rollout-mesh-edge-hit"', "generic rollout mesh edge hit targets");
includes(frontstageSource, 'data-testid="frontstage-rollout-mesh-edge-hotspot"', "generic rollout mesh edge hover hotspots");
includes(frontstageSource, 'data-testid="frontstage-rollout-mesh-edge-hover-card"', "generic rollout edge hover card");
includes(frontstageSource, 'data-testid="frontstage-rollout-mesh-time-tick"', "generic rollout mesh wall-clock ticks");
includes(frontstageSource, 'data-edge-kind={edge.edge_kind}', "generic rollout edge kind attribute");
includes(frontstageSource, 'data-edge-label={edge.label}', "generic rollout edge label attribute");
includes(frontstageSource, 'data-testid="frontstage-rollout-mesh-lane"', "generic rollout mesh lanes");
includes(frontstageSource, 'data-testid="frontstage-rollout-requirement-spine"', "rollout requirement spine");
includes(frontstageSource, 'data-testid="frontstage-rollout-sequence-ribbon"', "rollout sequence ribbon");
includes(frontstageSource, 'data-testid="frontstage-rollout-sequence-chip"', "rollout sequence chips");
includes(frontstageSource, 'data-testid="frontstage-rollout-requirement-unit"', "rollout requirement units");
includes(frontstageSource, 'data-testid="frontstage-rollout-requirement-step"', "rollout requirement steps");
includes(frontstageSource, 'data-testid="frontstage-rollout-capability-map"', "rollout capability map");
includes(frontstageSource, 'data-testid="frontstage-rollout-mapping-layer"', "rollout mapping layer cards");
includes(frontstageSource, 'data-testid="frontstage-rollout-flow-signals"', "rollout flow signals");
includes(frontstageSource, 'data-testid="frontstage-rollout-relationship-summaries"', "rollout relationship grammar");
includes(frontstageSource, 'data-testid="frontstage-rollout-attention-hotspots"', "rollout attention hotspots");
includes(frontstageSource, 'data-testid="frontstage-trajectory-stage-confidence"', "trajectory stage confidence card");
includes(frontstageSource, 'data-testid="frontstage-rollout-stage-flow"', "rollout stage flow");
includes(frontstageSource, 'data-testid="frontstage-rollout-lane-graph"', "rollout lane graph");
includes(frontstageSource, 'data-testid="frontstage-rollout-edge-list"', "rollout edge list");
includes(frontstageSource, "projection.scene.title", "rollout projection scene title render");
includes(frontstageSource, 'data-testid="frontstage-trajectory-stage-curve"', "trajectory stage progress curve");
includes(frontstageSource, 'data-testid="frontstage-trajectory-current-scene"', "trajectory current-stage scene");
includes(frontstageSource, 'data-testid="frontstage-trajectory-verdict-card"', "trajectory verdict card");
includes(frontstageSource, 'data-testid="frontstage-trajectory-evidence-drawer"', "trajectory evidence drawer");
includes(frontstageSource, "RolloutProjectionConstellation", "rollout projection renderer component");
includes(frontstageSource, "RolloutRelationshipMesh", "generic rollout relationship mesh renderer component");
includes(frontstageSource, "RolloutRequirementSpine", "rollout requirement spine renderer component");
includes(frontstageSource, "RolloutProjectionCapabilityMap", "rollout capability map component");
includes(frontstageSource, "RolloutProjectionStageFlow", "rollout stage renderer component");
includes(frontstageSource, "RolloutProjectionLaneGraph", "rollout lane graph renderer component");
includes(frontstageSource, "required_sections.join", "generic projection required sections render");
includes(frontstageSource, "raw trajectories and local state stay outside", "trajectory public boundary copy");
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
includes(frontstageSource, "huangruiteng.github.io/loopx", "hosted interactive case links");
includes(frontstageSource, "Projection is read-only", "read-only truth copy");
includes(frontstageSource, "Inspired by modern agent boards", "product benchmark copy");
excludes(frontstageSource, "<form", "write form");
excludes(frontstageSource, "method=", "form method");
excludes(frontstageSource, "onclick=", "inline click handler");

includes(catalogSource, '"efficiency_model"', "showcase catalog efficiency model");
includes(catalogSource, '"2026-06-19-loopx-self-iteration"', "self-iteration showcase case");
includes(catalogSource, '"2026-06-17-blocked-p0-safe-rotation"', "blocked P0 showcase case");
includes(catalogSource, '"2026-06-19-dynamic-workflow-hardware-agent"', "hardware-agent showcase case");
includes(catalogSource, '"public_safe_interactive_case"', "hardware-agent interactive case status");
includes(catalogSource, '"interactive_page"', "hardware-agent interactive page field");
includes(catalogSource, '"2026-06-20-creator-operator-case-spec"', "creator operator showcase case");

includes(rolloutProjectionFixtureSource, '"frontstage_rollout_projection_bundle_v0"', "rollout projection bundle schema");
includes(rolloutProjectionFixtureSource, '"frontstage_rollout_projection_model_v0"', "rollout projection model schema");
includes(rolloutProjectionFixtureSource, '"optional_rich_sections"', "rollout projection rich sections");
includes(rolloutProjectionFixtureSource, '"timeline"', "rollout timeline fixture");
includes(rolloutProjectionFixtureSource, '"item_node_ids"', "rollout timeline item ids");
includes(rolloutProjectionFixtureSource, '"axis_kind": "wall_clock"', "rollout wall-clock timeline axis");
includes(rolloutProjectionFixtureSource, '"timezone": "Asia/Shanghai"', "rollout timeline timezone");
includes(rolloutProjectionFixtureSource, '"started_at"', "rollout node started time");
includes(rolloutProjectionFixtureSource, '"completed_at"', "rollout node completed time");
includes(rolloutProjectionFixtureSource, '"duration_label"', "rollout node duration label");
includes(rolloutProjectionFixtureSource, '"wall-clock timeline ticks"', "rollout wall-clock acceptance item");
includes(rolloutProjectionFixtureSource, '"node time and duration hover details"', "rollout time hover acceptance item");
includes(rolloutProjectionFixtureSource, '"rollout_sequence"', "rollout sequence fixture");
includes(rolloutProjectionFixtureSource, '"sequence_id": "overnight_requirement_rollout_spine"', "rollout sequence id");
includes(rolloutProjectionFixtureSource, '"mapping_layers"', "rollout projection mapping layers");
includes(rolloutProjectionFixtureSource, '"flow_signals"', "rollout projection flow signals");
includes(rolloutProjectionFixtureSource, '"relationship_summaries"', "rollout projection relationship summaries");
includes(rolloutProjectionFixtureSource, '"attention_hotspots"', "rollout projection attention hotspots");
includes(rolloutProjectionFixtureSource, '"projection_id": "overnight_pr_batch_20260627"', "overnight PR projection id");
includes(rolloutProjectionFixtureSource, '"sample_window": "#746-#775"', "overnight PR sample window");
includes(rolloutProjectionFixtureSource, '"projection_is_writable": false', "rollout projection read-only contract");
includes(rolloutProjectionFixtureSource, '"Review mesh over a 30-PR public batch"', "rollout projection scene title");
includes(rolloutProjectionFixtureSource, '"generic projection model contract"', "rollout projection acceptance item");
includes(rolloutProjectionFixtureSource, '"30 PR relationship mesh"', "rollout relationship mesh acceptance item");
includes(rolloutProjectionFixtureSource, '"timeline axis"', "rollout timeline acceptance item");
includes(rolloutProjectionFixtureSource, '"hoverable node and edge details"', "rollout hover acceptance item");
includes(rolloutProjectionFixtureSource, '"sequential requirement rollout"', "rollout sequence acceptance item");
includes(rolloutProjectionFixtureSource, '"Show frontstage trajectory as a reusable projection"', "first rollout requirement");
includes(rolloutProjectionFixtureSource, '"Monitor tasks become due work instead of hidden polling"', "monitor rollout requirement");
includes(rolloutProjectionFixtureSource, '"planned_projections"', "planned projection section");
includes(rolloutProjectionFixtureSource, '"loopx_overall_iteration"', "planned LoopX overall iteration projection");
excludes(rolloutProjectionFixtureSource, "/Users/", "rollout projection local path");
excludes(rolloutProjectionFixtureSource, "/home/", "rollout projection home path");
excludes(rolloutProjectionFixtureSource, "Bearer ", "rollout projection credential marker");
excludes(rolloutProjectionFixtureSource, "GH_FAKE_PRIVATE", "rollout projection private trap marker");
excludes(rolloutProjectionFixtureSource, '"private_material_body_recorded": true', "rollout projection private body flag");

const motionSource = sourceBetween(frontstageSource, "function ShowcaseMotionBoard", "function rolloutKindTone", "showcase motion board");
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

const trajectorySource = sourceBetween(frontstageSource, "function TrajectoryAnalysisPanel", "const showcaseMotionTones", "trajectory analysis panel");
includes(trajectorySource, "overnightPrProjection", "trajectory uses overnight rollout projection");
includes(trajectorySource, "RolloutProjectionConstellation", "trajectory renders generic projection constellation");
includes(trajectorySource, "RolloutProjectionCapabilityMap", "trajectory renders capability map");
includes(trajectorySource, "RolloutProjectionStageFlow", "trajectory renders stage flow from projection");
includes(trajectorySource, "RolloutProjectionLaneGraph", "trajectory renders lane graph from projection");
includes(trajectorySource, "frontstage-trajectory-stage", "trajectory stage render loop");
includes(trajectorySource, "Stage progress curve", "trajectory curve label");
includes(trajectorySource, "Evidence drawer", "trajectory evidence drawer label");
includes(trajectorySource, "Anchor {anchorNode?.label", "trajectory anchor node explanation");
includes(trajectorySource, "read-only projection", "trajectory read-only projection label");
includes(trajectorySource, "projection.source_contract.next_projection_hint", "trajectory surfaces next projection hint");
includes(trajectorySource, "raw trajectories and local state stay outside", "trajectory private-source exclusion copy");
excludes(trajectorySource, "fetchFrontstageStatusPayload", "trajectory live status dependency");
excludes(trajectorySource, "statusUrl", "trajectory status URL dependency");

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

includes(frontstageAutoResearchSource, 'data-testid="frontstage-auto-research-board"', "auto-research board route test id");
includes(frontstageAutoResearchSource, "autoResearchBoardData", "auto-research board JSON import");
includes(frontstageAutoResearchSource, "auto-research-frontstage-board.public.json", "auto-research board public fixture");
includes(frontstageAutoResearchSource, 'data-testid="auto-research-value-metrics"', "auto-research value metrics");
includes(frontstageAutoResearchSource, 'data-testid="auto-research-contract-commands"', "auto-research runnable command strip");
includes(frontstageAutoResearchSource, 'data-testid="auto-research-lane-contract"', "auto-research lane contract");
includes(frontstageAutoResearchSource, 'data-testid="auto-research-frontier"', "auto-research per-agent frontier");
includes(frontstageAutoResearchSource, 'data-testid="auto-research-evidence-graph"', "auto-research evidence graph");
includes(frontstageAutoResearchSource, 'data-testid="auto-research-decision-candidates"', "auto-research decision candidates");
includes(frontstageAutoResearchSource, 'data-testid="auto-research-user-gates"', "auto-research user gates");
includes(frontstageAutoResearchSource, 'data-testid="auto-research-showcase-projection"', "auto-research showcase projection");
includes(autoResearchBoardSource, "single leader agent owns the whole hypothesis tree", "auto-research hidden leader anti-pattern");
includes(autoResearchBoardSource, "Public fixture and protected-evaluator outputs only", "auto-research public boundary");
includes(autoResearchBoardSource, "first_screen_review_gate", "auto-research first-screen gate data");
includes(frontstageAutoResearchSource, "BoardPanel", "auto-research board panel component");
excludes(frontstageAutoResearchSource, "<form", "auto-research board write form");
excludes(frontstageAutoResearchSource, "method=", "auto-research board form method");
excludes(frontstageAutoResearchSource, "fetchFrontstageStatusPayload", "auto-research board live status dependency");
excludes(frontstageAutoResearchSource, "statusUrl", "auto-research board status URL dependency");

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
