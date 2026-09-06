import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Check,
  ExternalLink,
  Loader2,
  MessageSquareText,
  Plus,
  Search,
  Settings2,
  Unlink,
  X,
} from "lucide-react";

import {
  ChatApiError,
  cancelLarkAppSetup,
  connectLarkGoalTopic,
  disconnectLarkGoalTopic,
  fetchLarkAppSetup,
  fetchLarkApps,
  fetchLarkConnections,
  fetchLarkGroupChats,
  startLarkAppSetup,
  type LarkApp,
  type LarkAppSetup,
  type LarkCaptureScope,
  type LarkGoalConnection,
  type LarkGroupChat,
  type LarkIngressMode,
  type LarkReplyMode,
} from "../../data/chat";
import { useWorkspaceI18n, type WorkspaceTranslate } from "./i18n";
import type { WorkspaceGoal } from "./personal-workspace-model";

type Tab = "apps" | "connections";

function ingressPresentation(mode: LarkIngressMode, t: WorkspaceTranslate): { label: string; detail: string } {
  return {
    live_steering: {
      label: t("lark.ingressSteering"),
      detail: t("lark.ingressSteeringDescription"),
    },
    session_queue: {
      label: t("lark.ingressQueue"),
      detail: t("lark.ingressQueueDescription"),
    },
    async_inbox: {
      label: t("lark.ingressAsync"),
      detail: t("lark.ingressAsyncDescription"),
    },
    direct_session: {
      label: t("lark.ingressLegacy"),
      detail: t("lark.ingressLegacyDescription"),
    },
  }[mode];
}

function larkConnectionHealth(connection: LarkGoalConnection, t: WorkspaceTranslate): { label: string; detail: string; ready: boolean } {
  if (connection.listener_status === "starting") {
    return { label: t("lark.health.starting"), detail: t("lark.health.startingDetail"), ready: false };
  }
  if (connection.listener_status === "retrying") {
    return { label: t("lark.health.retrying"), detail: t("lark.health.retryingDetail"), ready: false };
  }
  if (connection.listener_status === "stopped" || connection.listener_status === null) {
    return { label: t("lark.health.notStarted"), detail: t("lark.health.notStartedDetail"), ready: false };
  }
  if (connection.last_event_status === "message_context_permission_required") {
    return { label: t("lark.health.messageContextPermission"), detail: t("lark.health.messageContextPermissionDetail"), ready: false };
  }
  if (connection.last_event_status === "processing_failed") {
    return { label: t("lark.health.processingFailed"), detail: t("lark.health.processingFailedDetail"), ready: false };
  }
  if (connection.health_error_code === "invalid_routing_state") {
    return { label: t("lark.health.invalidRouting"), detail: t("lark.health.invalidRoutingDetail"), ready: false };
  }
  if (connection.last_event_status === "queued_for_agent") {
    return {
      label: t("lark.health.queued"),
      detail: t("lark.health.queuedDetail", { agent: connection.agent_id ?? t("lark.targetAgent") }),
      ready: true,
    };
  }
  if (connection.last_event_status === "ignored" && connection.last_event_reason === "not_addressed") {
    return {
      label: t("lark.health.notAddressed"),
      detail: t("lark.health.notAddressedDetail"),
      ready: true,
    };
  }
  if (connection.last_event_status === "ignored" && connection.last_event_reason === "self_message") {
    return { label: t("lark.health.listening"), detail: t("lark.health.ignoredSelf"), ready: true };
  }
  if (
    connection.health_error_code === "lark_event_route_mismatch"
    || ["chat_mismatch", "topic_mismatch", "route_ambiguous"].includes(connection.last_event_reason ?? "")
  ) {
    return {
      label: connection.last_event_reason === "route_ambiguous"
        ? t("lark.health.routeAmbiguous")
        : t("lark.health.routeMismatch"),
      detail: connection.last_event_reason === "route_ambiguous"
        ? t("lark.health.routeAmbiguousDetail")
        : t("lark.health.routeMismatchDetail"),
      ready: false,
    };
  }
  if (["invalid_event", "binding_unavailable"].includes(connection.last_event_reason ?? "")) {
    return {
      label: t("lark.health.routeUnavailable"),
      detail: t("lark.health.routeUnavailableDetail"),
      ready: false,
    };
  }
  if (connection.last_event_status === "replied_and_acknowledged") {
    return { label: t("lark.health.listening"), detail: t("lark.health.eventProcessed", { events: connection.event_count, replies: connection.replied_count }), ready: true };
  }
  if (connection.health_error_code === "lark_event_delivery_unverified" || connection.event_count === 0) {
    return {
      label: t("lark.health.eventUnverified"),
      detail: t("lark.health.eventUnverifiedDetail"),
      ready: false,
    };
  }
  return {
    label: connection.reply_ready ? t("lark.health.listening") : t("lark.health.unavailable"),
    detail: t("lark.health.lastStatus", { status: connection.last_event_status ?? t("lark.health.waiting") }),
    ready: connection.reply_ready,
  };
}

