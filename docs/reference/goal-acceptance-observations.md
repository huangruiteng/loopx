# Goal acceptance observations

Open a Goal, then **Goal settings → Goal details → Milestones and acceptance gaps**.
The read-only card shows each observed acceptance requirement with its Agent and
observation time, pending gates with their target Agent and decision scope,
and the next action already projected by status. A missing human decision owner
is shown as unknown; the blocked Agent is not assumed to be the approver.

The same projection is available as `run_history.goals[].artifact_lifecycle` in
`loopx status --format json`; status Markdown includes a compact summary.
No activation or new permission is required. This changes presentation only;
Todo, gate, quota, settlement, and Goal completion authority are unchanged.

Acceptance requirements reuse the frontier's existing per-Agent vision rules
from already-collected history before display trimming. Frontier observations,
when present, retain their bounded scope. History itself is bounded, so every
result is partial: no gaps is not successful acceptance. Missing sources and
truncated observations stay visible. Historical lifecycle markers have source
references when available and never override current open gates.

This implements a first read-only consumer of the
[Goal artifact lifecycle RFC](../architecture/rfcs/goal-artifact-lifecycle-projection-v0.md).
It does not introduce declared milestone authoring, a universal phase sequence,
an exhaustive evidence audit, new legal transitions, or a completion decision.
Legacy sources without the projection display unavailable, not success.

Validation: `python -m pytest tests/control_plane/test_goal_artifact_lifecycle.py`
and `node examples/dashboard-goal-acceptance-browser-smoke.mjs`. The browser
check consumes real status collection over a disposable synthetic Goal; set
`LOOPX_GOAL_ACCEPTANCE_PACKAGED=1` after the Dashboard build to check shipped assets.

## 中文

打开 Goal，选择 **Goal 设置 → Goal 详情 → 里程碑与验收缺口**。
只读卡片展示已有验收要求、对应 Agent、观测时间、待处理门禁的目标 Agent 和决策范围，
以及 status 已给出的下一步。人类决策责任人未提供时显示未知，不把被阻塞的 Agent
当作审批人。`loopx status --format json` 中的
`run_history.goals[].artifact_lifecycle` 提供相同投影，Markdown 提供简要摘要。

无需启用或增加权限。仅改变展示，不改变 Todo、gate、quota、settlement 或 Goal 完成权威。
验收要求复用执行前沿已有的 Agent vision 规则，并消费展示截断前已读取的历史，不额外读取文件。
历史和执行前沿本身是有界输入，因此始终显示部分观测：没有缺口不等于通过验收。
缺少来源及观测截断会明确提示；历史生命周期记录不能覆盖当前未关闭的门禁。

这是 RFC 的首个只读消费者，不增加里程碑声明入口、统一阶段序列、完整证据审计、
新的合法迁移或完成判定。旧来源不提供投影时显示不可用。上面的测试命令覆盖合成 Goal 的
真实 status 收集和浏览器入口；打包验证使用 `LOOPX_GOAL_ACCEPTANCE_PACKAGED=1`。
