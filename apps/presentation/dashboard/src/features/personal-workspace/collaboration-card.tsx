import type { CollaborationReadback } from "../../data/chat-model";
import { useWorkspaceI18n } from "./i18n";
import "./collaboration-card.css";

const copy = {
  "zh-CN": {
    title: "交办说明", context: "背景与补充", constraints: "约束", inputs: "输入材料",
    acceptance: "验收要求", return: "需要回传", supplied: "已提供给接收方", pending: "等待接收方读取",
    decision: "接收方判断", unknown: "尚未记录", unavailable: "暂时无法读取",
    adopt: "已采纳", defer: "已暂缓", reject: "未采纳", no_change: "无需调整",
    result: "结论已保存", delivered: "结论已回传", details: "查看交办内容",
  },
  en: {
    title: "Delegation brief", context: "Context & corrections", constraints: "Constraints", inputs: "Inputs",
    acceptance: "Acceptance", return: "Expected return", supplied: "Supplied to receiver", pending: "Awaiting receiver read",
    decision: "Receiver decision", unknown: "Not recorded", unavailable: "Readback unavailable",
    adopt: "Adopted", defer: "Deferred", reject: "Rejected", no_change: "No change needed",
    result: "Conclusion saved", delivered: "Conclusion returned", details: "View delegation details",
  },
};

export function CollaborationCard({ request }: { request?: CollaborationReadback }) {
  const { locale } = useWorkspaceI18n();
  if (!request) return null;
  const c = copy[locale];
  const brief = request.brief;
  const decision = request.decision as "adopt" | "defer" | "reject" | "no_change";
  const conclusion = request.returns.find((reply) => reply.phase === "conclusion");
  return <section className="personal-collaboration" aria-label={c.title}>
    <header><strong>{brief.purpose}</strong><span>{request.agent_id}</span></header>
    <p className="personal-collaboration-status">
      <span>{request.read_status === "supplied" ? c.supplied : request.read_status === "unavailable" ? c.unavailable : c.pending}</span>
      <span>{c.decision}: {c[decision] ?? (request.decision === "unavailable" ? c.unavailable : c.unknown)}</span>
      {conclusion ? <span>{conclusion.status === "delivered" ? c.delivered : c.result}</span> : null}
    </p>
    <details>
      <summary>{c.details}</summary>
      <h4>{c.context}</h4><p>{brief.context}</p>
      {brief.constraints.length ? <><h4>{c.constraints}</h4><ul>{brief.constraints.map((item, i) => <li key={i}>{item}</li>)}</ul></> : null}
      {brief.inputs.length ? <><h4>{c.inputs}</h4><ul>{brief.inputs.map((input, i) => <li key={i}><code>{input.ref}</code> — {input.description}{input.sha256 ? <small>sha256:{input.sha256}</small> : null}</li>)}</ul></> : null}
      <h4>{c.acceptance}</h4><ul>{brief.acceptance.map((item, i) => <li key={i}>{item}</li>)}</ul>
      <h4>{c.return}</h4><p>{brief.return_requirement}</p>
    </details>
  </section>;
}
