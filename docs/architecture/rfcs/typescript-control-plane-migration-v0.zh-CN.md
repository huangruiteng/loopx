# RFC：LoopX 控制面 TypeScript 渐进迁移方向 v0

- Status：Accepted，transaction-payoff 阶段进行中
- Proposed by：LoopX maintainers
- Date：2026-08-15
- Last revised：2026-09-05
- Scope：LoopX 控制面核心从 Python 到 TypeScript 的增量、replacement-first
  迁移；不长期维护两份语义实现
- Tracking issue：[#3225](https://github.com/huangruiteng/loopx/issues/3225)
- Language note：本中文版与
  [英文版](./typescript-control-plane-migration-v0.md) 为语义镜像；
  两者不一致视为缺陷。

---

## 当前实现检查点

受检入的 generator 校验语言中立 contract，并生成深度不可变的 Python/TypeScript
binding，覆盖原生 domain 与 projection section。两端 runtime 直接 import 生成物；
CI 检查源数据一致性并拒绝陈旧生成物。这删除了重复 contract loader，但不改变
Todo 语义或 promotion policy。

coordination 路径使用同一份语言中立的 `coordination_state_contract_v0.json`。
原生 `TodoDomainRecord` 持有任务语义，包括 `archive_state`；
`TodoProjectionMetadata` 包含 `source_section` 和可选 `index`。TypeScript reducer
与 provider-first collection reader 接受独立版本的原生 domain manifest；测试证明
原生创建、归档、receipt replay 与 store reopen 不需要 Markdown metadata。Python
仅将 typed read result 适配为兼容 summary。这是 contract 检查点，不是已经完成的
CLI lifecycle cutover。

Provider-first `todo update --text/--note` 保留不改变认领关系的文案修正：
已注册、未被排除且符合 agent binding 的 actor，可以编辑未认领、active 且未完成的
agent Todo，不得因此写入 `claimed_by`；其他 claim owner 的 Todo 仍拒绝修改。
只允许 patch/clear text 与 note，不授予治理字段修改权或 hard-lease 执行权。
资格检查、CAS 与 receipt replay 由 TS 事务持有；promotion 不应把文案修正变成认领。
Provider conformance 同时覆盖原生与 v0 记录，真实 CLI 在无 Markdown 时验证该行为。

默认 Markdown 与显式 promotion 两条 `todo claim` 路径现在都由同一个 TS claim
decision 处理 actor、registration、role、status、archive、exclusion 与现有 owner
检查；Python legacy writer 只在持锁后提交该 decision。显式 promotion 后，claim
只跨一次 runtime 边界，由同一 TS 事务同时处理原生
和 v0 记录。新 claim 要求 active、open Todo，并检查当前 actor/lease；同一 operation
的重试先恢复原 claim receipt，再考虑当前资格。观测时间和当前注册信息不属于请求
身份。回放 receipt 不续租，也不表示当前仍持有任务。非 preview 的成功 `no_change`
同样在 head CAS 下持久化终态 receipt：存储 revision 可以前进，但 Todo 状态、
`updated_at` 和 domain events 不变。结构合法的空注册名单允许历史回放，不能发起
新 claim；非法名单仍失败。preview 保持零写入，非法 preview boolean 在访问 provider
前失败。CLI 默认仍为每次调用生成新 operation id。在已经 promotion 的 canonical
authority 上，可显式使用
`loopx todo claim --goal-id <goal> --todo-id <todo> --claimed-by <agent> --agent-id <agent> --claim-operation-id <public-safe-id>`
进行跨进程重试：响应丢失后复用相同 id 和请求意图；同 id 搭配不同意图会失败。
preview 不消耗该 id。legacy 模式会拒绝此选项，不写入也不自动 promotion；省略
选项即可保持默认行为。历史 replay 不授予 lease 或当前所有权，claim/lease 联合
获取仍是后续工作。

下一 replacement slice 让 promotion 后的 `todo add` 成为同一 authority owner 上的
原生 create transaction。Python 只校验既有 CLI 参数并一次性适配为带版本的 domain
record；语义重复、replay、actor/owner 资格、CAS、receipt 和 projection-outbox
mutation 都由 TypeScript 持有。preview 与真实 subprocess CLI 路径会先删除 Markdown
state file 再验证，因此 promotion 不会悄悄恢复 Markdown 写入。completion-validation
argv 保持 typed data，不退回 shell 编码的兼容字段。未 promotion 的默认 goal 在显式
promotion 边界前继续使用既有 Markdown transaction。

旧 v0 consumer manifest 继续可读，并保留所有已有字段。默认 Markdown capture 仍
输出 v0；本 PR 不改写已存 head，也不自动晋升 goal。schema 分层不等于允许后续迁移
丢失 v0 provenance 或改变旧排序。

### 长程持久化也是迁移收益的一部分

产品目标是单个 goal 至少持续十个自然日。shared-authority RFC 的
[第 7.2 节](./shared-goal-authority-state-provider-v0.zh-CN.md#72-十天-goal本地存储资格化目标提案)
统一维护负载、性能预算、保留策略和真实 soak 验收；变化的容量数字不在此重复维护。

与 provider-first Todo caller 同期推进完整本地持久化切片：资格化嵌入式事务存储
（SQLite 为首选候选）、有界 live head/receipt lookup、crash-safe checkpoint 与精确
历史 readback。file-v0 保留作 conformance/import 基线。只把 Python 改为 TypeScript、
换数据库但保留不断增长的 head，或只通过加速容量测试，都不证明十天连续性。
本地晋升等待容量与自然时间双重资格化，不等待 PostgreSQL 服务，也不在第十天使
receipt 过期。

### 交付语义：先修正规则，再迁移

交付历史边界将 `classification`、`health_check` 与 `recommended_action` 视为
叙述文本。它们不能生成或解除 follow-through obligation，不能证明 outcome，也
不能判定交付规模。例如，`unblocked after dependency update` 不构成 blocker
receipt，`implemented network protocol parser` 不构成仅完成准备工作的证据。

规则继续由 `control_plane/work_items/delivery_outcome.py`、`delivery_signals.py`
和 `outcome_followthrough.py` 持有。本批在既有 owner 中完成正确性前置修复，不新增
capability/provider，也不宣称完成 TypeScript 事务迁移。删除关键词推断与 status
常量，不增加 runtime crossing、schema 或 service；复用已有 typed blocker
settlement 判定，不复制证据绑定规则。

验收不变量是**叙述非干涉**：固定 typed fields 与配置，改写叙述或增加未经验证的
`compact_evidence` / `case_result` 对象，都不能改变交付语义与后续执行义务。
classification 保留为历史标签；没有明确展示消费者时，不保留旧预测逻辑。

- 合法的显式 outcome、turn kind 和 scale 保持原有语义。显式 blocker kind
  继续可读。带作用域的 typed blocked observation 必须通过既有 work-item/evidence
  绑定检查，才能将 gap 判定为 blocker writeback；只有 `outcome_gap` 不够。
- 历史字段缺失或不受支持时保持 unknown。unknown 中断连续小规模／outcome-gap
  证据计数，不视为成功或推断出的失败。未配置 floor 且没有 outcome 时，保留
  `not_configured` 展示哨兵值。
- 新交付声明通过现有 writer API 写显式 enum，例如
  `refresh-state --delivery-outcome ... --delivery-batch-scale ...`。
  纯状态刷新仍可不声明交付；本批不强迫每次刷新声明进展。既有写入 enum 校验、
  settlement evidence、quota 和 gate 检查继续有效。
- 旧 outcome-marker/hint 配置继续可读，并保留 floor 是否配置的含义；配置中的
  词语不再分类 run。不改写持久历史，也不新增开关恢复错误行为。此前由未结构化
  历史标签推导的 status、handoff/review 和 quota 决策会发生明确的行为变化。

交付领域的迁移单元是完整的 delivery-history-to-obligation projection，包含规模／结果
连续计数与 status/quota 消费者。这定义该领域的切片边界，不改变下文 provider-first
Todo 的交付顺序。每批有界历史最多跨 runtime 一次，删除被替代的
Python decision，保留独立审阅的 typed case，并通过真实 CLI 验证叙述变异用例。
旧推断本身错误，因此只有传输 golden parity 不够。另行盘点仍缺少 material-result
字段的 writer，并用明确兼容计划退役旧 marker/hint 配置。本批不迁移精确的旧
lifecycle classification code 或其他 cadence policy，不能宣称全局已无文本规则。

### 下一步交付顺序

1. **一组 provider-first Todo 完整事务。** 原生 create、claim、update、
   complete-with-successor、archive 及相关 lease effect 经过现有 TS authority owner。
   每个内聚的纵向切片包含真实 CLI caller、replay/CAS/error 测试，并删除被替代的
   Python decision。仅统一 schema 或常量不满足退出条件。
   单命令切片（例如通过同一兼容 editor 的 `todo update --text/--note`）只是
   合成/资格化 goal 的验证里程碑，不是真实 goal 的 promote：一旦 promote，其余
   legacy writer 仍被 fence 以 fail-closed 拦截。因此活跃 goal 的 promote 要等
   到其 agent 实际使用的写命令族都经由同一个统一 TS 提交权威（同一入口的分命令
   transaction 类型（共享同一个 effect-runtime 边界，而不是平行语义 owner），并且
   capture/projection outbox 落盘接通之后。
   删除的收益只在该入口背后的 in-place Markdown editor 被纯投影 renderer 替代时兑现。

2. **先资格化，再启用。** 与 shared-authority RFC 的显式 v0 import、consumer
   parity、writer fencing、capture/projection outbox recovery 和 fenced export 汇合。
   集成上述本地持久化切片，包含历史 receipt 保留、容量与 >=10 天 soak 证据。
   file-v0 conformance 不足以支持长程晋升；不默认切换 authority，也不依赖 PostgreSQL service。
3. **删除 bridge，再收敛入口。** 最后一个 caller 切换后，删除被替代的 reference
   aggregate 与 Python facade；native CLI/App 和可选 daemon 复用同一 kernel。
   每个切片报告删除的 product LOC、新增 bridge LOC、crossings 与剩余删除条件。
   连续两个切片只有 scaffolding 时，停止并重新规划。

stack 中的 schema identifier 清理是独立维护，不是上述路线的前置条件。只吸收所选
完整事务确实依赖的下游改动；base 合并后，其余工作再 rebase。

## 0. 用一个例子说明决策

迁移期间，Python `loopx` CLI 向 LoopX 托管的 TypeScript runtime 发送一笔
粗粒度 typed transaction。例如，Turn settlement 先由 TypeScript 验证 journal，
并授权仍由 Python 承载的 provider；Python checkpoint 这些外部结果后，再由
TypeScript 完成最终 reduction 并返回 typed result。没有待执行 provider 的 replay
只需一次 reduction。Python 只把结果投影为旧 CLI shape，不再串行调用一组
TypeScript leaf helper，也不保留平行的 enum 和 reducer。

同一 PR 必须删除被它替代的 Python 语义路径。仅新增 TypeScript module 不等于取得
迁移进展；真正的兑现是语义 owner 更少、跨 runtime round trip 更少，并且 facade
有可信的删除条件。

CLI 自身迁到 TypeScript 后，CLI-only 使用方式会在进程内直接 import 同一份
kernel，Python 到 TypeScript 的桥随之删除。当 App、CLI、scheduler 或多个
host 需要一个共享 writer 时，同一 kernel 可以运行在一个可选的 managed
daemon 内。这是一份 kernel 的两种部署形态，不是每个控制面状态族一个
server。

## 1. 问题

LoopX 已有 TypeScript host 与 dashboard 表面。Effect Program、Turn-journal effect、
若干 Todo/quota decision 和 scheduler state 已有 TypeScript owner，但大量 CLI
composition 与兼容表面仍在 Python。一次性重写风险过高；然而继续逐个翻译 leaf
helper 会留下 chatty bridge 和重复 DTO 知识：代码位置变了，产品并没有简化。

因此，中间迁移节点必须同时满足：

- 每条已迁规则只有一个语义 owner；
- 用户看不到 CLI 分叉，也无需手动管理 daemon；
- 可以迁移真实副作用，而不只迁纯投影；
- 基于 pinned 迁移前基线和独立定义的不变量验证正确性；
- 每次 cutover 都测量 latency、packaging、upgrade、rollback 与 crash recovery；
- 每个 PR 都是完整、可评审的 replacement slice；
- 迁移经济性必须改善：旧语义代码和临时 scaffolding 的退出速度要快于 bridge
  代码的累积速度。

## 2. 架构决策

### 2.1 一份 TypeScript kernel

`@loopx/control-plane` 是目标语义 kernel。Domain module 拥有 typed state、
解释、transition rule 和属于这些规则的内部 effect。Transport shell 不能成为
第二个业务 owner。

```text
迁移期 Python CLI ─────────┐
LoopX App / scheduler ─────┼─> 一个 typed runtime boundary ─> TS kernel
未来 TS CLI ───────────────┘
```

边界传递“结算这个 Turn”“提交这个 journal”这类粗粒度、版本化请求，而不是
频繁的属性 getter。Runtime 只有一个静态 typed handler registry；新增 domain
handler 不会新增 server。

### 2.2 两种部署形态，一份实现

| 产品拓扑 | 执行形态 |
| --- | --- |
| TS CLI cutover 后的 CLI-only | CLI 进程内 import 并执行 TS kernel；没有 daemon |
| 仅 App | App runtime 内嵌同一 kernel |
| App + CLI + scheduler，或多个并发 client | 一个 managed local authority daemon；client 连接当前 writer |
| Python 仍是 CLI 的迁移期 | 一个 idle-exiting loopback runtime 把 Python 桥接到已迁 TS kernel |

如果 authority daemon 已拥有某个 registry/workspace，CLI 必须连接它，而不能
绕过它再打开第二个直接 writer。Runtime discovery 与启动全自动；用户无需配置
端口或守护进程。

### 2.3 TypeScript 拥有已迁 effect

目标不是“TypeScript 决策、Python 永远执行”。TypeScript 可以拥有 atomic
state checkpoint、event append、receipt commit、幂等 reducer write 等 LoopX
内部 effect。每个 effect 都有 typed request、稳定 idempotency identity、typed
receipt 与 retry policy。

异步执行不会削弱 settlement ordering：只有被 `await` 的 durability boundary
成功后，才能发出 effect receipt。但异步允许请求并发，因此拥有已迁写入 authority
的一方也必须拥有按 key 串行化或 compare-and-swap 合同。Caller-side lock 只能作为
明确的迁移期 guard；native TypeScript caller 在 cutover 后不得绕过这个 invariant。
Retry identity 必须绑定具体 operation：当一个 Turn effect 连续 checkpoint 多个
journal 状态时，仅凭宽粒度 Turn effect id 不能证明两次写入 payload 是同一 operation。

外部 authority 仍是显式 adapter：model call、human gate、host scheduler、
credential 和第三方 mutation 不会藏到一个万能 executor 后面。它们的 receipt
回到 Effect Program 完成 settlement。

### 2.4 替换，而不是生产双跑

Characterization 可以离线让新旧实现运行同一份 pinned corpus。生产环境不保留
两个 rule engine，也不 dual-write semantic state。一个 slice 通过门禁后，caller
翻到 TypeScript，并删除被替代的 Python 规则。只有真实 public import、持久化
schema 或未迁 callback 需要时，才保留窄 compatibility facade。

### 2.5 在每个信任边界只验证一次

TypeScript 类型在运行时会被擦除。因此 network/RPC payload、解析后的 JSON、
持久化状态、extension 输入与 adapter response 都必须以 `unknown` 进入系统；
静态类型标注或 `as T` 断言不能证明这些字节满足合同。每个已迁 domain 都必须先
通过 typed decoder 或显式的版本化 schema parser 解码，再交给 domain handler
或 Effect interpreter 消费。

解码成功后，TypeScript kernel 拥有这个 typed value，domain 内部可以依赖编译器，
而不必在每层重复临时字段检查。Framing、authentication、size limit 等 transport
检查与 schema validation、semantic invariant 分层负责。未经检查的
`JSON.parse(...) as T` 不能建立控制面 authority。

`as unknown as T` 只允许作为具名迁移缝：cutover PR 必须明确其调用点、上游
validator、负向边界覆盖和移除 owner。只要 public、持久化、RPC 或 extension
输入仍通过未经验证的断言进入已迁 domain 的 semantic core，该 domain 就不能
通过 promotion gate。TypeScript 补充运行时验证，而不是替代它。

## 3. 当前基线与阶段转换

Effect Program 先迁，是因为它连接 ordered step、identity、short-circuit failure、
replay、receipt 与 settlement。这个架构选择已经落地，不再是假设。

### 3.1 已交付基线

| 切片 | 已交付的 TypeScript 权威能力 | 剩余迁移债务 |
| --- | --- | --- |
| Effect runtime 与 Turn journal（[#3416](https://github.com/huangruiteng/loopx/pull/3416)） | Effect algebra、settlement rule、runtime lifecycle、typed Turn-journal interpretation 与 durable checkpoint effect | Python settlement facade 仍暴露细粒度调用，并重复 DTO/enum shape |
| Todo、quota 与 scheduler 证明切片（[#3431](https://github.com/huangruiteng/loopx/pull/3431)–[#3434](https://github.com/huangruiteng/loopx/pull/3434)） | Completion fence/state、workspace causality 与 scheduler transition 各有一个 TS rule owner | 切口大多仍是 leaf-shaped；Python 继续组合多个产品 transaction |
| Scheduler durable state（[#3440](https://github.com/huangruiteng/loopx/pull/3440)） | State normalization、persistence、replay 与一笔粗粒度 transition 由 TS 拥有 | Python compatibility path 仍承担跨 runtime transport 税 |
| Scheduler heartbeat/state transaction | TypeScript 拥有 receipt freshness、ACK 与 host-failure validation、state construction、failure-cache transition、replay/CAS fencing、atomic write，以及 public JSON/Markdown projection | 生成的 receipt-bound host follow-up 直接进入 native TS CLI；Python 只处理 unbound/manual compatibility call 与 external host mutation |
| Quota spend commit transaction | TypeScript 拥有最终 spend transition 校验、typed event 构造、effect replay/CAS fencing、crash repair，以及 JSON/Markdown/index write set | Python 仍投影 `should-run` 与 settlement readback facts，并在 CLI/index writer 进程内迁移前持有 legacy cross-writer index lock |
| Quota void commit transaction | TypeScript 拥有 spend-target resolution、before/after reduction、canonical correction 构造、effect replay/index CAS、prepared-receipt repair，以及 JSON/Markdown/index write set | Python 保留 `should-run` facts、clock/effect identity、legacy cross-writer index lock、一次 transport 与 compatibility entrypoint |
| Quota monitor-poll commit transaction | TypeScript 拥有 monitor admission 复核、target/event/result 构造、effect replay/index CAS、provider intent，以及可修复的 JSON/Markdown/index persistence | Python 投影 compact `should-run` facts，在最多两次 reduction 之间调用真实 Todo provider，刷新 legacy status，并持有 cross-writer index lock |
| Runtime decoder（[#3443](https://github.com/huangruiteng/loopx/pull/3443)） | 稳定 primitive decoding 进入一个很小的共享模块；domain decoder 仍留在本地 | 没有理由建设更大的 schema framework |
| Transaction 兑现（[#3464](https://github.com/huangruiteng/loopx/pull/3464)、[#3481](https://github.com/huangruiteng/loopx/pull/3481) 与 Todo completion） | Turn settlement、quota delivery routing 与 Todo completion 均只跨一个粗粒度 TS boundary；Todo transaction 拥有 identity、replay fence、validation planning/result reduction、continuation/recovery 与 completion metadata | Python 仍执行显式 external provider，并物化 legacy Markdown/event result；其他 domain 仍需各自的 bounded cutover |

Scheduler facade exit 已交付第一段有边界的 Stage 3 路径。带版本的
`heartbeat_followup_cli.ts` 从生成的 ACK/failure hint 接收有大小上限的 compact host
facts，校验原始 heartbeat receipt，并在一个 Node 进程内完成 state validation、
replay/CAS fencing、锁内写入，以及 public JSON/Markdown projection。Unix、Windows
和 wheel 安装后的 console launcher 只为精确匹配的 receipt-bound command 选择这条
路径。持续运行的 host path 因此不再启动 Python，也没有 Python 到 Node 的
request/response。旧 Python ACK rule 与只服务 adapter 的测试已经删除，不再形成第二个
semantic owner。无决策权的 Python compatibility adapter 暂时服务显式 in-process call
与手工构造的 unbound call，等这些 caller 改用生成的 receipt-bound hint 后即可删除。
Host automation adapter 及其 TOML/SQLite 写入仍有意留在 Python，并处在这笔
transaction 之外。

这些切片已经证明 correctness、packaging、Windows lifecycle、crash recovery、真实
TS-owned write 和可接受的 warm primitive-call latency。它们也暴露了迁移边界：
逐 leaf 翻译会先增加 TypeScript、facade、parity fixture 与 bridge traffic，尚未删除
足够多的 Python composition。

### 3.2 兑现阶段决策

迁移因此进入 **transaction-payoff 阶段**。后续 leaf migration 默认拒绝；只有它
能在同一 PR 或明确的紧邻 bounded follow-up 中直接解锁完整 transaction cutover
与删除时才例外。进展单位改为 operator 可感知的 transaction，而不是 helper、
enum、dataclass 或源文件。

一笔 transaction cutover 必须：

1. 把 validation、state transition、已迁 internal effect 和 result construction
   放到一个 domain-owned TS request/response boundary 后；
2. 删除被替代的 Python rule composition、细粒度 API、重复 enum/dataclass 和
   implementation-specific test；
3. 让 Python 只保留 transport、legacy response projection，以及仍属于外部
   authority 的显式 adapter；
4. 不允许 leaf-level bridge chatter。Effect provider 已迁入 TypeScript，或没有待执行
   provider 的 replay，只使用一次 request/response。真实 provider 仍在 Python 时，
   最多使用两次：一次 fail-closed preflight 授权具名 effect，一次基于已 checkpoint
   outcome 的最终 reduction。Model call、human gate 或第三方 mutation 会开启一笔
   新的、带 receipt 的 transaction，而不是隐式 callback tunnel；
5. 写明 Python facade 与 bridge operation 的精确删除条件。

Domain invariant 仍归各自 bounded owner。“更粗粒度”不等于建立一个万能控制面
command 或 mega-reducer。

## 4. 迁移顺序

### Stage 0 — 固定行为与 authority（已完成；每笔 transaction 重复执行）

每个选中的 transaction 都要记录权威 schema、经独立 review 的合法/非法
transition、生产 caller 与 side effect、matched latency/install baseline，以及
rollback/state-compatibility boundary。Characterization fixture 是临时迁移证据，
不是永久 specification。

### Stage 1 — Effect Program 与 managed runtime 基础（已交付）

TypeScript Effect algebra、settlement 语义、Turn-journal interpretation、durable
checkpoint effect、runtime lifecycle、packaging、upgrade fingerprint 与 boundary
decoder 基础都已进入 `main`。Stage 1 的 settlement facade 清理已完成：Python
细粒度 settlement reader 已移除，coarse readback/projection 留作有界的 Stage 2B 工作。

### Stage 2A — Bounded rule-owner 证明（已交付；不再复制该模式）

Todo completion、quota workspace causality、scheduler transition 与 scheduler
durable state 已证明 Python caller 可以安全切换到唯一 TS semantic owner。它们的
characterization 与 facade layer 是合适的迁移证据，但继续在更多 domain 平铺相同
leaf pattern 会增加总复杂度。

### Stage 2B — 完整 transaction cutover（进行中）

按删除杠杆与 runtime traffic 选切口，而不是按翻译难度选。已经交付的 Turn
settlement、quota delivery routing、Todo completion、scheduler heartbeat、quota
spend commit、quota void commit 与 task-lease acquire cutover 建立了这一模式。后续候选必须明确剩余
transaction 及其删除杠杆；剩余 quota settlement readback 只有在能退出或显著收窄
facade，而不是再增加 leaf handler 时才适合迁移。

每完成一笔 transaction，就用 native TS semantic/invariant test 加一个持久的
end-to-end adapter contract，替换 migration-only characterization worker 与 Python
implementation fixture。只有旧 authority 仍可执行，或 versioned compatibility
window 仍需 differential proof 时才保留 characterization corpus；引入时必须记录
删除触发条件。

当前实现状态：Stage 1、bounded Stage 2A proof 与已交付的 Stage 2B cutover 已就位：

- Turn settlement/commit：TypeScript 拥有 preflight authorization、ordered-prefix
  与 replay validation、provider failure classification、receipt construction、
  terminal closeout joining 和 canonical result。真实 Python provider 使用两次
  coarse reduction；完成态 replay 使用一次。
- Quota delivery routing：TypeScript 拥有 continuity 与 fallback 的选择，以及
  selected Todo 的 settlement boundary。In-flight 路径从两次跨 runtime 调用降到
  一次；空 candidate 的 short circuit 仍为零次。
- Todo completion：TypeScript 在一笔 transaction 中拥有 completion identity、
  terminal replay fence、validation declaration/effect planning、validation receipt
  reduction、continuation/recovery 与 completion metadata。没有声明 validation 的
  Todo（包括 replay）使用一次 reduction；真实 caller-approved validation command
  作为显式 Python provider，位于两次 reduction 之间。取得 mutation lock 后会比较
  source snapshot，确保一份 declaration 的 receipt 不能授权已经变化的 Todo。
  Materialized 与 event-projected 写入消费同一 typed result。
- Scheduler heartbeat/state 由 TypeScript 拥有 receipt freshness、ACK 与
  host-failure validation、带 identity 的 progression、failure-cache
  retention/counting、replay 与 CAS fencing、preview reduction、锁内 atomic write，
  以及兼容旧合同的 JSON/Markdown result。生成的 receipt-bound ACK/failure hint 携带
  一份有版本且有大小上限的 facts packet，随后通过 native CLI 直接进入这笔
  transaction。持续运行的路径不再经过 Python。无决策权的 compatibility adapter
  只服务显式 in-process caller 与 unbound manual caller，等这些 caller 改用生成路径
  后即可退出。Host automation mutation 继续作为 Python 拥有的 external effect。
- Quota spend commit：TypeScript 重新校验 compact before/after transition，构造
  canonical public-safe spend event，以带锁 index CAS fence effect，并把 JSON、
  Markdown、index 与 transaction receipt 作为一笔可修复操作提交。同一 effect retry
  幂等，跨 effect 漂移冲突，prepared transaction 可修复 partial artifact set。
  receipt 绑定 append 前的 index digest 与字节偏移，因此 retry 只会修复属于本事务的
  截断 JSONL 尾行，其他损坏仍然 fail closed。
  Python 只保留 `should-run`/settlement fact projection、一次 coarse transport call 与
  legacy kernel index lock；它不再构造或写入 spend event。
- Quota void commit：TypeScript 在 mutation lock 内定位被引用的 spend，归约
  before/after accounting decision，构造 canonical correction，并通过闭合的
  spend/void accounting-artifact kernel 提交 JSON、Markdown、index row 与 prepared
  receipt。同一 effect 的 retry 会 replay 或修复同一 transaction；新的 CLI invocation
  仍是新的 effect，因此保留对同一 spend target 再追加 correction 的既有行为。
  Malformed index row 现在由静默跳过改为 fail closed。Void artifact 文件名加入
  effect digest，JSONL row 改用 compact JSON；public payload 语义保持稳定。共享 kernel
  同时加固既有 spend recovery 的持久化 receipt/path identity。Python 只保留
  `should-run` facts、UUID/clock、一次 coarse transport call 与 legacy cross-writer
  index lock。
- 本地 task-lease lifecycle：native TypeScript transaction 现在拥有 acquire、renew、
  transfer、release、terminal verification、holder verification 与 fence close。它们拥有
  boundary decode、handoff 与 owner/Todo eligibility、同 Todo 与重叠 write scope
  conflict、compare-and-swap、generation/idempotency rule、operation/fence receipt、
  per-goal mutation lock、atomic lease persistence 及 canonical result。Python 只投影带有
  前后 source digest 的 compact registry、active-state、event-log 与 rollout-log facts，
  然后执行一次 native transaction call。TypeScript 在 lease lock 内、decision 前和
  write 紧前重验 source。Closed fence replay 与 generation 绑定：non-required receipt
  仅在 lease record 仍不存在时可重放；已提交 release 必须仍匹配同一 retired
  generation；aborted close 只能在新锁下重验同一 active generation。
  Provider-neutral coordination executor 通过 typed Python adapter，对 acquire、renew、
  transfer、release 到达同一份纯 TypeScript decision；#3669 跟踪的 shared provider
  execution、CAS 与 authority receipt 仍不属于本次 cutover。
- Quota monitor-poll commit：TypeScript 复核 quiet、due、external 与
  exact-blocked-wait admission，构造 canonical monitor target/event，在 mutation
  前记录 Todo-provider intent，并拥有 effect replay、index CAS、artifact path
  fence 与 prepared/committed repair。无 Todo 的 poll 和所有已完成 replay 都只用
  一次 reduction。真实 Todo writeback 仍是显式幂等 Python provider，位于一次
  preflight 与一次 final reduction 之间。Provider retry 绑定到持久化 monitor
  effect identity，较旧 effect 不能覆盖更新 observation。
- Task-lease acquire：TypeScript 拥有 identity normalization、settlement plan
  projection、provider failure classification、ordered receipt construction 与
  canonical result。Python 在一次 preflight 与一次 final reduction 之间调用现有
  atomic provider；provider 继续拥有 per-goal lock、owner eligibility、conflict、
  compare-and-swap、idempotency 与 lease-file durability check。无效 identity 会在
  provider 前停止；provider 后发生 crash/retry 时则重入同 key 的幂等路径。

Quota-accounting cutover 删除了 Python spend/void event builder 与三文件 writer。
当 quota decision 与顶层 CLI 在进程内执行 TypeScript、全部 run-index writer 改用
native lock，并且 legacy Python void API compatibility window 结束时，它们的 bounded
facade 即可退出。在此之前，Python 只提供 compact projection facts、clock/effect
identity、result validation 与共享 legacy index lock。Todo cutover 删除了 Python
state-evaluation dataclass、local identity projection、
replay helper，以及这些 implementation leaf 的 public runtime handler。剩余 Python
Todo facade 只拥有 transport、external command execution、source compare-and-swap、
legacy response projection 与实际 Markdown/event write；当 writer 与 CLI 进入 native
TS transaction 后即可退出。剩余细粒度 Turn facade 则在 quota 与 host-adapter
caller 进入各自 coarse transaction 后退出。Task-lease semantic facade、Python atomic
provider、settlement bridge operation 与 lifecycle rule engine 已经删除。Python 只保留
compact source projection、一次 process transport、携带 opaque fence token/receipt id
的 context-manager plumbing、legacy response projection，以及现有 Python caller 所需的
compatibility import。顶层 LoopX CLI、Todo writer 与 authority-source adapter 在进程内
调用 TypeScript transaction 后，这些 surface 即可退出。Python/TypeScript 共享锁协议
仍服务于 Python handoff-mode transition 与其他跨 runtime holder；当不再有 Python
writer 获取 per-goal lease lock 时即可删除。Vision checkpointing 属于不同的
refresh/writeback 生命周期阶段，因此继续作为独立 transaction。

Lifecycle receipt 可以在 transport response 丢失或 owner caller 退出后，恢复已经完成
的 mutation 或 held/closed fence。长生命周期 fence lock 记录 Python caller PID，而不是
managed Node server PID；stale reclaim 会先取得 token claim，并用抗路径替换的文件身份
核验后再退役 lock。这不构成“同一 Node 进程内 handler 超时后仍并行执行时”的
exactly-once 保证；原 handler 可能仍存活时，caller 不得启动第二笔独立 operation。

#### Quota void commit 迁移经济账

| 字段 | 回执 |
| --- | --- |
| Canonical owner | 迁移前由 Python `slot_accounting.py` 拥有 spend-target lookup、correction reduction、event/result 构造、artifact 分配及 JSON/Markdown/index persistence。迁移后由版本化 TypeScript `quota.void.commit` 拥有这些语义，并通过闭合的 spend/void accounting kernel 拥有 effect fence、index CAS、receipt、replay 与 repair。 |
| 删除的旧语义代码 | 删除 212 行 Python 产品代码，包括原 void lookup、transition、event/projection、path allocation 与 JSON/Markdown/index writer 路径。 |
| 新增的 bridge 代码 | 新增 263 行 Python diff LOC，其中 243 行是有界的 `void_commit.py` transport/compatibility facade，另有 `loopx/quota.py` 与 legacy `slot_accounting.py` surface 中 20 行 import、re-export、normalization 与 route wiring。 |
| 跨 runtime 调用 | 公开 execute 与 dry-run 路径从零次 crossing 变为一次 coarse request/response。Exact-effect replay 或 repair 也使用一次。不同 CLI invocation 仍是不同 effect；legacy preview 加 record 两步 compatibility surface 的每个 entrypoint 各调用一次。 |
| 产品代码净增减 | 产品代码新增 2,210 行、删除 898 行，净增 1,312 行。Test/example 另计新增 1,416 行、删除 3 行，净增 1,413 行；build configuration 为 +3，docs 不计入。生产共享 kernel 已同时服务 spend 与 void，并替换 `spend_commit.ts` 中 671 行逻辑，不是预留的 speculative framework。 |
| 迁移 scaffolding | 没有新增 migration-only worker、parity corpus 或临时 schema framework。保留 native boundary/invariant/replay/CAS/repair 测试作为已交付和持久化 contract；Python bridge 测试随 compatibility facade 一起退出。 |
| Facade 退出 | 当 quota decision 与顶层 CLI 在进程内执行 TypeScript、全部 run-index writer 使用 native lock，并且 legacy `build_*void*`/`record_*void*` Python API compatibility window 结束时，删除 Python void facade。 |
| 正确性与性能 | Typed-decoder 负例、legacy target compatibility、effect isolation、index CAS、malformed receipt/path、exact index-row identity、受支持的 duplicate-index repair、concurrent mutation、truncated-tail repair、公开 CLI 行为，以及干净 wheel/sdist semantic probe 均通过。16 次 cold start 的 p50/p95 为 230.88/260.92 ms；128 次 warm typed ping 为 1.07/1.29 ms，warm void preview 为 1.93/2.34 ms。64 次 durable facade transaction 中，commit 为 30.64/37.49 ms，exact-effect replay 为 8.05/9.86 ms。Daemon RSS 在 idle 时为 108.38 MiB，256 次请求后为 109.80 MiB。64 对交错 full-CLI 样本中，baseline/candidate p50/p95 为 736.51/828.68 与 779.52/856.49 ms，p95 增量为 27.81 ms（3.36%）。这个绝对增量来自新增的一次 managed-runtime fingerprint/request 与 prepared-receipt durability；百分比低于 5% 物质回退门槛，Stage 3 会删除这次 crossing。 |

#### Task-lease acquire 迁移经济账

| 字段 | 回执 |
| --- | --- |
| Canonical owner | 迁移前由 Python 拥有 atomic acquire provider，TypeScript 在外层做 settlement reduction。迁移后由 `task_lease_acquire.ts` 拥有完整带锁 transaction 与 canonical result。 |
| 删除的旧语义代码 | 973 行产品代码，包括 Python provider/acquire 组合与 conflict 路径、Python↔TS settlement bridge/reducer 及 handler，以及 legacy CLI settlement projection。 |
| 新增的 bridge 代码 | 约 641 行 gross、有界的 compatibility 产品代码，包括 compact Python authority projection 加一次 managed-runtime request、compatibility import、Python/TypeScript 共享锁协议，以及 typed NoKV/coordination decision adapter。顶层 CLI 进入 Node 后删除本地 projection 与 import；其余 lease writer 与 fence 迁移后删除 dual lock；coordination executor 进入 native runtime 后删除该 adapter。 |
| 跨 runtime 调用 | 公开 acquire 与 replay 路径从两次 request/response reduction 降为一次 native transaction request/response。 |
| 产品代码净增减 | 产品代码 +2,130/−1,122 行，净增 1,008 行。Test 与 fixture 单独计为 +898/−1,081，build configuration 为 +4。 |
| 迁移 scaffolding | 删除 task-lease settlement characterization、fault-matrix、incident-replay 及其 fixture 切片。以 native invariant、crash/retry、direct-CLI、adapter 与 cross-runtime lock 测试取代；不再保留 migration-only worker。 |
| Facade 退出 | 本次删除 semantic facade、atomic provider、settlement operation 与 legacy CLI projection。仅保留 source/transport compatibility 与 cross-runtime serialization，删除条件如上。 |
| 正确性与性能 | 公开 CLI 在 5 个 acquire/replay/failure 场景与旧实现精确匹配；20 个 focused native test、207 个 Node test、4,615 个 Python test（12 个 skip）、crash/retry 与 packaged-wheel smoke 通过。在匹配的 16 样本 full-CLI 测试中，happy-path p95 从 1,593.7 ms 变为 1,167.8 ms，replay p95 从 513.3 ms 变为 445.4 ms；中位数分别为 364.6→425.6 ms 与 343.3→351.9 ms。 |

#### Task-lease lifecycle 迁移经济账

| 字段 | 回执 |
| --- | --- |
| Canonical owner | 迁移前由 Python 围绕 native acquire transaction 拥有 renew、transfer、release、terminal/holder verification 与 fence close。迁移后由 `task_lease_lifecycle.ts` 拥有全部六个 operation、锁内持久化及 canonical receipt/result。 |
| 删除的旧语义代码 | 删除 Python lifecycle decision、CAS、lease write 与进程内 fence rule 路径；Python 只保留 authority/source projection、managed-runtime transport、context-manager adaptation 与 legacy public payload projection。 |
| 跨 runtime 调用 | 每个 lifecycle verb 使用一次 coarse native request/response。Held fence 有意跨 verify 和 close 两次调用，因为 caller 的 Todo mutation 位于两者之间，并持续由同一个 lock token 授权。 |
| 恢复契约 | Operation receipt 绑定 retry identity 与 expected generation。Fence receipt 区分 acquired、held、closed；返回幂等结果前会重验当前 authority 以及当前或 retired lease generation。 |
| 锁迁移债务 | PID liveness、token claim、stale reclaim 与抗替换文件身份使 Python/Node 共享锁可安全恢复。handoff-mode transition 与所有剩余 Python lease-lock holder 进程内迁移后，删除这层有界协议。 |
| 非目标 | 本次 cutover 共享 ordinary lifecycle decision，但不实现 #3669 的 shared-provider execution、CAS 或 authority receipt；也不承诺 client timeout 后原 Node handler 仍运行时，第二个请求具备 exactly-once execution。 |

Monitor-poll cutover 删除了 Python admission-policy、monitor-target module，以及
Python event/replay/artifact writer。它的 bounded facade 会在 quota `should-run`、
Todo monitor persistence、status projection 与剩余 run-index writer 都进入原生
TypeScript 进程后退出；在此之前只承载 compact facts、具名 Todo provider、legacy
after-projection 与共享 Python index lock。

本次 cutover 以最终 merge-base 计算的 migration economics receipt 如下：

| 字段 | 证据 |
| --- | --- |
| Canonical owner | 变更前由 Python `monitor_poll.py`、`monitor_poll_policy.py` 与 `monitor_target.py` 拥有。变更后，版本化 TypeScript `quota.monitor_poll.commit` transaction 拥有 admission、target/event/result 构造、replay/CAS、provider intent 与 durable artifact；Python 只保留 compact fact projection、具名 Todo provider、transport 与 legacy after-projection。 |
| 删除的旧语义代码 | 删除 826 行 Python 产品代码，包括 `monitor_poll.py` 中被替换的 601 行、161 行 policy module 与 64 行 target module。 |
| 新增的 bridge 代码 | 有界 bridge 新增 495 行 Python diff LOC，其中 455 行位于 `_NativeMonitorPollRejected`、`_mapping`、`_monitor_candidate`、`_due_monitor_candidates`、`_vision_wait_state`、`_registry_due_monitor`、`_decision_packet`、`_observation_packet`、`_index_digest`、`_native_result`、`_request`、`build_quota_monitor_poll_event`、`find_quota_monitor_poll_turn`、`_status_with_monitor_poll`、`_reload_status_after_monitor_writeback`、`_monitor_poll_failure`、`_capability_declaration_retry` 与 `record_quota_monitor_poll_for_decision`，另有 40 行 import/schema wiring。34 行 `_provider_writeback` 是真实保留 provider 的 adapter，不计入 bridge。 |
| 跨 runtime 调用 | 变更前整条路径由 Python 拥有，因此为零。变更后，无 Todo 写入、exact replay 或 recovery 使用一次 request/response；真实 Todo provider 运行时使用一次 preflight 与一次 final reduction。 |
| 产品代码净增减 | 产品代码新增 2,743 行、删除 831 行，净增 1,912 行；test/example 另计新增 1,045 行、删除 242 行，净增 803 行，docs 不计入。该临时增长交付一笔完整 transaction，不能连续复制；当 quota decision、Todo persistence、status projection 与剩余 index writer 原生化后，下一项删除是 495 行 bridge。 |
| 迁移 scaffolding | 删除 218 行 implementation-specific policy smoke 与 18 行 target-helper assertion。没有提交临时 parity harness；保留 typed boundary、public CLI、replay/CAS、malformed input、provider 与 repair 测试，因为它们表达已交付或持久化 contract。 |
| Facade 退出 | Python facade 只剩 compact source facts、Todo provider、一个共享 cross-writer lock、transport 与 legacy result projection。当 `should-run`、Todo monitor persistence、status projection 与全部 run-index writer 在原生 TypeScript 进程执行时删除。 |
| 正确性与性能 | Identity/admission、effect isolation、provider fence、malformed receipt、concurrent CAS、crash repair、packaging 与 launcher coverage 均通过。Managed runtime 的 cold start p50/p95 为 274.35/450.44 ms，warm event 为 1.13/1.72 ms，durable commit 为 2.06/2.27 ms，idle/burst memory 均为 126.0 MiB。在把 prepared-plus-staged receipt 序列收敛为一份保守的 prepared WAL、继续以 index 作为 commit proof，并且只在 registry 可证明位于 Git worktree 之外时跳过 Git subprocess 后，最终 64 对交错 full-CLI 样本中，Todo write 的 baseline/candidate p50/p95 为 663.34/971.40 与 631.96/878.10 ms，candidate p95 增量为 -93.31 ms（-9.61%）；replay 为 598.23/910.75 与 580.13/900.69 ms，candidate p95 增量为 -10.06 ms（-1.10%）。两条路径的 p95 增量均同时落在完整 CLI 的 5% 与 25 ms 门槛内，因此此前的 owner-review hold 已解除。 |

### Stage 3 — CLI 与 App 汇合

交付 native TS CLI，并在进程内 import kernel。只保留一个自动选择的 authority
路径：CLI-only 时进程内直接执行；App/scheduler 已拥有 workspace 时连接 managed
daemon。所有生产 caller 不再需要 Python bridge 后，删除 bridge 与协议。

Receipt-bound scheduler ACK/failure 是本阶段第一段有边界的 native CLI 切片。它只做
精确 launcher dispatch，没有引入通用 Node router。`quota should-run`、host automation
mutation 与更广的 quota policy 继续由原 owner 负责。

### Stage 4 — 清理分发

通过 npm 与 LoopX release artifact 分发 kernel，删除 Python runtime 依赖，并
决定可选 daemon 使用普通 Node entry point 还是 LoopX 自建 single executable。
不要静默依赖非官方第三方 Node wheel。

## 5. 兑现阶段 PR 合同

后续每个迁移 PR 都要在描述与 validation comment 中附一份 **migration economics
receipt**：

| 字段 | 必需证据 |
| --- | --- |
| Canonical owner | Cutover 前后分别由谁拥有；不得存在模糊双 authority |
| 删除的旧语义代码 | 删除的 Python rule、细粒度 API、enum/dataclass 与 implementation-only adapter 的产品 LOC |
| 新增的 bridge 代码 | 仅为 Python↔TS transport 或 compatibility 新增的产品 LOC |
| 跨 runtime 调用 | Happy path 与 recovery path 在变更前后的 request/response 次数；effect 已由 TS 拥有或没有待执行 provider 时目标为一次，否则真实 Python provider 尚存期间最多一次 preflight 加一次最终 reduction |
| 产品代码净增减 | 产品 LOC 的新增减去删除；与 test、fixture、generated file 和 docs 分开报告 |
| 迁移 scaffolding | 新增、保留或删除的 characterization/parity helper，以及具体删除触发条件 |
| Facade 退出 | 本次已删除，或列出精确剩余 caller/compatibility contract 和删除条件 |
| 正确性与性能 | 与变更 transaction 相关的 invariant、负例、matched end-to-end baseline、packaging、crash/retry 与 host coverage |

LOC 以最终 merge-base diff 为准，并把 production code 与 test、fixture、generated
file、docs 分开分类。搬移代码按删除加新增计算；bridge LOC 必须列出那些唯一职责是
跨 runtime transport 或 compatibility 的函数。Round trip 要在一条具名 public
happy path 及其 retry/recovery path 上实测，不能由 handler 数量推断。

只搬动代码、只新增 handler，或扩大 bridge 却不删除 authority 的 PR 不能通过这一
阶段。一笔 cohesive transaction 可以暂时净增代码，但 receipt 必须说明 bridge
为何有界，以及下一次哪项删除会兑现收益；这个例外不能被串成无限 leaf migration。

稳定 primitive decoder 可以复用现有的小型 runtime decoder module。Domain decoder
仍留在各自 bounded context；本 RFC 不授权 generic schema framework。

## 6. 正确性与性能门禁

### 正确性

- 独立定义 algebra properties：identity、适用场景下的 associativity、ordering、
  short-circuit、replay 与 effect-id isolation。
- pinned characterization corpus 输出精确一致。
- malformed state、cross-effect overwrite、partial commit、cancellation、
  permission denial 与 budget rejection 的负例。
- 边界 decoder 必须在 domain dispatch 前拒绝缺失字段、错误类型、不支持的 schema
  版本，以及 oversized 或 malformed payload。Cutover inventory 必须列出仍存在的
  `as unknown as T` 迁移缝并证明其已受保护；promotion 要求移除已迁 domain
  authority 输入上的未经验证断言。
- 被 `await` 的写入只有在其声明的 durability point 成功后才能发出 receipt；同 key
  并发 mutation 必须串行化或使用经过测试的 CAS 合同，retry identity 必须区分同一
  Turn 内连续发生的 checkpoint。
- 进程 crash 与 retry 不得重复已经提交的内部 effect。
- wheel 与 sdist 安装到全新环境后，从打包文件执行 deep semantic probe。

#### Caller 可观测语义是 promotion 门禁

每笔 Python 到 TypeScript cutover 在实现前都要盘点所有生产 caller 分支的行为。盘点
包括：可接受输入与默认归一化；已传入、未传入、空值与显式清除参数；资格与重叠拒绝
的优先级；完整诊断与修复建议；从 dispatch 到持久化后独立 readback；authority、
ownership、receipt 与 no-effect 结果；以及 transaction 支持时的 replay 或并发更新。
只有相同 reason code，或 provider conformance 通过，不足以证明 parity。

Cutover PR 必须分别为不可变基线 revision 和精确审查 head 记录机器可重放的执行
receipt。除非声明且独立批准有意差异，两次运行必须使用同一有界脚本、合成 fixture
指纹、公开生产入口与真实受影响 backend。每个 receipt 都要写明 revision、命令、
backend、退出状态、归一化观测指纹，以及公开安全的证据指针或内联观测。归一化可以
消除临时路径、时间戳等已记录的非确定性，但不得消除诊断、字段存在性、优先级、
持久状态、identity、ownership 或 effect 差异。

同一 harness 还必须证明回归敏感性：它要在历史缺陷或一个故意注入的语义 mutation
上使独立定义的 invariant 失败，并在修复 head 上通过。Mutation 例如丢弃字段或诊断
细节，或引入更强前置条件。绕过生产入口的单测，或所有 provider 都已共享候选规则
的测试集，只能算辅助覆盖，不是 baseline/head 证明。如果无法安全运行真实 backend
或不可变基线，promotion 必须以 `not_yet_proven` 暂停；文字说明不能豁免该缺口。

这项验证是离线证据，不是第二份 authority。生产环境不同时运行 Python 与 TypeScript，
不从候选实现推导期望结果，cutover 后不保留 legacy rule。有意行为变更必须与 parity row
分开，根据公开 contract 说明理由并显式批准。Promotion 后只保留表达持久公开或
持久化语义的 fixture。

Characterization output 是证据，不是 specification。Pinned 行为若与独立 review 的
invariant 冲突，PR 必须披露，并把行为变更单独批准。旧 authority 删除后，promotion
还要求删除只服务这次实现对比的 characterization machinery；当 fixture 表达 public
或 persisted compatibility contract 时，可以保留为持久 regression test。

### 性能

Cold startup 与 steady-state 分开测量。每笔 transaction cutover 必须报告：

- managed runtime cold-start p50/p95；
- warm typed request p50/p95；
- representative complete transaction p50/p95 与跨 runtime round trip 次数；
- 相比 pinned Python baseline 的完整 CLI p50/p95；
- idle 后和 bounded request burst 下的 daemon 内存。

默认验收目标仍是 warm、non-durable internal transition p95 低于 2 ms，完整 CLI
不出现物质回退（p95 超过 5% 或出现无法解释的 25 ms 额外开销）。Durable
transaction 要和 matched durability baseline 比较，而不是套用 2 ms kernel budget。
不达标，或用更快的 microbenchmark 隐藏 tail regression，都是 owner review gate，
不能静默放宽。

## 7. 安装、升级与回滚

迁移不能要求用户管理服务。Python 过渡版本可以要求 Node.js 22.6 或更新版本，
但 installer 与 `loopx doctor` 必须在正常控制面工作前检测，并给出精确修复方式。
Wheel 与 sdist 携带 TS source 和版本化 schema。

Runtime 因 idle 退出时仍是健康状态：`stopped` 表示下一次控制面请求会自动拉起，
不表示用户需要手工执行 daemon 命令。CLI 与 App 消费同一个 lifecycle projection
（`running`、`stopped` 或 `unavailable`）和稳定 diagnostic code；raw stderr、token、
本地路径和私有 runtime metadata 不进入投影。

Runtime fingerprint 包含每个实际执行的 TS module 与 contract。升级会启动新
fingerprint 的 runtime；旧进程可完成 in-flight work，并在 idle 后退出。Request
携带稳定 effect identity；只有显式幂等的 handler 才允许 transport retry。

Rollback 恢复上一版本 artifact 与 fingerprint。在单独通过 state-schema cutover
前，不把持久化状态改写为 TS-only 格式。

## 8. 非目标与停止条件

- 不永久维护 Python/TS 语义双胞胎。
- 不为每个 domain 建 server，也不建 arbitrary-command 通用 executor。
- 不 big-bang 重写 CLI。
- 不以 dual-write production semantic state 作为迁移策略。
- 不只凭 microbenchmark 声称性能。
- 不因 bridge 已存在就继续平铺迁更多 leaf helper。
- 除非存在具名 public import、persisted wire contract 或未迁 caller，不保留重复的
  Python enum/dataclass。
- 不为已经不存在的实现永久保留 characterization harness。

如果 bridge 需要用户手动管理、已迁规则仍有 Python 语义 owner、handler boundary
变得 chatty、连续两个 PR 增加 bridge/scaffolding 却没有退出 facade，或一笔
transaction 只能靠削弱既有行为才能通过 invariant/recovery/performance 门禁，
就停止或 replan。
