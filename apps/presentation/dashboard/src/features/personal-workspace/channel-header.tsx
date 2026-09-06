import { useEffect, useRef, useState } from "react";
import { Bot, ChevronDown, Eye, Info, Menu, RefreshCw, SlidersHorizontal } from "lucide-react";

import { localizedGoalState, useWorkspaceI18n } from "./i18n";
import type { WorkspaceAgentOption, WorkspaceGoal, WorkspaceGoalTab } from "./personal-workspace-model";
import { goalUsageLabel } from "./personal-workspace-model";
import { WorkspaceSelect } from "./workspace-select";

export function ChannelHeader({
  agents,
  managerChatOpen,
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
  managerChatOpen?: boolean;
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

  return (
    <header className="personal-channel-header">
      <button aria-expanded={mobileNavigationOpen ?? false} aria-label={t("header.openGoalNavigation")} className="personal-icon-button personal-mobile-menu" onClick={onOpenNavigation} type="button"><Menu size={18} /></button>
      <div className="personal-channel-title">
        <h1>{selectedGoal?.title ?? t("header.manager")}</h1>
        <p>{selectedGoal
          ? selectedGoal.loadState ? t(selectedGoal.loadState === "error" ? "startup.goalError" : "startup.goalLoading") : `${selectedGoal.agentLaneCount && selectedGoal.agentLaneCount > 1
            ? t("header.workAgentCount", { count: selectedGoal.agentLaneCount })
            : selectedGoal.agentLabel ?? selectedGoal.agentId} · ${(selectedGoal.loadState ? t(selectedGoal.loadState === "error" ? "startup.goalError" : "startup.goalLoading") : localizedGoalState(selectedGoal.state, locale))}${selectedGoalUsageLabel ? ` · ${selectedGoalUsageLabel}` : ""} · ${selectedGoal.nextSentence}`
          : t("header.managerDescription")}</p>
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
                  <span><strong>{t("header.goalDetails")}</strong><small>{t("header.goalDetailsDescription")}</small></span>
                </button>
                <button onClick={() => runGoalTool(onOpenGoalCapabilities)} type="button">
                  <SlidersHorizontal aria-hidden size={17} />
                  <span><strong>{t("header.goalCapabilities")}</strong><small>{t("header.goalCapabilitiesDescription")}</small></span>
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
