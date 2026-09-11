export const defaultConfiguredSshHostsUrl = "/ssh-hosts";

export type ConfiguredSshHost = {
  alias: string;
};

export type ConfiguredSshHostCatalog = {
  hosts: ConfiguredSshHost[];
  schemaVersion: "ssh_host_catalog_v0";
};

const safeAliasPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$/;

export function isConfiguredSshHostAlias(value: unknown): value is string {
  return typeof value === "string" && safeAliasPattern.test(value.trim());
}

export function parseConfiguredSshHostCatalog(value: unknown): ConfiguredSshHostCatalog {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("SSH Host 列表响应无效。");
  }
  const payload = value as Record<string, unknown>;
  if (payload.ok !== true || payload.schema_version !== "ssh_host_catalog_v0" || !Array.isArray(payload.hosts)) {
    throw new Error("SSH Host 列表协议不兼容，请更新本机 LoopX 服务。");
  }
  const seen = new Set<string>();
  const hosts = payload.hosts.flatMap((value) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) return [];
    const alias = String((value as Record<string, unknown>).alias ?? "").trim();
    if (!isConfiguredSshHostAlias(alias) || seen.has(alias)) return [];
    seen.add(alias);
    return [{ alias }];
  });
  return { hosts, schemaVersion: "ssh_host_catalog_v0" };
}

export async function fetchConfiguredSshHosts(
  fetcher: typeof fetch = fetch,
  url = defaultConfiguredSshHostsUrl,
): Promise<ConfiguredSshHostCatalog> {
  const response = await fetcher(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`无法读取本机 SSH Host（HTTP ${response.status}）。`);
  return parseConfiguredSshHostCatalog(await response.json());
}

export function configuredSshTunnelDraft(hostAlias: string, localPortValue: string) {
  const alias = hostAlias.trim();
  if (!isConfiguredSshHostAlias(alias)) return { error: "请选择有效的 SSH Host。" } as const;
  const localPort = Number(localPortValue);
  if (!Number.isInteger(localPort) || localPort < 1024 || localPort > 65535) {
    return { error: "本地端口必须是 1024–65535 之间的整数。" } as const;
  }
  return {
    command: `ssh -N -L ${localPort}:127.0.0.1:8766 ${alias}`,
    hostAlias: alias,
    label: alias,
    statusUrl: `http://127.0.0.1:${localPort}/status.json`,
  } as const;
}


export const defaultSshSourceEnsureUrl = "/api/ssh-source/ensure";
export const defaultSshGoalLifecycleUrl = "/api/ssh-source/goal-lifecycle";

export type EnsureSshSourceResult = {
  ok: true;
  status_url: string;
  tunnel_required: boolean;
  remote_started: boolean;
};

export async function ensureSshSource(
  hostAlias: string,
  localPort: string | number,
): Promise<EnsureSshSourceResult> {
  const response = await fetch(defaultSshSourceEnsureUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ host_alias: hostAlias, local_port: Number(localPort) }),
  });
  const payload = (await response.json().catch(() => null)) as
    | (EnsureSshSourceResult & { error?: string })
    | null;
  if (!response.ok) {
    throw new Error(payload?.error ?? "无法建立 SSH 隧道来源。");
  }
  if (!payload?.ok) {
    throw new Error("无法建立 SSH 隧道来源。");
  }
  return payload;
}

export type RemoteGoalLifecycleResult = {
  activation_state: "active" | "stopped";
  changed: boolean;
  goal_id: string;
  host_alias: string;
  ok: true;
  operation: "stop" | "resume";
  projection_verified: true;
  schema_version: "loopx_remote_goal_lifecycle_v1";
};

export async function applyRemoteGoalLifecycle(
  hostAlias: string,
  goalId: string,
  operation: "stop" | "resume",
  reason: string,
  fetcher: typeof fetch = fetch,
): Promise<RemoteGoalLifecycleResult> {
  const response = await fetcher(defaultSshGoalLifecycleUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ goal_id: goalId, host_alias: hostAlias, operation, reason }),
  });
  const payload = (await response.json().catch(() => null)) as
    | (RemoteGoalLifecycleResult & { error?: string })
    | null;
  if (!response.ok) {
    throw new Error(payload?.error ?? "无法更新远端 Goal 生命周期。");
  }
  if (
    !payload?.ok
    || payload.schema_version !== "loopx_remote_goal_lifecycle_v1"
    || payload.goal_id !== goalId
    || payload.host_alias !== hostAlias
    || payload.operation !== operation
    || payload.activation_state !== (operation === "stop" ? "stopped" : "active")
    || payload.projection_verified !== true
  ) {
    throw new Error("远端 Goal 生命周期回读未验证。");
  }
  return payload;
}
