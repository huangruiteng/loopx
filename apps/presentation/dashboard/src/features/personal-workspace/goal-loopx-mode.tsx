import {useEffect, useState} from "react";
import {Pause, Play, Settings2} from "lucide-react";
import {fetchLoopXMode, updateLoopXMode, type LoopXModeSnapshot, type LoopXModeSettings} from "../../data/chat";
import {useWorkspaceI18n} from "./i18n";
import "./goal-loopx-mode.css";

export function GoalLoopXMode({sessionId, onPrepare, onExecute, onChange}: {
  sessionId?: string;
  onPrepare: () => Promise<string>;
  onExecute: (operation: "start" | "resume", settings?: LoopXModeSettings) => void;
  onChange: (snapshot: LoopXModeSnapshot | null) => void;
}) {
  const {locale} = useWorkspaceI18n();
  const zh = locale === "zh-CN";
  const [snapshot, setSnapshot] = useState<LoopXModeSnapshot | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [settings, setSettings] = useState<LoopXModeSettings>({agent_id: "", token_budget: 0});
  useEffect(() => {
    let alive = true;
    let refreshing = false;
    setSnapshot(null); onChange(null); setError(""); setEditing(false);
    if (!sessionId || sessionId === "new-session-pending") return;
    async function refresh() {
      if (refreshing) return;
      refreshing = true;
      try {
        const result = await fetchLoopXMode(sessionId!);
        if (alive) {setSnapshot(result); onChange(result);}
      } catch (failure) {if (alive) setError(failure instanceof Error ? failure.message : String(failure));}
      finally {refreshing = false;}
    }
    void refresh();
    const interval = window.setInterval(() => {if (!document.hidden) void refresh();}, 2500);
    return () => {alive = false; window.clearInterval(interval);};
  }, [sessionId]); // onChange is the owning component's stable state setter.
  const active = Boolean(snapshot?.enabled && snapshot.active_turn_id);
  const native = snapshot?.native.status ?? "absent";
  const resume = !["absent", "complete"].includes(native);
  const configured = Boolean(snapshot?.settings.agent_id && snapshot.settings.token_budget
    && snapshot.settings.execution_config);
  const editSettings = (current: LoopXModeSnapshot) => {
    setSettings({agent_id: current.settings.agent_id ?? "", token_budget: current.settings.token_budget ?? 0});
    setEditing(true);
  };
  const status = !snapshot?.enabled ? (zh ? "普通对话" : "Conversation")
    : snapshot.recovery_required ? (zh ? "LoopX · 需要恢复连接" : "LoopX · Reconnect required")
    : native === "blocked" ? (zh ? "LoopX · 需要处理阻塞" : "LoopX · Blocked")
    : active ? (zh ? "LoopX · 正在推进" : "LoopX · Working")
    : native === "complete" ? (zh ? "LoopX · 本轮已结束" : "LoopX · Run finished")
    : ["budgetLimited", "usageLimited"].includes(native) ? (zh ? "LoopX · 已到额度限制" : "LoopX · Usage limit")
    : (zh ? "LoopX · 已暂停" : "LoopX · Paused");
  const openSettings = () => {
    if (snapshot && !editing) editSettings(snapshot);
    else setEditing(false);
  };
  async function prepareSettings() {
    setBusy(true); setError("");
    try {
      const preparedSessionId = await onPrepare();
      const result = await fetchLoopXMode(preparedSessionId);
      setSnapshot(result); onChange(result); editSettings(result);
    } catch (failure) {setError(failure instanceof Error ? failure.message : String(failure));}
    finally {setBusy(false);}
  }
  async function mutate(operation: string) {
    if (!sessionId) return;
    setBusy(true); setError("");
    try {const result = await updateLoopXMode(sessionId, operation, operation === "configure" ? settings : undefined);
      setSnapshot(result); onChange(result); setEditing(false);
    } catch (failure) {setError(failure instanceof Error ? failure.message : String(failure));}
    finally {setBusy(false);}
  }
  return <section className="goal-loopx-mode" aria-label={zh ? "LoopX 运行模式" : "LoopX execution mode"}>
    <div className="goal-loopx-mode-bar"><div><strong>{status}</strong><p>{active
      ? (zh ? "协调员持续工作；成员保持独立执行与验收。" : "The coordinator continues; members execute and qualify independently.")
      : snapshot?.enabled && native === "complete" ? (zh ? "本次执行已结束；整个 Goal 仍按原标准验收。" : "This run ended; canonical Goal acceptance remains separate.")
      : snapshot?.enabled ? (zh ? "暂停不会停止已派发成员；整个 Goal 仍按原标准验收。" : "Pausing retains delegated work; Goal acceptance remains separate.")
      : (zh ? "开启后，当前协调员持续推进本 Goal。" : "Enable continued work on this Goal in this conversation.")}</p></div>
      <div className="goal-loopx-mode-actions"><button type="button" disabled={busy || snapshot?.conversation_busy || !snapshot} onClick={openSettings} aria-expanded={editing}><Settings2 size={14}/>{zh ? "运行设置" : "Settings"}</button>
        <button type="button" disabled={busy || Boolean(snapshot?.conversation_busy && !active)} onClick={async () => {
          if (!snapshot) {
            await prepareSettings();
            return;
          }
          if (active) void mutate("pause");
          else if (!configured || Number(snapshot?.settings.token_budget ?? 0) <= Number(snapshot?.native.tokensUsed ?? 0)) openSettings();
          else onExecute(resume ? "resume" : "start");
        }}>{active ? <Pause size={14}/> : <Play size={14}/>}{active ? (zh ? "暂停" : "Pause") : !snapshot?.enabled ? (zh ? "开启 LoopX 模式" : "Enable LoopX") : native === "complete" ? (zh ? "开启新一轮" : "Start new run") : (zh ? "恢复推进" : "Continue")}</button>
        {snapshot?.enabled && !active ? <button type="button" disabled={busy} onClick={() => void mutate("exit")}>{zh ? "退出模式" : "Exit mode"}</button> : null}
      </div></div>
    {editing ? <div className="goal-loopx-mode-settings"><label>{zh ? "已注册的协调身份" : "Registered coordinator"}<select value={settings.agent_id} onChange={event => setSettings({...settings, agent_id: event.target.value})}><option value="">{zh ? "选择已授权身份" : "Select authorized identity"}</option>{snapshot?.registered_agents.map(id => <option key={id} value={id}>{id}</option>)}</select></label>
      <label>{zh ? "协调员总 token 额度" : "Coordinator total token allowance"}<input type="number" min={1} max={2147483647} value={settings.token_budget || ""} onChange={event => setSettings({...settings, token_budget: Number(event.target.value)})}/></label>
      <label>{zh ? "成员执行绑定文件（Goal 配置）" : "Member execution bindings (Goal configuration)"}<input readOnly value={snapshot?.settings.execution_config ?? (zh ? "未配置" : "Not configured")}/></label>
      <p>{zh ? "绑定文件由 Goal 子代理设置统一管理；额度包含协调员历史用量，成员授权不会因开启模式而扩大。" : "Manage the binding file in Goal sub-agent settings. The allowance includes coordinator history; enabling this mode does not expand member grants."}</p>
      <button type="button" disabled={busy || !settings.agent_id || settings.token_budget < 1 || !snapshot?.settings.execution_config} onClick={() => void mutate("configure")}>{zh ? "保存设置" : "Save settings"}</button></div> : null}
    {snapshot?.enabled && snapshot.native.tokensUsed !== undefined ? <p className="goal-loopx-mode-usage">{zh ? "协调员累计用量" : "Coordinator usage"} {snapshot.native.tokensUsed.toLocaleString()} / {snapshot.native.tokenBudget?.toLocaleString() ?? "—"} tokens</p> : null}
    {snapshot?.enabled && snapshot.ingress.some(row => row.status !== "delivered") ? <p role="status">{zh ? "待处理消息：" : "Pending messages: "}{snapshot.ingress.filter(row => row.status !== "delivered").map(row => `${row.mode === "loopx_queue" ? "queue" : "inbox"} · ${row.status}`).join(" / ")}</p> : null}
    {snapshot?.enabled && snapshot.deliveries.length ? <div className="goal-loopx-mode-members" aria-label={zh ? "最近一次成员回读" : "Last member observations"}><span>{zh ? "成员最近回读" : "Last observations"}</span>{snapshot.deliveries.map(row => <span key={row.operation_id}>{row.agent_id} · {row.status === "accepted" ? (zh ? "已通过验收" : "Accepted") : row.status === "rejected" ? (zh ? "未通过验收" : "Rejected") : row.status === "unavailable" ? (zh ? "需要重新核验" : "Recheck required") : (zh ? "执行中" : "Working")}</span>)}</div> : null}
    {error ? <p className="personal-composer-error" role="alert">{error}</p> : null}
  </section>;
}
