import { StatusPayload, parseStatusPayload } from "./status";

export const expectedStatusContractSchemaVersion = 2;
export const fallbackStatusContractReloadHint = "scripts/macos-dashboard-launchagent.sh restart";

export type ResolvedFrontstageStatusUrl = {
  isLoopback: boolean;
  isRelative: boolean;
  url: string;
};

export type StatusContractFreshnessIssue = {
  reloadHint: string;
  schemaVersion: number;
};

export type LocalDashboardApiCapabilities = {
  controlPlaneApplyUrl: string | null;
  controlPlaneDryRunUrl: string | null;
  controlPlaneWriteEnabled: boolean;
  loopbackOnly: boolean;
  readOnlyDefault: boolean;
  rewardAppendUrl: string | null;
  rewardDryRunUrl: string | null;
  rewardWriteEnabled: boolean;
  source: string;
};

function isExplicitUrl(value: string) {
  return /^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(value) || value.startsWith("//");
}

export function isLoopbackHostname(hostname: string) {
  return ["localhost", "127.0.0.1", "::1", "[::1]"].includes(hostname);
}

export function resolveFrontstageOpsStatusUrl(value: string, baseHref: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return { error: "status URL is empty" };
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed, baseHref);
  } catch {
    return { error: "status URL is invalid" };
  }

  const isRelative = !isExplicitUrl(trimmed);
  const isLoopback = isLoopbackHostname(parsed.hostname);
  if (!isRelative && !isLoopback) {
    return {
      error: "Ops statusUrl must be relative or loopback; use showcase mode for public links.",
    };
  }

  return {
    source: {
      isLoopback,
      isRelative,
      url: trimmed,
    } satisfies ResolvedFrontstageStatusUrl,
  };
}

export async function fetchFrontstageStatusPayload(statusUrl: string) {
  const response = await fetch(statusUrl, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} while loading ${statusUrl}`);
  }
  return parseStatusPayload(await response.json());
}

export function statusContractFreshnessIssue(
  payload: StatusPayload,
  source: ResolvedFrontstageStatusUrl,
): StatusContractFreshnessIssue | null {
  if (!source.isLoopback) {
    return null;
  }
  const schemaVersion = payload.status_contract.schema_version ?? 0;
  if (schemaVersion >= expectedStatusContractSchemaVersion) {
    return null;
  }
  return {
    reloadHint: payload.status_contract.reload_hint || fallbackStatusContractReloadHint,
    schemaVersion,
  };
}

function localApiUrl(source: ResolvedFrontstageStatusUrl, path: string | null | undefined) {
  if (!path || !source.isLoopback) {
    return null;
  }
  try {
    const sourceUrl = new URL(source.url, window.location.href);
    const targetUrl = new URL(path, sourceUrl.origin);
    return isLoopbackHostname(targetUrl.hostname) ? targetUrl.toString() : null;
  } catch {
    return null;
  }
}

export function localDashboardApiCapabilities(
  payload: StatusPayload,
  source: ResolvedFrontstageStatusUrl,
): LocalDashboardApiCapabilities {
  const localApi = payload.local_dashboard_api;
  const rewardDryRunUrl = localApiUrl(source, localApi?.reward_dry_run_url);
  const rewardAppendUrl = localApiUrl(source, localApi?.reward_append_url);
  const controlPlaneDryRunUrl = localApiUrl(source, localApi?.configure_goal_dry_run_url);
  const controlPlaneApplyUrl = localApiUrl(source, localApi?.configure_goal_apply_url);
  const rewardWriteEnabled = Boolean(localApi?.reward_write_enabled && rewardAppendUrl);
  const controlPlaneWriteEnabled = Boolean(localApi?.control_plane_write_enabled && controlPlaneApplyUrl);

  return {
    controlPlaneApplyUrl,
    controlPlaneDryRunUrl,
    controlPlaneWriteEnabled,
    loopbackOnly: source.isLoopback,
    readOnlyDefault: !rewardWriteEnabled && !controlPlaneWriteEnabled,
    rewardAppendUrl,
    rewardDryRunUrl,
    rewardWriteEnabled,
    source: localApi?.source ?? "not advertised",
  };
}
