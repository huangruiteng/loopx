import { useEffect, useRef, useState } from "react";
import { Bot, ChevronDown, Eye, Info, Menu, RefreshCw, SlidersHorizontal } from "lucide-react";

import { localizedGoalState, useWorkspaceI18n } from "./i18n";
import type { ManagerChannelBinding, ManagerRuntimeSessionReadback } from "../../data/chat";
import type { WorkspaceAgentOption, WorkspaceGoal, WorkspaceGoalTab } from "./personal-workspace-model";
import { goalUsageLabel } from "./personal-workspace-model";
import { WorkspaceSelect } from "./workspace-select";

export function ChannelHeader({
  agents,
  managerChannelBinding,
  managerChatOpen,
  managerRuntime,
  mobileNavigationOpen,
  onOpenGoalCapabilities,
  onOpenGoalDetail,
  onOpenManagerChat,
  onRefresh,
  onOpenNavigation,
  onSelectGoalTab,
  onSelectAgent,
  onReturnManagerHome,
  refreshState,
  readOnlySourceLabel,
  selectedAgentId,
  selectedGoal,
  selectedGoalTab,
}: {
  agents: WorkspaceAgentOption[];
  managerChannelBinding?: ManagerChannelBinding | null;
  managerChatOpen?: boolean;
  managerRuntime?: ManagerRuntimeSessionReadback | null;
  mobileNavigationOpen?: boolean;
  onOpenGoalCapabilities?: () => void;
  onOpenGoalDetail?: () => void;
  onOpenManagerChat?: () => void;
  onRefresh?: () => void;
  onOpenNavigation?: () => void;
  onSelectGoalTab: (tab: WorkspaceGoalTab) => void;
  onSelectAgent: (agentId: string) => void;
  onReturnManagerHome?: () => void;
  refreshState?: "idle" | "loading" | "done" | "error";
  readOnlySourceLabel?: string;
  selectedAgentId: string;
  selectedGoal: WorkspaceGoal | null;
  selectedGoalTab: WorkspaceGoalTab;
}) {
  const { locale, t } = useWorkspaceI18n();
  const [goalToolsOpen, setGoalToolsOpen] = useState(false);
  const goalToolsButtonRef = useRef<HTMLButtonElement | null>(null);
  const goalToolsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!goalToolsOpen) return undefined;
    function closeOnOutsidePointer(event: PointerEvent) {
      if (!goalToolsRef.current?.contains(event.target as Node)) setGoalToolsOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setGoalToolsOpen(false);
        goalToolsButtonRef.current?.focus();
      }
    }
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [goalToolsOpen]);

  useEffect(() => setGoalToolsOpen(false), [selectedGoal?.goalId]);

  function runGoalTool(action?: () => void) {
    setGoalToolsOpen(false);
    action?.();
  }

  const selectedGoalUsageLabel = selectedGoal
    ? goalUsageLabel(selectedGoal.usage, {
      cost: t("drawer.costShort"),
      duration: t("drawer.durationShort"),
      period24h: t("drawer.period24h"),
      period7d: t("drawer.period7d"),
      tokens: t("drawer.tokensShort"),
    })
    : null;
  // The chip reports the selected executor, whose credential pays for it, and
  // the resolved model, so an executor and a model that disagree are visible
  // instead of arriving as one silent configuration.
  const managerExecutionKindLabel = managerChannelBinding
    ? managerChannelBinding.executor_kind === "individual"
      ? t("header.managerExecutorKindIndividual")
      : managerChannelBinding.executor_kind === "managed"
        ? t("header.managerExecutorKindManaged")
        : t("header.managerExecutorKindRegistered")
    : null;
  const managerExecutionUnavailable = managerChannelBinding?.available === false;
  // Name the reason instead of one hardcoded host: the channel can hold the
  // managed host through its segment transport now, so "this channel needs
  // codex" would be both wrong and unactionable. An unknown reason stays
  // unclaimed rather than being rendered as a reason this build invented.
  const managerExecutionUnavailableReason = managerChannelBinding?.available === false
    ? managerChannelBinding.unavailable_reason
    : null;
  const managerExecutionUnavailableKey = managerExecutionUnavailableReason === "operator_credential_unconfigured"
    ? "header.managerExecutionUnavailableCredential"
    : managerExecutionUnavailableReason === "dsh_runtime_unavailable"
      ? "header.managerExecutionUnavailableRuntime"
      : managerExecutionUnavailableReason === "invalid_reasoning_effort"
        ? "header.managerExecutionUnavailableEffort"
        : "header.managerExecutionUnavailable";
  // The shipped default is one endpoint, so the chip names it and the one way
  // to move it; without this a steward the operator selected looks identical to
  // the one every machine runs, and the reason stays in the binding's typed
  // field instead of being invented here.
  const managerExecutionDefaultReason = managerChannelBinding
    && managerChannelBinding.executor_endpoint_source === "product_default"
    && managerChannelBinding.executor_endpoint_default_reason === "steward_channel_default"
    ? "header.managerEndpointStewardDefault"
    : null;

  return (
    <header className="personal-channel-header">
      <button aria-expanded={mobileNavigationOpen ?? false} aria-label={t("header.openGoalNavigation")} className="personal-icon-button personal-mobile-menu" onClick={onOpenNavigation} type="button"><Menu size={18} /></button>
      <div className="personal-channel-title">
        <h1>{selectedGoal?.title ?? t("header.manager")}</h1>
        {!selectedGoal && managerRuntime ? (
          <p>{managerRuntime.status === "ready"
            ? t("header.managerRuntime", {
              profile: managerRuntime.runtime_profile,
              sandbox: managerRuntime.sandbox,
            })
            : t("header.managerRuntimeFallback", {
              profile: managerRuntime.runtime_profile,
              sandbox: managerRuntime.sandbox,
            })}</p>
        ) : null}
        {!selectedGoal && managerChannelBinding ? (
          <p className="personal-manager-execution">
            <span className={managerExecutionUnavailable ? "personal-execution-chip is-unavailable" : "personal-execution-chip"}>
              <span className="personal-execution-chip-endpoint">{managerChannelBinding.executor_endpoint}</span>
              {managerExecutionKindLabel ? <span className="personal-execution-chip-kind">{managerExecutionKindLabel}</span> : null}
              <span className="personal-execution-chip-model">{managerChannelBinding.model}</span>
            </span>
            {managerExecutionUnavailable ? (
              <span className="personal-execution-note">
                {t(managerExecutionUnavailableKey, {
                  executor: managerChannelBinding.executor_endpoint,
                  credential: managerChannelBinding.credential_env_var,
                })}
              </span>
            ) : null}
            {managerExecutionDefaultReason ? (
              <span className="personal-execution-rule-note">
                {t(managerExecutionDefaultReason, { executor: managerChannelBinding.executor_endpoint })}
              </span>
            ) : null}
          </p>
        ) : null}
        {selectedGoal ? <p>{selectedGoal.loadState ? t(selectedGoal.loadState === "error" ? "startup.goalError" : "startup.goalLoading") : `${selectedGoal.agentLaneCount && selectedGoal.agentLaneCount > 1
            ? t("header.workAgentCount", { count: selectedGoal.agentLaneCount })
            : selectedGoal.agentLabel ?? selectedGoal.agentId} · ${(selectedGoal.loadState ? t(selectedGoal.loadState === "error" ? "startup.goalError" : "startup.goalLoading") : localizedGoalState(selectedGoal.state, locale))}${selectedGoalUsageLabel ? ` · ${selectedGoalUsageLabel}` : ""} · ${selectedGoal.nextSentence}`}</p> : null}
      </div>
      {selectedGoal ? (
        <nav aria-label={t("header.goalView")} className="personal-goal-tabs">
          <button aria-current={selectedGoalTab === "chat" ? "page" : undefined} onClick={() => onSelectGoalTab("chat")} type="button">{t("header.chat")}</button>
          <button aria-current={selectedGoalTab === "tasks" ? "page" : undefined} onClick={() => onSelectGoalTab("tasks")} type="button">{t("header.tasks")}</button>
          <button aria-current={selectedGoalTab === "files" ? "page" : undefined} onClick={() => onSelectGoalTab("files")} type="button">{t("header.files")}</button>
        </nav>
      ) : (
        <nav aria-label={t("header.managerView")} className="personal-goal-tabs">
          <button aria-current={!managerChatOpen ? "page" : undefined} onClick={onReturnManagerHome} type="button">{t("header.managerOverview")}</button>
          <button aria-current={managerChatOpen ? "page" : undefined} onClick={onOpenManagerChat} type="button">{t("header.chat")}</button>
        </nav>
      )}
      <div className="personal-channel-actions">
        {selectedGoal && onOpenGoalDetail && onOpenGoalCapabilities ? (
          <div className="personal-goal-tools" ref={goalToolsRef}>
            <button
              aria-expanded={goalToolsOpen}
              aria-haspopup="menu"
              aria-label={t("header.goalSettingsDescription")}
              className="personal-goal-tools-trigger"
              onClick={() => setGoalToolsOpen((open) => !open)}
              ref={goalToolsButtonRef}
              title={t("header.goalSettingsDescription")}
              type="button"
            >
              <SlidersHorizontal aria-hidden size={16} />
              <span>{t("header.goalSettings")}</span>
              <ChevronDown aria-hidden size={13} />
            </button>
            {goalToolsOpen ? (
              <fieldset aria-label={t("header.goalSettings")} className="personal-goal-tools-menu">
                <button onClick={() => runGoalTool(onOpenGoalDetail)} type="button">
                  <Info aria-hidden size={17} />
                  <span><strong>{t("header.goalDetails")}</strong></span>
                </button>
                <button onClick={() => runGoalTool(onOpenGoalCapabilities)} type="button">
                  <SlidersHorizontal aria-hidden size={17} />
                  <span><strong>{t("header.goalCapabilities")}</strong></span>
                </button>
              </fieldset>
            ) : null}
          </div>
        ) : null}
        {readOnlySourceLabel ? (
          <span className="personal-read-only-source" title={t("header.readOnlySourceDescription", { source: readOnlySourceLabel })}><Eye size={15} />{readOnlySourceLabel}<small>{t("common.readOnly")}</small></span>
        ) : (
          <WorkspaceSelect
            ariaLabel={t("header.selectChatRuntime")}
            className="personal-agent-select"
            icon={<Bot size={16} />}
            onChange={onSelectAgent}
            options={agents.map((agent) => ({
              disabled: !agent.available,
              label: `${agent.label}${agent.available ? "" : ` · ${t("header.agentUnavailable")}`}`,
              value: agent.agentId,
            }))}
            prefixLabel={t("header.chatRuntime")}
            value={selectedAgentId}
          />
        )}
        <span className="personal-live-indicator"><i />{t("header.live")}</span>
        {onRefresh ? (
          <span className={`personal-refresh-control is-${refreshState ?? "idle"}`}>
            {refreshState === "loading" ? <small>{t("header.refreshing")}</small> : refreshState === "done" ? <small>{t("header.refreshDone")}</small> : refreshState === "error" ? <small>{t("header.refreshFailed")}</small> : null}
            <button aria-label={refreshState === "loading" ? t("header.refreshing") : t("header.refresh")} className="personal-icon-button" disabled={refreshState === "loading"} onClick={onRefresh} type="button">
              <RefreshCw className={refreshState === "loading" ? "is-spinning" : undefined} size={17} />
            </button>
          </span>
        ) : null}
      </div>
    </header>
  );
}
