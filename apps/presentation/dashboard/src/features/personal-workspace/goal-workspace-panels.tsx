import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import type { WorkspaceGoalTab } from "./personal-workspace-model";

/** Keep visited views alive within one Goal; each view owns its scroll position. */
export function GoalWorkspacePanels({ activeTab, panels, scrollRef }: {
  activeTab: WorkspaceGoalTab;
  panels: Record<WorkspaceGoalTab, ReactNode>;
  scrollRef: RefObject<HTMLDivElement | null>;
}) {
  const [visited, setVisited] = useState(() => new Set([activeTab]));
  const positions = useRef<Partial<Record<WorkspaceGoalTab, number>>>({});
  useEffect(() => setVisited(current => current.has(activeTab) ? current : new Set([...current, activeTab])), [activeTab]);
  useLayoutEffect(() => {
    const scroll = scrollRef.current;
    if (!scroll) return;
    scroll.scrollTop = positions.current[activeTab] ?? 0;
    const remember = () => { positions.current[activeTab] = scroll.scrollTop; };
    scroll.addEventListener("scroll", remember, { passive: true });
    return () => scroll.removeEventListener("scroll", remember);
  }, [activeTab, scrollRef]);
  return (Object.keys(panels) as WorkspaceGoalTab[]).map(tab => visited.has(tab) || tab === activeTab
    ? <div className="personal-goal-view-panel" data-goal-panel={tab} hidden={tab !== activeTab} key={tab}>{panels[tab]}</div>
    : null);
}