function larkGroupHistoryPermissionUrl(connection: LarkGoalConnection): string | null {
  return connection.history_permission_guidance?.api_document_url ?? null;
}

function larkErrorMessage(cause: unknown, fallback: string, t: WorkspaceTranslate): string {
  if (cause instanceof ChatApiError) {
    const code = String(cause.payload.error_code ?? "");
    const messages: Record<string, string> = {
      lark_cli_not_installed: t("lark.error.cliMissing"),
      lark_cli_not_executable: t("lark.error.cliExecutable"),
      lark_cli_start_failed: t("lark.error.cliStart"),
      lark_message_permissions_required: t("lark.error.messagePermissions"),
      lark_app_required: t("lark.error.appRequired"),
      invalid_lark_app: t("lark.error.invalidApp"),
      lark_group_lookup_failed: t("lark.error.groupLookup"),
      provider_api_failed: t("lark.error.provider"),
    };
    return messages[code] ?? cause.message;
  }
  return cause instanceof Error ? cause.message : fallback;
}

export function LarkSettingsPage({
  embedded = false,
  focusGoalConnection = false,
  goals,
  initialGoalId,
  onChanged,
  onClose,
}: {
  embedded?: boolean;
  focusGoalConnection?: boolean;
  goals: WorkspaceGoal[];
  initialGoalId?: string | null;
  onChanged?: () => void;
  onClose: () => void;
}) {
  const { t } = useWorkspaceI18n();
  const [tab, setTab] = useState<Tab>("connections");
  const [apps, setApps] = useState<LarkApp[]>([]);
  const [connections, setConnections] = useState<LarkGoalConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [modalOpen, setModalOpen] = useState(focusGoalConnection);
  const [appRef, setAppRef] = useState("");
  const [goalId, setGoalId] = useState(initialGoalId ?? goals[0]?.goalId ?? "");
  const [chatQuery, setChatQuery] = useState("");
  const [chats, setChats] = useState<LarkGroupChat[]>([]);
  const [chatId, setChatId] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatLoadError, setChatLoadError] = useState<string | null>(null);
  const [captureScope, setCaptureScope] = useState<LarkCaptureScope>("addressed_only");
  const [ingressMode, setIngressMode] = useState<LarkIngressMode>("async_inbox");
  const [replyMode, setReplyMode] = useState<LarkReplyMode>("topic_reply");
  const [agentId, setAgentId] = useState("");
  const [connectAllAgents, setConnectAllAgents] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [editingGoalId, setEditingGoalId] = useState<string | null>(null);
  const [disconnectConnectionId, setDisconnectConnectionId] = useState<string | null>(null);
  const [setupOpen, setSetupOpen] = useState(false);
  const [setupAppRef, setSetupAppRef] = useState("loopx-workspace-bot");
  const [setupBrand, setSetupBrand] = useState<"feishu" | "lark">("feishu");
  const [setupSnapshot, setSetupSnapshot] = useState<LarkAppSetup | null>(null);
  const [setupStarting, setSetupStarting] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const setupPopup = useRef<Window | null>(null);
  const openedSetupUrl = useRef<string | null>(null);
  const focusedGoalOpened = useRef(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [nextApps, nextConnections] = await Promise.all([
        fetchLarkApps(),
        fetchLarkConnections(),
      ]);
      setApps(nextApps);
      setConnections(nextConnections);
      setAppRef((current) => current || nextApps.find((app) => app.reply_ready)?.app_ref || nextApps.find((app) => app.ready)?.app_ref || nextApps[0]?.app_ref || "");
    } catch (cause) {
      setError(larkErrorMessage(cause, t("lark.error.configuration"), t));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    if (!focusGoalConnection || loading || focusedGoalOpened.current || !initialGoalId) return;
    focusedGoalOpened.current = true;
    const connection = connections.find((item) => item.goal_id === initialGoalId);
    if (connection) openConnectionEditor(connection);
    else openConnect(goals.find((goal) => goal.goalId === initialGoalId));
  }, [connections, focusGoalConnection, goals, initialGoalId, loading]);

  useEffect(() => {
    if (!modalOpen || !appRef) {
      setChats([]);
      setChatId("");
      setChatLoading(false);
      setChatLoadError(null);
      return;
    }
    let cancelled = false;
    setChatLoading(true);
    setChatLoadError(null);
    const timer = window.setTimeout(() => {
      void fetchLarkGroupChats(appRef, chatQuery)
        .then((items) => {
          if (cancelled) return;
          setChats(items);
          setChatId((current) => items.some((item) => item.chat_id === current) ? current : items[0]?.chat_id ?? "");
        })
        .catch((cause: unknown) => {
          if (!cancelled) {
            setChats([]);
            setChatId("");
            setChatLoadError(larkErrorMessage(cause, t("lark.error.groupLoad"), t));
          }
        })
        .finally(() => {
          if (!cancelled) setChatLoading(false);
        });
    }, 180);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [appRef, chatQuery, modalOpen]);

  useEffect(() => {
    if (!setupOpen || !setupSnapshot || ["ready", "failed", "cancelled"].includes(setupSnapshot.status)) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void fetchLarkAppSetup(setupSnapshot.setup_id)
        .then(async (snapshot) => {
          if (cancelled) return;
          setSetupSnapshot(snapshot);
          if (snapshot.verification_url && openedSetupUrl.current !== snapshot.verification_url) {
            openedSetupUrl.current = snapshot.verification_url;
            if (setupPopup.current && !setupPopup.current.closed) {
              setupPopup.current.location.href = snapshot.verification_url;
            }
          }
          if (snapshot.status === "ready") {
            await refresh();
            setAppRef(snapshot.app_ref);
            setSetupOpen(false);
          }
          if (snapshot.status === "failed") {
            setSetupError(snapshot.error ?? t("lark.error.appCreate"));
          }
        })
        .catch((cause: unknown) => {
          if (!cancelled) setSetupError(larkErrorMessage(cause, t("lark.error.setupPoll"), t));
        });
    }, 650);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [setupOpen, setupSnapshot]);

  const selectedGoal = goals.find((goal) => goal.goalId === goalId);
  const fallbackGoalAgents = selectedGoal?.agentId
    ? [{ agentId: selectedGoal.agentId, label: selectedGoal.agentLabel ?? selectedGoal.agentId }]
    : [];
  const goalAgents = selectedGoal?.agentLanes?.length
    ? selectedGoal.agentLanes
    : fallbackGoalAgents;
  const selectedAgentAvailable = goalAgents.some((agent) => agent.agentId === agentId);
  let targetAgentIds: string[] = [];
  if (connectAllAgents) targetAgentIds = goalAgents.map((agent) => agent.agentId);
  else if (selectedAgentAvailable) targetAgentIds = [agentId];
  let connectActionLabel = t("lark.connect");
  if (editingGoalId) connectActionLabel = t("lark.saveConnection");
  else if (connectAllAgents) connectActionLabel = t("lark.connectAllAgentsAction", { count: targetAgentIds.length });
  const selectedApp = apps.find((app) => app.app_ref === appRef);
  const selectedChat = chats.find((chat) => chat.chat_id === chatId);
  const filteredConnections = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase();
    if (!keyword) return connections;
    return connections.filter((connection) => [
      connection.app_label,
      connection.chat_name,
      connection.goal_title,
      connection.topic_name,
    ].some((value) => value.toLocaleLowerCase().includes(keyword)));
  }, [connections, query]);

  function openConnect(goal?: WorkspaceGoal) {
    const nextGoal = goal ?? goals.find((item) => item.goalId === initialGoalId) ?? goals[0];
    setEditingGoalId(null);
    setGoalId(nextGoal?.goalId ?? "");
    setAgentId(nextGoal?.agentId ?? "");
    setConnectAllAgents(false);
    setCaptureScope("addressed_only");
    setIngressMode("async_inbox");
    setReplyMode("topic_reply");
    setChatQuery("");
    setConnectError(null);
    setModalOpen(true);
  }

  function openConnectionEditor(connection: LarkGoalConnection) {
    setEditingGoalId(connection.goal_id);
    setAppRef(connection.app_ref);
    setGoalId(connection.goal_id);
    setAgentId(connection.agent_id ?? goals.find((goal) => goal.goalId === connection.goal_id)?.agentId ?? "");
    setConnectAllAgents(false);
    setCaptureScope(connection.capture_scope);
    setIngressMode(connection.ingress_mode === "direct_session" ? "session_queue" : connection.ingress_mode);
    setReplyMode(connection.reply_mode);
    setChatQuery(connection.chat_name);
    setConnectError(null);
    setModalOpen(true);
  }

  function openSetup() {
    setSetupSnapshot(null);
    setSetupError(null);
    openedSetupUrl.current = null;
    setSetupOpen(true);
  }

  async function startSetup() {
    if (setupStarting || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/.test(setupAppRef)) return;
    setSetupStarting(true);
    setSetupError(null);
    openedSetupUrl.current = null;
    setupPopup.current = window.open(window.location.href, "_blank");
    try {
      const snapshot = await startLarkAppSetup({ appRef: setupAppRef, brand: setupBrand });
      setSetupSnapshot(snapshot);
    } catch (cause) {
      setupPopup.current?.close();
      setSetupError(larkErrorMessage(cause, t("lark.error.setupStart"), t));
    } finally {
      setSetupStarting(false);
    }
  }

  async function closeSetup() {
    const snapshot = setupSnapshot;
    setSetupOpen(false);
    setupPopup.current?.close();
    if (snapshot && !["ready", "failed", "cancelled"].includes(snapshot.status)) {
      try {
        await cancelLarkAppSetup(snapshot.setup_id);
      } catch {
        // The local setup process may already have completed while the modal closed.
      }
    }
  }

  async function connect() {
    if (!appRef || !goalId || !selectedChat || targetAgentIds.length === 0 || connecting) return;
    setConnecting(true);
    setConnectError(null);
    try {
      const input = {
        agentBindings: targetAgentIds.map((targetAgentId) => ({ agentId: targetAgentId, appRef })),
        captureScope,
        chatId: selectedChat.chat_id,
        chatName: selectedChat.chat_name,
        goalId,
        incomingMode: captureScope === "configured_chat_all" ? "all" as const : "mentions" as const,
        ingressMode,
        replyMode,
      } as const;
      const preview = await connectLarkGoalTopic({ ...input, execute: false });
      if (!preview.ok) throw new ChatApiError(preview.public_summary ?? preview.blocker ?? t("lark.error.bindPreview"), { error_code: preview.blocker ?? "provider_api_failed" });
      const result = await connectLarkGoalTopic({ ...input, execute: true });
      if (!result.ok) throw new ChatApiError(result.public_summary ?? result.blocker ?? t("lark.error.bind"), { error_code: result.blocker ?? "provider_api_failed" });
      setModalOpen(false);
      await refresh();
      onChanged?.();
    } catch (cause) {
      setConnectError(larkErrorMessage(cause, t("lark.error.bind"), t));
    } finally {
      setConnecting(false);
    }
  }

  async function disconnect(goal: string, connectionId: string) {
    if (disconnectConnectionId !== connectionId) {
      setDisconnectConnectionId(connectionId);
      return;
    }
    try {
      await disconnectLarkGoalTopic(goal, connectionId);
      setDisconnectConnectionId(null);
      await refresh();
      onChanged?.();
    } catch (cause) {
      setError(larkErrorMessage(cause, t("lark.error.disconnect"), t));
    }
  }

  return (
    <section className={`personal-lark-settings${embedded ? " is-embedded" : ""}`} aria-label={t("lark.configuration")}>
      {embedded ? null : (
        <header className="personal-lark-header">
          <div>
            <small>{t("settings.goalConnections")}</small>
            <h1>Lark</h1>
            <p>{t("lark.description")}</p>
          </div>
          <button aria-label={t("lark.closeSettings")} className="personal-icon-button" onClick={onClose} type="button"><X size={18} /></button>
        </header>
      )}

      <nav className="personal-lark-tabs" aria-label={t("lark.management")}>
        <button aria-current={tab === "apps" ? "page" : undefined} onClick={() => setTab("apps")} type="button">{t("lark.apps")} <span>{loading ? "…" : apps.length}</span></button>
        <button aria-current={tab === "connections" ? "page" : undefined} onClick={() => setTab("connections")} type="button">{t("lark.connections")} <span>{loading ? "…" : connections.length}</span></button>
      </nav>
      {error ? <p className="personal-notification-error">{error}</p> : null}
      {loading ? <div className="personal-lark-loading"><Loader2 className="is-spinning" size={18} />{t("lark.loading")}</div> : null}

      {!loading && tab === "apps" ? (
        <div className="personal-lark-apps">
          <div className="personal-lark-app-toolbar"><span>{t("lark.reusableApps", { count: apps.length })}</span><button className="personal-primary-action" onClick={openSetup} type="button"><Plus size={16} />{t("lark.newApp")}</button></div>
          <div className="personal-lark-app-grid">
            {apps.map((app) => (
              <article className="personal-lark-app-card" key={app.app_ref}>
                <span className="personal-lark-app-avatar"><Bot size={19} /></span>
                <div><strong>{app.label}</strong><small>{app.brand} · lark-cli profile</small></div>
                <em className={app.reply_ready ? "is-ready" : "is-off"}>{app.reply_ready ? t("lark.autoReplyReady") : app.ready ? t("lark.needsMessagePermissions") : t("lark.needsSetup")}</em>
                <p>{t("lark.goalConnections", { count: connections.filter((connection) => connection.app_ref === app.app_ref).length })}{app.ready && !app.reply_ready ? ` · ${t("lark.autoReplyUnavailable")}` : ""}</p>
              </article>
            ))}
            {apps.length === 0 ? <p className="personal-lark-empty">{t("lark.noProfiles")}</p> : null}
          </div>
        </div>
      ) : null}

      {!loading && tab === "connections" ? (
        <div className="personal-lark-connections">
          <div className="personal-lark-toolbar">
            <label><Search size={16} /><input aria-label={t("lark.searchConnections")} onChange={(event) => setQuery(event.target.value)} placeholder={t("lark.searchPlaceholder")} type="search" value={query} /></label>
            <button className="personal-primary-action" disabled={apps.length === 0 || goals.length === 0} onClick={() => openConnect()} type="button"><Plus size={16} />{t("lark.connectApp")}</button>
          </div>
          <div className="personal-lark-table" role="table" aria-label={t("lark.goalTopicConnections")}>
            <div className="personal-lark-table-head" role="row"><span>{t("lark.connection")}</span><span>{t("common.goal")}</span><span>{t("lark.capture")}</span><span>{t("lark.processing")}</span><span>{t("common.actions")}</span></div>
            {filteredConnections.map((connection) => (
              <div className="personal-lark-table-row" key={connection.connection_id} role="row">
                <span>
                  <strong>{connection.chat_name}</strong>
                  <small>{connection.app_label} · {larkConnectionHealth(connection, t).label}</small>
                  <small>{larkConnectionHealth(connection, t).detail}</small>
                  {connection.health_error_code === "lark_event_delivery_unverified" ? (
                    <a href="https://open.feishu.cn/document/server-docs/im-v1/message/events/receive?lang=zh-CN" rel="noreferrer" target="_blank"><ExternalLink size={12} />{t("lark.openEventSettings")}</a>
                  ) : null}
                  {larkGroupHistoryPermissionUrl(connection) ? (
                    <a href={larkGroupHistoryPermissionUrl(connection) ?? undefined} rel="noreferrer" target="_blank"><ExternalLink size={12} />{t("lark.historyPermission")}</a>
                  ) : null}
                </span>
                <span><strong>{connection.goal_title}</strong><small># {connection.topic_name}</small></span>
                <span>{connection.capture_scope === "addressed_only" ? t("lark.mentionsOnly") : t("lark.allTopicMessages")}</span>
                <span><strong>{ingressPresentation(connection.ingress_mode, t).label}</strong><small>{connection.agent_id ?? ingressPresentation(connection.ingress_mode, t).detail}</small></span>
                <span className="personal-lark-row-actions">
                  <button aria-label={t("lark.settingsConfigure", { goal: connection.goal_title })} onClick={() => openConnectionEditor(connection)} type="button"><Settings2 size={15} /></button>
                  <button aria-label={t("lark.settingsDisconnect", { goal: connection.goal_title })} className={disconnectConnectionId === connection.connection_id ? "is-confirm" : ""} onClick={() => void disconnect(connection.goal_id, connection.connection_id)} type="button"><Unlink size={15} />{disconnectConnectionId === connection.connection_id ? t("common.confirm") : null}</button>
                </span>
              </div>
            ))}
            {filteredConnections.length === 0 ? <p className="personal-lark-empty">{t("lark.noConnections")}</p> : null}
          </div>
        </div>
      ) : null}

      {modalOpen ? (
        <div className="personal-lark-modal-backdrop" role="presentation">
          <section aria-labelledby="connect-lark-title" aria-modal="true" className="personal-lark-modal" role="dialog">
            <header><div><small>Goal Topic connection</small><h2 id="connect-lark-title">{editingGoalId ? t("lark.editConnection") : t("lark.connectApp")}</h2></div><button aria-label={t("lark.closeConnection")} onClick={() => setModalOpen(false)} type="button"><X size={18} /></button></header>
            <label><span>{t("lark.appProfile")}</span><select aria-label={t("lark.appProfile")} disabled={loading} onChange={(event) => { if (event.target.value === "__register__") openSetup(); else setAppRef(event.target.value); }} value={appRef}>{loading ? <option value="">{t("lark.appLoading")}</option> : <>{apps.map((app) => <option disabled={!app.ready} key={app.app_ref} value={app.app_ref}>{app.label}{app.reply_ready ? "" : app.ready ? ` · ${t("lark.needsMessagePermissions")}` : ` · ${t("lark.needsSetup")}`}</option>)}<option value="__register__">{t("lark.registerAnother")}</option></>}</select></label>
            {selectedApp?.ready && !selectedApp.reply_ready ? <div className="personal-lark-group-state is-error" role="alert">{t("lark.appPermissions")}</div> : null}
            <label>
              <span>{t("lark.groupChat")}</span>
              <input aria-label={t("lark.groupSearch")} onChange={(event) => setChatQuery(event.target.value)} placeholder={t("lark.groupSearch")} type="search" value={chatQuery} />
              {chatLoading ? <div className="personal-lark-group-state" role="status"><Loader2 className="is-spinning" size={15} />{t("lark.groupLoading")}</div> : null}
              {!chatLoading && chatLoadError ? <div className="personal-lark-group-state is-error" role="alert">{chatLoadError}</div> : null}
              {!chatLoading && !chatLoadError && chats.length === 0 ? <div className="personal-lark-group-state" role="status">{t("lark.groupEmpty")}</div> : null}
              {!chatLoading && !chatLoadError && chats.length > 0 ? <select aria-label={t("lark.groupChat")} onChange={(event) => setChatId(event.target.value)} value={chatId}>{chats.map((chat) => <option key={chat.chat_id} value={chat.chat_id}>{chat.chat_name}</option>)}</select> : null}
            </label>
            <label><span>{t("lark.bindGoal")}</span><select aria-label={t("lark.bindGoal")} onChange={(event) => { const nextGoalId = event.target.value; setGoalId(nextGoalId); setAgentId(goals.find((goal) => goal.goalId === nextGoalId)?.agentId ?? ""); }} value={goalId}>{goals.map((goal) => <option key={goal.goalId} value={goal.goalId}>{goal.title}</option>)}</select></label>
            <label className="personal-lark-check"><input checked readOnly type="checkbox" /><span><strong>{t("lark.createAutomatically")}</strong><small>{t("lark.createAutomaticallyDescription")}</small></span></label>
            <label><span>{t("lark.topicPreview")}</span><div className="personal-lark-topic-preview"><MessageSquareText size={15} /># {selectedGoal?.title ?? selectedGoal?.goalId ?? "Goal"}</div></label>
            <label><span>{t("lark.captureScope")}</span><select aria-label={t("lark.captureScope")} onChange={(event) => setCaptureScope(event.target.value as LarkCaptureScope)} value={captureScope}><option value="addressed_only">{t("lark.captureAddressed")}</option><option value="configured_chat_all">{t("lark.captureAll")}</option></select><small>{t("lark.captureScopeDescription")}</small></label>
            <fieldset aria-label={t("lark.agentIngress")} className="personal-lark-ingress"><legend>{t("lark.agentIngress")}</legend><div>{(["live_steering", "session_queue", "async_inbox"] as const).map((mode) => { const presentation = ingressPresentation(mode, t); return <label className={ingressMode === mode ? "is-active" : ""} key={mode}><input aria-label={presentation.label} checked={ingressMode === mode} name="lark-agent-ingress" onChange={() => setIngressMode(mode)} type="radio" value={mode} /><span><strong>{presentation.label}</strong><small>{presentation.detail}</small></span></label>; })}</div></fieldset>
            <label><span>{t("lark.targetAgent")}</span><select aria-label={t("lark.targetAgent")} onChange={(event) => setAgentId(event.target.value)} value={agentId}>
              {!selectedAgentAvailable ? <option disabled value={agentId}>{agentId ? t("lark.agentUnavailable", { agent: agentId }) : t("lark.noAgentConfigured")}</option> : null}
              {goalAgents.map((agent) => <option key={agent.agentId} value={agent.agentId}>{agent.label === agent.agentId ? agent.agentId : `${agent.label} · ${agent.agentId}`}</option>)}
            </select><small>{t("lark.targetAgentDescription")}</small></label>
            {!editingGoalId && goalAgents.length > 1 ? <label aria-label={t("lark.connectAllAgents")} className="personal-lark-check"><input checked={connectAllAgents} onChange={(event) => setConnectAllAgents(event.target.checked)} type="checkbox" /><span><strong>{t("lark.connectAllAgents")}</strong><small>{t("lark.connectAllAgentsDescription", { count: goalAgents.length })}</small></span></label> : null}
            {targetAgentIds.length === 0 ? <p className="personal-notification-error" role="alert">{t("lark.selectRegisteredAgent")}</p> : null}
            <label><span>{t("lark.replyMode")}</span><select aria-label={t("lark.replyMode")} onChange={(event) => setReplyMode(event.target.value as LarkReplyMode)} value={replyMode}><option value="topic_reply">{t("lark.topicReply")}</option></select><small>{t("lark.replyModeDescription")}</small></label>
            <p className="personal-lark-cardinality"><Check size={15} />{t("lark.cardinality")}</p>
            {connectError ? <p className="personal-notification-error" role="alert">{connectError}</p> : null}
            <footer><button className="personal-secondary-action" onClick={() => setModalOpen(false)} type="button">{t("lark.cancel")}</button><button className="personal-primary-action" disabled={loading || !appRef || !selectedApp?.reply_ready || !goalId || !chatId || targetAgentIds.length === 0 || connecting} onClick={() => void connect()} type="button">{connecting ? <Loader2 className="is-spinning" size={15} /> : null}{connectActionLabel}</button></footer>
          </section>
        </div>
      ) : null}

      {setupOpen ? (
        <div className="personal-lark-modal-backdrop is-setup" role="presentation">
          <section aria-labelledby="new-lark-app-title" aria-modal="true" className="personal-lark-modal personal-lark-setup-modal" role="dialog">
            <header><div><small>{t("lark.reusableWorkspaceApp")}</small><h2 id="new-lark-app-title">{t("lark.newApp")}</h2></div><button aria-label={t("lark.closeCreate")} onClick={() => void closeSetup()} type="button"><X size={18} /></button></header>
            {!setupSnapshot ? (
              <>
                <p className="personal-lark-setup-copy">{t("lark.setupCopy")}</p>
                <label><span>{t("lark.profileName")}</span><input aria-label={t("lark.profileName")} autoComplete="off" onChange={(event) => setSetupAppRef(event.target.value)} placeholder="loopx-workspace-bot" value={setupAppRef} /></label>
                <label><span>{t("lark.region")}</span><select aria-label={t("lark.region")} onChange={(event) => setSetupBrand(event.target.value as "feishu" | "lark")} value={setupBrand}><option value="feishu">Feishu</option><option value="lark">Lark</option></select></label>
                {setupAppRef && !/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/.test(setupAppRef) ? <p className="personal-notification-error">{t("lark.profileValidation")}</p> : null}
              </>
            ) : (
              <div className="personal-lark-setup-progress">
                <span className={`personal-lark-setup-icon is-${setupSnapshot.status}`}>{setupSnapshot.status === "ready" ? <Check size={22} /> : <Loader2 className={setupSnapshot.status === "failed" ? "" : "is-spinning"} size={22} />}</span>
                <div><strong>{setupSnapshot.status === "ready" ? t("lark.appCreated") : setupSnapshot.status === "failed" ? t("lark.appCreateFailed") : t("lark.waitingFeishu")}</strong><p>{setupSnapshot.status === "waiting_for_feishu" ? t("lark.waitingFeishuDescription") : setupSnapshot.status === "starting" ? t("lark.waitingLink") : setupSnapshot.error}</p></div>
                {setupSnapshot.verification_url ? <a href={setupSnapshot.verification_url} rel="noreferrer" target="_blank"><ExternalLink size={15} />{t("lark.reopenFeishu")}</a> : null}
              </div>
            )}
            {setupError ? <p className="personal-notification-error">{setupError}</p> : null}
            <footer><button className="personal-secondary-action" onClick={() => void closeSetup()} type="button">{t("lark.cancel")}</button>{!setupSnapshot ? <button className="personal-primary-action" disabled={setupStarting || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/.test(setupAppRef)} onClick={() => void startSetup()} type="button">{setupStarting ? <Loader2 className="is-spinning" size={15} /> : <ExternalLink size={15} />}{t("lark.continueFeishu")}</button> : null}</footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
