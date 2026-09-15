# Goal acceptance observations

Open a Goal, then **Goal settings → Goal details → Acceptance observations**.
The read-only card shows each observed acceptance requirement with its Agent and
observation time, pending gates with their target Agent and decision scope,
and the next action already projected by status. A missing human decision owner
is shown as unknown; the blocked Agent is not assumed to be the approver.

The same projection is available as `run_history.goals[].acceptance_observation` in
`loopx status --format json`; status Markdown includes a compact summary.
No activation or new permission is required. This changes presentation only;
Todo, gate, quota, settlement, and Goal completion authority are unchanged.

Acceptance requirements reuse the frontier's existing per-Agent vision rules
from already-collected history before display trimming. It does not collect a
complete frontier or audit all Agent lanes. History is bounded, so every
result is partial: no gaps is not successful acceptance. Missing sources and
truncated observations stay visible. Historical lifecycle markers have source
references when available and never override current open gates.

This bounded slice uses `goal_acceptance_observation_projection_v0`. It is not
the broader `goal_artifact_lifecycle_projection_v0` contract proposed by the
[Goal artifact lifecycle RFC](../architecture/rfcs/goal-artifact-lifecycle-projection-v0.md),
whose phases, declared milestones and legal transitions remain unchanged.
No alias accepts that broader schema as this observation payload.
It does not introduce declared milestone authoring, a universal phase sequence,
an exhaustive evidence audit, new legal transitions, or a completion decision.
Legacy sources without the projection display unavailable, not success.
The proposed [Goal direction baseline](../architecture/rfcs/goal-direction-baseline-v0.md)
material declarations and revision-bound usage receipts are not implemented here;
historical progress does not establish that current direction materials were read.

Status also exposes a separate `run_history.goals[].artifact_lifecycle` readout
and Markdown summary: observed phase, evidence milestones, guards and next steps.
It consumes the current Goal's session-runtime work observation before display
trimming. Outstanding required work keeps the phase `qualifying` even when
Todos are complete and historical progress is reached. An absent work observation
does not invent a work requirement. This v0 readout **never recommends a terminal
transition**: `closing` stays a verification step with the machine-readable
`next_transitions[].reason_codes` value `acceptance_unverified`, both when sources
are missing and when all bounded sources were observed. Consumers use that code,
not English `precondition` text. A Goal already recorded as terminal still displays
`lifecycle_phase: closed` with no next transitions. Adding acceptance-driven
terminal advice requires a separate contract change and producer-side validation.
This readout grants no execution or completion authority; the Dashboard card
above keeps its separate acceptance-observation contract.

Work observation coverage follows the supplied projection, not `adapter.kind`:

| Source delivered to status | Work observation coverage |
| --- | --- |
| Session-runtime adapter, or another adapter emitting the same session-runtime projection | Available only with `session_runtime_readonly_projection_v0`, a matching Goal id, and work facts |
| Adapter without that projection, or a projection with a mismatched schema/Goal id | Unavailable; this readout does not query quota or other lane owners |

Without that source a Goal may read `closing` from Todo/history even when a lane
outside the observation still requires work. Neither `closing` nor absence of
`work_lane_selected` proves all work is complete; the lane and completion owners
retain their decisions.

Validation: `python -m pytest tests/control_plane/test_goal_acceptance_observation.py`
and `python -m pytest tests/control_plane/test_goal_artifact_work_observation.py`,
plus `node examples/dashboard-goal-acceptance-browser-smoke.mjs`. The browser
check consumes real status collection over a disposable synthetic Goal; set
`LOOPX_GOAL_ACCEPTANCE_PACKAGED=1` after the Dashboard build to check shipped assets.

## 中文

打开 Goal，选择 **Goal 设置 → Goal 详情 → 验收观察**。
只读卡片展示已有验收要求、对应 Agent、观测时间、待处理门禁的目标 Agent 和决策范围，
以及 status 已给出的下一步。人类决策责任人未提供时显示未知，不把被阻塞的 Agent
当作审批人。`loopx status --format json` 中的
`run_history.goals[].acceptance_observation` 提供相同投影，Markdown 提供简要摘要。

无需启用或增加权限。仅改变展示，不改变 Todo、gate、quota、settlement 或 Goal 完成权威。
验收要求复用执行前沿已有的 Agent vision 规则，并消费展示截断前已读取的历史，不额外读取文件。
不收集完整执行前沿，也不审计所有 Agent 通道。历史是有界输入，因此始终显示部分观测：
没有缺口不等于通过验收。
缺少来源及观测截断会明确提示；历史生命周期记录不能覆盖当前未关闭的门禁。

此有界切片使用 `goal_acceptance_observation_projection_v0`，不是 RFC 中的完整
`goal_artifact_lifecycle_projection_v0`；后者的阶段、声明式里程碑和合法迁移设计保持不变。
不保留把完整协议误认作该观察结构的别名。此切片不增加里程碑声明入口、统一阶段序列、完整证据审计、
新的合法迁移或完成判定。Goal direction baseline 提案中的材料声明和绑定版本的阅读回执
不在此次实现范围；历史进展不能证明已阅读当前方向材料。旧来源不提供投影时显示不可用。
status 同时在独立的 `run_history.goals[].artifact_lifecycle` 和 Markdown 摘要中展示
观测阶段、证据里程碑、门禁和下一步。它在展示截断前读取当前 Goal 的 session-runtime
工作观察：即使 Todo 全部完成且历史进展已达成，只要仍有必须执行的工作，阶段就保持
`qualifying`。缺少工作观察不会凭空产生执行要求。此 v0 读出**始终不建议终态迁移**：
`closing` 保持为验收核验步骤，无论是否缺少来源，均通过
`next_transitions[].reason_codes` 中的 `acceptance_unverified` 表达本读出未验证验收。
机器消费者读取该 code，无需匹配英文 `precondition`。已记录为终态的 Goal 仍展示
`lifecycle_phase: closed`，下一步列表为空。未来若增加基于验收的终态建议，必须另行变更合同并验证产出侧。
此读出不授予执行或完成权威，Dashboard 卡片仍使用独立的验收观察合同。

工作观察覆盖取决于实际提供的投影，不按 `adapter.kind` 名称判断：

| status 接收的来源 | 工作观察覆盖 |
| --- | --- |
| session-runtime adapter，或提供相同 session-runtime 投影的其它 adapter | schema 为 `session_runtime_readonly_projection_v0`、Goal id 匹配且包含工作事实时可用 |
| 不提供该投影的 adapter，或 schema/Goal id 不匹配的投影 | 不可用；此读出不会额外查询 quota 或其它工作通道权威 |

缺少该来源时，即使观察范围外仍有必须执行的工作，Todo/历史也可能让 Goal 显示 `closing`。
`closing` 或缺少 `work_lane_selected` 均不证明所有工作完成，工作通道与完成权威仍保留各自的判断。
上面的测试命令覆盖合成 Goal 的生产 refresh-state 写入、
真实 status 收集和浏览器入口；打包验证使用 `LOOPX_GOAL_ACCEPTANCE_PACKAGED=1`。
