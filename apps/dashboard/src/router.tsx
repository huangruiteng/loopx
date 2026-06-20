import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { z } from "zod";

import { DashboardPage } from "./views/dashboard-page";
import { FrontstagePage } from "./views/frontstage-page";

const searchSchema = z.object({
  actionKind: z.enum(["all", "reward", "controller", "codex", "evidence", "health"]).optional().default("all"),
  goalId: z.string().optional().default(""),
  lane: z.enum(["all", "user", "codex", "watch"]).optional().default("all"),
  severity: z.enum(["all", "high", "action", "watch"]).optional().default("all"),
  statusUrl: z.string().optional().default(""),
  view: z.enum(["ops", "share"]).optional(),
});

export const rootRoute = createRootRoute({
  component: () => <Outlet />,
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
  component: FrontstagePage,
});

const routeTree = rootRoute.addChildren([dashboardRoute, frontstageRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
