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
const dashboardSource = readFileSync("src/views/dashboard-page.tsx", "utf8");
const readmeSource = readFileSync("README.md", "utf8");
const contractSource = readFileSync("../../docs/status-data-contract.md", "utf8");
const packageSource = readFileSync("package.json", "utf8");

const shareGoalSpecStart = dashboardSource.indexOf("const shareGoalSpecs");
const shareGoalSpecEnd = dashboardSource.indexOf("const shareStatusLabel", shareGoalSpecStart);
assert(shareGoalSpecStart >= 0 && shareGoalSpecEnd > shareGoalSpecStart, "missing share goal spec block");
const shareGoalSpecBlock = dashboardSource.slice(shareGoalSpecStart, shareGoalSpecEnd);
const shareGoalIds = [...shareGoalSpecBlock.matchAll(/id: "([^"]+)"/g)].map((match) => match[1]);
assert(shareGoalIds.length >= 4, "expected public showcase goal specs");
for (const goalId of shareGoalIds) {
  assert(
    goalId.startsWith("showcase-") || goalId === "loopx-meta",
    `public dashboard goal spec must use showcase/meta id: ${goalId}`,
  );
}

includes(routerSource, 'view: z.enum(["ops", "share"]).optional()', "optional view search param");
includes(routerSource, 'todoGoalId: z.string().optional().default("all")', "todo project search param");
includes(routerSource, 'todoQuery: z.string().optional().default("")', "todo query search param");
includes(routerSource, 'todoRole: z.enum(["all", "user", "agent"]).optional().default("all")', "todo role search param");
includes(routerSource, 'todoStatus: z.enum(["all", "open", "done", "blocked", "deferred"]).optional().default("all")', "todo status search param");
excludes(routerSource, 'view: z.enum(["ops", "share"]).optional().default("share")', "share default route mode");

includes(dashboardSource, 'const defaultGlobalStatusUrl = "http://127.0.0.1:8766/status.json";', "global default status URL");
includes(dashboardSource, 'return view === "ops" ? "ops" : undefined;', "canonical URL omits non-ops view");
includes(dashboardSource, 'if (search.view !== "ops" && source.kind === "example") {', "non-ops loads global status source once");
includes(dashboardSource, '[search.statusUrl, search.view, source.kind, source.label]', "status URL change reload effect");
includes(dashboardSource, 'void loadFromUrl(defaultGlobalStatusUrl);', "home loads global status source");
includes(dashboardSource, 'data-testid="share-overview"', "control-plane home test id");
includes(dashboardSource, 'data-testid={`share-top-todos-${view.spec.id}`}', "share top todo list test id");
includes(dashboardSource, 'data-testid={`share-decision-frame-${view.spec.id}`}', "first-screen decision frame test id");
includes(dashboardSource, "第一屏决策帧", "first-screen decision frame label");
includes(dashboardSource, "等待方", "first-screen waiting owner label");
includes(dashboardSource, "推荐动作", "first-screen recommended action label");
includes(dashboardSource, "安全边界", "first-screen safety boundary label");
includes(dashboardSource, "首个用户 Todo", "first-screen first user todo label");
includes(dashboardSource, "最高优 Agent Todo", "first-screen top agent todo label");
includes(dashboardSource, "Todo 投影缺口", "first-screen todo projection gap label");
includes(dashboardSource, "Top-4 Todo", "share top-four todo label");
includes(dashboardSource, "已完成", "share todo done status");
includes(dashboardSource, "决策需 rebase", "share decision freshness warning");
includes(dashboardSource, "这不是仓库回滚", "share decision non-rollback copy");
includes(dashboardSource, "synthetic-only", "showcase synthetic-only boundary");
includes(dashboardSource, '单面改动', "Chinese delivery scale label");
includes(dashboardSource, '阻塞说明', "Chinese blocker label");
includes(dashboardSource, '配额守卫', "Chinese quota guard label");
includes(dashboardSource, '状态写回', "Chinese state writeback label");
includes(dashboardSource, '<h1 className="text-2xl font-semibold">Goal Operations</h1>', "ops workbench fallback");
includes(dashboardSource, 'data-testid="project-todo-explorer"', "project todo explorer test id");
includes(dashboardSource, 'data-testid="project-todo-search-input"', "project todo search input test id");
includes(dashboardSource, 'data-testid="project-todo-id"', "project todo id rendering");
includes(dashboardSource, "Project Todo Explorer", "project todo explorer title");
includes(dashboardSource, "All projects", "project todo all-project selector");
includes(dashboardSource, "todoExplorerProjectOptions", "project todo auto project options");
includes(dashboardSource, "selectedTodoGoalId", "project todo selected project prop");
includes(dashboardSource, "claimed_by=", "project todo claimed owner metadata");
includes(dashboardSource, "action=", "project todo action metadata");
includes(dashboardSource, "source={item.source}", "project todo source metadata");
includes(dashboardSource, "latest_event_kind", "project todo historical event metadata");
includes(dashboardSource, "todoIndex={payload.todo_index}", "project todo index wiring");
excludes(dashboardSource, "raw internal slot constraints", "raw internal constraint copy");
includes(contractSource, "todo_id", "status contract todo id metadata");
includes(readFileSync("src/data/goal-channel-frontstage.ts", "utf8"), "generated_at: z.string().optional().nullable()", "goal channel generated_at optional live status compatibility");
includes(packageSource, '"smoke:home-route"', "home route smoke script");
includes(packageSource, '"smoke:home-browser"', "home browser smoke script");
includes(packageSource, '"smoke:demo-readiness"', "demo readiness smoke script");
includes(readmeSource, "npm run smoke:home-browser", "README home browser smoke command");
includes(readmeSource, "npm run smoke:demo-readiness", "README demo readiness smoke command");
includes(readmeSource, "--skip-browser", "README demo readiness CI skip-browser command");
includes(readmeSource, "Fresh Clone Public Preview", "README fresh-clone preview section");
includes(readmeSource, "npm ci", "README fresh-clone npm dependency install");
includes(readmeSource, "examples/status.example.json", "README bundled public status fixture");
includes(readmeSource, "without `view=share`", "README home smoke canonical route expectation");

for (const [source, sourceLabel] of [
  [readmeSource, "dashboard README"],
  [contractSource, "status data contract"],
] as const) {
  includes(source, "control-plane home", `${sourceLabel} canonical home`);
  includes(source, "?view=ops", `${sourceLabel} ops fallback`);
  includes(source, "view=share", `${sourceLabel} legacy share compatibility`);
}

includes(contractSource, "translate raw machine fields", "status contract translation expectation");
includes(contractSource, "single_surface", "status contract raw machine token example");

console.log("home-route smoke ok");
