import {
  Navigate,
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { z } from "zod";

import { DashboardPage } from "./views/dashboard-page";
import { DeprecatedFrontstageOpsPage } from "./views/deprecated/frontstage-ops-page";
import { FrontstageDeveloperPage } from "./views/frontstage-developer-page";
import { FrontstagePage } from "./views/frontstage-page";
import { BenchmarkStudyPage } from "./views/benchmark-study-page";

const searchSchema = z.object({
  goalId: z.string().optional().default(""),
  statusUrl: z.string().optional().default(""),
});

const frontstageSearchSchema = z.object({
  goalId: z.string().optional().default(""),
  mode: z.enum(["showcase", "developer", "ops"]).optional().default("showcase"),
  statusUrl: z.string().optional().default(""),
  todoLane: z.enum(["all", "user", "agent"]).optional().default("all"),
  todoQuery: z.string().optional().default(""),
});

const deprecatedFrontstageOpsSearchSchema = frontstageSearchSchema.omit({ mode: true });

const benchmarkStudySearchSchema = z.object({
  dashboardUrl: z.string().optional().default(""),
  view: z.enum(["campaign", "arms", "cases", "runs"]).optional().default("campaign"),
  runId: z.string().optional().default(""),
});

function FrontstageRoutePage() {
  const search = frontstageRoute.useSearch();
  if (search.mode === "ops") {
    return (
      <Navigate
        replace
        search={{
          goalId: search.goalId,
          statusUrl: search.statusUrl,
          todoLane: search.todoLane,
          todoQuery: search.todoQuery,
        }}
        to="/deprecated/frontstage/ops"
      />
    );
  }
  return <FrontstagePage search={search} />;
}

function DeprecatedFrontstageOpsRoutePage() {
  const search = deprecatedFrontstageOpsRoute.useSearch();
  const navigate = deprecatedFrontstageOpsRoute.useNavigate();
  return (
    <DeprecatedFrontstageOpsPage
      onNavigate={(next) => {
        return navigate({ search: (current) => ({ ...current, ...next }) });
      }}
      onOpenShowcase={() => navigate({
        search: { goalId: "", mode: "showcase", statusUrl: "", todoLane: "all", todoQuery: "" },
        to: "/frontstage",
      })}
      search={search}
    />
  );
}

export const rootRoute = createRootRoute({
  component: () => <Outlet />,
  errorComponent: () => <main role="alert" className="p-8">
    <h1>页面暂时无法显示 / Page unavailable</h1>
    <p>请重新加载页面；这不会执行任务。 / Reloading does not execute tasks.</p>
    <button type="button" onClick={() => window.location.reload()}>重新加载 / Reload</button>
  </main>,
});

export const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  validateSearch: (search) => searchSchema.parse(search),
  component: DashboardPage,
});

export const frontstageRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/frontstage",
  validateSearch: (search) => frontstageSearchSchema.parse(search),
  component: FrontstageRoutePage,
});

export const deprecatedFrontstageOpsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/deprecated/frontstage/ops",
  validateSearch: (search) => deprecatedFrontstageOpsSearchSchema.parse(search),
  component: DeprecatedFrontstageOpsRoutePage,
});

export const frontstageDeveloperRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/frontstage/developer",
  component: FrontstageDeveloperPage,
});

export const benchmarkStudyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/benchmarks/study",
  validateSearch: (search) => benchmarkStudySearchSchema.parse(search),
  component: BenchmarkStudyPage,
});

const routeTree = rootRoute.addChildren([
  dashboardRoute,
  frontstageRoute,
  deprecatedFrontstageOpsRoute,
  frontstageDeveloperRoute,
  benchmarkStudyRoute,
]);

function routerBasepathFromViteBase(baseUrl: string) {
  if (!baseUrl || baseUrl === "/" || baseUrl === "./") {
    return "/";
  }
  const withLeadingSlash = baseUrl.startsWith("/") ? baseUrl : `/${baseUrl}`;
  return withLeadingSlash.replace(/\/+$/, "") || "/";
}

export const router = createRouter({
  routeTree,
  basepath: routerBasepathFromViteBase(import.meta.env.BASE_URL),
  trailingSlash: "preserve",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
