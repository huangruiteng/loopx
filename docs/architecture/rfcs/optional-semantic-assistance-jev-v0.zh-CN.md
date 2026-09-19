# RFC：LoopX 可选语义增强方向、优先级与降级契约——TypeSafe/Jev（v0）

- **RFC status：** Draft，待维护者评审；不是已接受的架构决议。
- **Delivery maturity：** Proposal；仅文档提案，没有交付 Jev 运行时接入或模型质量验收。
- **Created / Last normative revision：** 2026-09-19。
- **Implementation baseline：** `9f1916960306b3650d795895b89f331eeae2516e`，已核对相关 owner 源码，并单独检查官方 main 至 `cc8e28d8b58a9b15e928d7e2cee16097172567d1` 的差异；不是全仓或运行时认证。
- **Authors / owners：** 各方向保留原领域 owner；跨方向协调人为待定维护者角色，不新设运行时权威。
- **Language mirror：** [English](optional-semantic-assistance-jev-v0.md)
- **Related contracts：** [总体路线图](loopx-overall-roadmap-v0.zh-CN.md)、[Decision Context](../../reference/protocols/decision-context-architecture-v0.md)、[Goal acceptance](../../reference/goal-acceptance-observations.md) 及第 4 节领域映射；已有领域 RFC 保留权威。

## 文档地图与维护契约

第 1–10 节定义拟议边界、方向和验收，第 11 节定义有限交付计划，第 12 节列未决问题；附录记历史和证据。第 4 节区分源码/既有契约与设计建议。方向 D1–D6 是文档定位符，不是新全局枚举、任务状态或强制六个 PR。中文是英文的语义镜像，两版规范须同步；候选方向排序不构成运行、数据出站或推广批准。

命令、字段和模块除明确标注现有者均为建议。准许一个方向不自动准许另外五个方向。优先级不是准确率、收益实测或固定工期。

## 1. 决策摘要

本 RFC 讨论六个 LoopX 与 Jev 的结合方向，按产品价值、契合现有 owner、输入证据就绪程度、误判后果、成本和可退出性排序。只选择一个具名方向先形成端到端闭环；不先建设通用智能控制器。

**LoopX 的必要业务流程不依赖新增的 Jev 账户或 API key。** Jev 是可选增强，不是必经裁判。配置缺失或关闭保留旧行为；显式启用但无 key、API 失败、预算不足或结果不可用时，回到该场景已定义的基线路径，并清楚标记未完成的模型判断。

三个边界始终成立：

1. 可以降级的是可选增强，不是身份、权限、来源、验收、结算、租约或必需人工评审。
2. 无模型不意味着本地规则能等价理解自然语言；保留现有能力并披露缺口，不伪造概率或正常结论。
3. 持有 key / 安装 skill 不等于启用、访问私有证据或允许第三方上传。不得因 Jev 不可用就隐式调用其他云模型或下载本地模型。

本 RFC 不批准自动 replan、pause、redirect、合并 PR、修改 Goal、解除 gate 或绕过已配置 verifier。D4/D5/D6 未来一旦改变 worker 上下文、排序或动作输入，必须按现有影响/权限政策单独准入。

## 2. 问题、目标与不变量

用户希望长周期工作不因合法字段和忙碌表象失去目标，也希望开发者更容易发现可复用概念、评审更快定位有效证据、技能与材料更易选择。Jev 可能帮助理解这些非结构化含义，但不应成为安装、运行和 CI 的新障碍。

成功不是接通六个 API，而是在一个真实场景中，证明可选推断带来可观察的额外价值，且无 key 时仍有可运行、可信的基本路径。

### 不变量

- **I1：Core 权威不变。** 原来拒绝的工作不能因 fallback 或高 confidence 获准；模型不能否决原有确定性保险丝。
- **I2：默认无副作用。** 关闭路径不读凭证、不建 client、不联网、不增加文件或 worker hook；原命令输出不变。
- **I3：基线路径真实存在。** 每个方向须定义无模型时的输出、遗漏能力和负责决定者；新功能不能把不存在的本地检测器当作 fallback。
- **I4：未知如实。** 未运行、服务失败、模型弃权、低信心、基准过期分别表达；均不等于无漂移或评审通过。
- **I5：证据、推断与行为分开。** 工具退出码、版本、实际产物读取仍是事实；模型结果是建议；当前权限决定行为。
- **I6：访问和上传分开。** 同 Goal/Agent/项目归属和来源权限通过后，仍需目的地、数据类别、预算与留存授权。
- **I7：单一领域 owner。** D1 不接管 D2/D3 的规则；模型适配器不成为资料读取器、上下文检索器或第二个 evaluator。
- **I8：有界与可退出。** 无隐式重试、无限队列或静默换模型；禁用/卸载后现有工作保持原规则。
- **I9：复用但不强推框架。** 在第二个真实场景证明确有相同传输需求前，不创建通用注册中心或任务 DSL。
- **I10：证据信用独立。** key 缺失可以使 live 测试 skipped，不可以使模型资格测试 passed；落地与推广分别记录。

## 3. 六个方向与优先级

### 3.1 总排序

| 顺位 | 方向 | 优先级 | Jev 提供的增量 | 无 Jev 的有效基线 | 最大允许的首轮影响 |
|---|---|---|---|---|---|
| D1 | 任务进展与目标偏离观察 | P1，核心价值优先 | 理解目标、真实产物与有限历史的相关性和增量 | 保留当前 typed repeat、frontier、writeback、验收及人工观察；自然语言偏离未评估 | operator 只读判断，不改变执行 |
| D2 | 新词 / owner 复用建议 | P1，低风险开发入口 | 比较本地发现候选与已有契约含义 | 无 npm 依赖的有界本地探针（尚需实现）＋已有 owner 线索/人工决定；原全树检查保留 | 提供提示，不自动登记/合并/消除候选 |
| D3 | PR 目标与交付证据对照 | P2，D1/D2后 | 比较 issue 的预期结果、diff 和独立证据 | 当前 exact-head review、`problem_context` 评审义务、测试与人工/既有 Agent 复核 | 附加审查线索，不产生批准 |
| D4 | 材料、证据和 recall 候选重排 | P2 | 对已获准候选作语义相关性排序 | 各调用方原来的候选排序、exact read、来源新鲜度和覆盖要求 | 先独立 operator 排序视图，不改变 worker 输入 |
| D5 | Skill / capability 选择建议 | P2，D4后 | 从已允许且可用集合选少量相关技能，也可全不选 | 原 catalog、host discovery、显式选择和权限校验 | 不安装、不激活、不执行；只展示建议 |
| D6 | Replan 候选比较与历史重复风险 | P3，研究性、后置 | 对既有且合法的替代方案比较目标关系、重复风险和缺证据 | 原 planner、候选排序、typed obligations、恢复与人工决定 | operator 比较表，不提交计划或触发新义务 |

排序建议依据是潜在价值与风险，不是模型能力已经证实。首个产品闭环默认选 D1；其有效 acceptance/证据源未就绪时，可以先选择 D2 做低风险完整试点，不为启动 Jev 提升 canonical authority 或虚构 Goal 基准。D2 就绪不是 D1 的必需依赖，D1 也不是 D2 的前置门槛。

### 3.2 D1：任务进展与目标偏离

**owner：** 建议 Decision Context。已有 progress / Replan / acceptance 保留权威。首批只处理已有效启用 owner-authorized acceptance 的同本地 Goal/Agent、可归属的已完成工作窗口。

**输入：** 目标与非目标、criteria、任务绑定和 revision；host 实际读取的前后产物/验证 readback；有序去重 Turn；作者自述单独标记。不能从 worker 自述、文件名或 opaque ID 推断当前目标；exact read 不是内容真实证明。

**两个独立判断：** alignment（直接推进、必要前置、偏离、证据不足）和 novelty（实质新证据、没有实质新证据、证据不足）。结果局部且私有，不加入 `ProgressResultClass` 或 `EffectiveAction`。

**降级：** 展示可得的原检测、已有验证及缺失证据；模型判断为 null。不能从“未发现相同指纹”推出没有任务漂移；缺少 canonical 基准不能降级从 Markdown 猜一个。原独立 gate 仍有效。

**首轮验收：** 真实进展、必要测试/研究、负实验、合理等待、只改 ID、自述相反、合法改目标、同 Turn 重试、缺失证据和注入对照；与完整原链路比较，不只比较一个函数。无 key 与原业务输出/拒绝对等。

### 3.3 D2：新词与 owner 复用

**owner：** 语义开发工具和 #4743 的本地探针；不是 D1 的 runtime 子流程。#4743 的探针仍是独立交付，不能把它当成已存在。

**输入：** 本地变更模式明确的 old/new carrier、新值、所在符号/槽位、有限 owner 说明与候选契约。支持显式提供未跟踪源码，不扫忽略的私有文件。先发现，再给相关线索；完全不匹配 registry 的新概念也要出现。

**Jev：** 建议哪个已提供 owner 值得调查是否复用，允许无合适候选和证据不足。不自动填写静态 `admitted_as`，不把相同字面量集等同相同语义。

**降级：** 完整保留本地候选、结构重复/重叠线索和 disposition 问题。作者理由或 `reuse_existing` 标签不是消音开关；原语义审查义务不变。

**验收：** 未注册且不相似的新集合、同值不同义、实际改用 import、只写理由未复用、普通文案、不支持 TS 形式、无 npm、无 key。模型 quality 只计算附加建议，不把规则发现计作模型召回。

### 3.4 D3：PR 交付证据对照

**owner：** `pull-request-review` 能力既有 exact-head review 和证据合同。

**输入：** 同一 base/head 的 issue 结果要求、限定 diff、真实测试和产物读回、作者声称及未验证项。引用先 exact read；汇总相同不等于逐站点等价。

**Jev：** 指出声称与证据可能不匹配、仅前置交付、需要深入看的部分；不是 reviewer、verifier 或 merge gate。

**降级：** 沿现有 review queue、代码阅读、problem_context、独立验证和人工/既有 Agent 流程继续。原来缺失的必需评审仍使合并不具备条件，不能因缺 key 而自动 APPROVE、`not_applicable` 或降低证据要求。

**验收：** 修复正例、只有 serializer/包装层、合理前置工作、相同事实不同宣传、head 变化、证据缺失；Jev 离线时不改变 review 完成规则。

### 3.5 D4：证据/材料重排

**owner：** 该调用方的 Decision Context / Material Lifecycle / Turn Recall；每个具体采用独立评审，不把三个领域合并成一个 registry。

**输入：** 本地已作权限过滤的有限候选、query、版本、新鲜度、必读/P0 标志；不让模型自行跟随 URI 或扩大来源。

**Jev：** 对同一可比问题下的候选评分/排序，模型置信度与相关性分数分开。保留完整候选和原排序；首版只展示一个单独建议视图。

**降级：** 采用原来的排序与必读要求。结果部分失败、超时或分数不可比时整次排序回退，不把未打分条目当成零分删除；禁止隐藏 P0 来源、冲突、缺失及过期。

**验收：** 候选召回与重排质量分开统计，强相关但过期/无权材料不得因高分升级为可信；无模型时排序与身份完全等价。未来自动改变 worker context 需独立 treatment 与数据/预算批准。

### 3.6 D5：技能与能力建议

**owner：** 现有 capability catalog、host discovery 与 `project_skill_delivery` 的原安装规则。

**输入：** 任务需求与已经允许、兼容、可用的候选说明。安装、可发现、启用、授权是不同状态。

**Jev：** 返回有限候选 ID 或不推荐，选择不能超出 supplied set。推荐不是安装或调用；不生成任意 import / 命令。

**降级：** 保留既有发现、默认路由和显式选择；Jev 缺 key 不让原技能全部消失，也不新建下载动作。

**验收：** 推荐不适用、全部无匹配、disabled/unready/未授权对象、结果未知 ID、profile 变化；无模型仍可列出和按原授权使用已有技能。不得以“省 token”默认把所有技能发到外部。

### 3.7 D6：Replan 候选比较

**owner：** 现有 Replan / Explore / planner；Decision Context 仅在真实 caller 需要时提供证据，不复制候选生成政策。

**输入：** 已产生且符合原权限/前置条件的有界替代方案、当前目标、可归属历史尝试和证据。外部 recall 如不可用必须标历史不完整。

**Jev：** 提供候选与目标关系、重复风险和证据缺口的比较。材料缺失不能报“从未尝试”；概率不直接转化为执行权。

**降级：** 继续原 planner/recovery/obligation 和既有人工路径。既有 Replan 所需新证据不能因为 Jev 不可用被免除，也不能仅因没模型创建新 gate。

**验收：** 既有拒绝不变、旧案例换 ID、真正的新 probe、历史不足、同 Agent 作用域、用户改目标；评估诊断与干预收益分开。自动选择、scheduler 变化、pause/redirect/replan 需要另一个明确的 L3 决策，不是本方向隐含交付。

## 4. 当前系统与已有 RFC 的关系

| 现有边界 | 可复用部分 | 本 RFC 不覆盖的权威 |
|---|---|---|
| Decision Context | default-off、来源读取、版本、证据与建议分离、provider fail-open | review settlement、`no_change`、cursor、outcome |
| progress / Replan | 精确 typed repeat、frontier/写回等原规则 | canonical progress、obligation discharge、花费 |
| Goal acceptance / Direction Baseline | D1 使用已有 acceptance；direction-material linkage 保留独立路线 | 不虚构完整 Goal intent 版本或已读回执 |
| 语义 RFC / #4447 / #4743 | owner、注册、检查及开发期提示候选 | 不替代 F1–F6，不扩大 tracker 关闭条件 |
| PR Review | exact-head queue、review 证据、明确权限 | 模型不认证 evidence truth，不批准/合并 |
| Reliability Diagnostics | 原 L1/L2/L3 权限区分 | 原 L1 空出站/不含原文契约；联网组件不得伪报 L1 |
| Post-writeback / Effect / TS migration | 主事务外具名 intent、既有 owner 与治理 | 不把模型调用塞进 writeback 锁或复制 TS 规则 |
| Skill delivery / extensions | 显式发现、安装、启用、doctor 与卸载 | 推荐不能创造域权限或自动安装 |

### 4.1 基于源码的归属与依赖映射

| 方向 / 关注点 | 现有源码或 RFC | 已观察边界及实施含义 |
| --- | --- | --- |
| D1 证据 | [Decision Context runtime](../../../loopx/capabilities/decision_context/runtime.py)、[sources](../../../loopx/capabilities/decision_context/sources.py)、[profile](../../../loopx/capabilities/decision_context/profile.py) | 已有来源获取、exact read 和作用域启用。`context_provider` 是检索接口，不是语义推理接口。在原 owner 下增加显式评估路径，保留原来源 review/cursor 结算。 |
| D1 目标基准 | [acceptance authority](../../../loopx/control_plane/goals/acceptance_authority.ts)、[acceptance contract](../../../loopx/control_plane/goals/acceptance_contract.ts)、[Direction Baseline RFC](goal-direction-baseline-v0.zh-CN.md)、[Alignment RFC](shared-goal-alignment-and-governed-amendment-v0.zh-CN.md) | canonical acceptance 已有 objective、non-goals、criteria 和任务绑定。Direction Baseline 仍为提案，本 RFC 不能创造完整 Goal-intent 修订权。只读已有有效 acceptance revision，不为此提升 provider。 |
| D1 原检测 | [progress observation](../../../loopx/control_plane/work_items/progress_observation.py) | `typed_progress_repeat_trigger` 比较连续有效等指纹 typed rows、去重可归属 Turn，只对 unchanged/blocked 触发；不是自然语言偏航检测器。较新的官方 main Replan 改动保留此边界，并把更多 discharge 语义交给 TypeScript。 |
| D2 开发提示 | [语义收敛 RFC](semantic-vocabulary-convergence-v0.zh-CN.md)、[inventory script](../../../scripts/generate_semantic_inventory.py)、[inventory](../../../loopx/semantics/inventory.py)、[#4743](https://github.com/huangruiteng/loopx/issues/4743) | 已有全树 inventory 和建议排名；脚本报告前会调用 `build_inventory`。有界 diff/no-npm 开发期探针仍是设计请求；须先交付真实基线，再称附加建议可用。本稿不关闭该 issue，也不批准其建议的 registry 字段。 |
| D3 评审 | [review contract](../../../loopx/capabilities/pr_review_queue/review_contract.py)、[result check](../../../loopx/capabilities/pr_review_queue/result_check.py)、[智能评审展示 RFC](intelligent-review-presentation-surfaces-v0.zh-CN.md) | PR 证据评审归 `pr_review_queue`；Intelligent Review 提供 typed 展示，只是未来可能的消费者。模型建议仍是后续可选阶段。`check_review_result` 检查证据声明的一致性，不验证其真实性；Jev 不替代 exact-head review。 |
| D4 检索 | [Decision Context](../../../loopx/capabilities/decision_context/README.md)、[Reward Memory](../../../loopx/capabilities/reward_memory/README.md)、[记忆效用 RFC](post-outcome-memory-utility-attribution-v0.zh-CN.md) | 复用真实 caller 的候选来源与排序。结果归因不等于排名影响已经验收。历史命名的 [cross-session memory RFC](cross-session-memory-substrate-v0.zh-CN.md) 交付的是有界 Todo continuation，不是通用检索存储。 |
| D5 技能 | [Project Skill Delivery](../../../loopx/capabilities/project_skill_delivery/README.md)、[extension 放置规则](../../reference/extensions.md) | 发现、安装、启用、领域权限分别存在；建议读取原已获准 catalog，不建第二套 installer/registry。 |
| D6 规划 | [Explore](../../../loopx/capabilities/explore/README.md)、[Research Exploration RFC](research-exploration-control-plane-v0.zh-CN.md)、[Manager Handoff RFC](capable-manager-semantic-handoff-v0.zh-CN.md) | 原 planner/manager 生成并采纳候选；检索或模型比较不能成为第二套 planner，不能解除 obligation。 |
| 自动化 / policy | [post-writeback hooks](provider-neutral-post-writeback-capability-hooks-v0.zh-CN.md)、[Effect Interpreter](agent-loop-effect-interpreter-v0.zh-CN.md)、[TS migration](typescript-control-plane-migration-v0.zh-CN.md)、[reliability RFC](long-running-agent-reliability-diagnostics-governed-delivery-v0.zh-CN.md) | M1 是显式 CLI 观察。日后自动调用必须使用原具名 intent/lifecycle，位于主事务之外；共享状态与 effect 权威保留 typed TypeScript，零外联 L1 collector 保持独立。 |

[总体路线图](loopx-overall-roadmap-v0.zh-CN.md) 继续管理组合：D1/D4 对应 S6/S11，D2/D3 对应工程 S8/S12 路径，D5 对应 S8/S12，D6 对应 S11。本稿不改排 R1/G1，也不宣称完成这些里程碑。官方 main 差异增加了协作/恢复与 Replan 能力，均不证明 Jev 已接入。表中源码现状、Draft 依赖与未来验收分别表达。

## 5. 共同接入与降级设计

### 5.1 最小结构

```text
现有领域入口与资格判断
    ├── 原有基线工作 / 原有候选与证据输出
    └── 显式 opt-in 的可选增强
          检查配置/出站/预算/输入当前性/凭证
          ├── 不满足：不调用，baseline + 明确未评估
          └── 满足：有界 Jev 调用 → 严格解码/当前性复核
                         ├── 不可用：baseline + 明确失败/弃权
                         └── 可用：baseline + 独立建议
```

“baseline”不是重复运行有副作用的主流程。使用已有输出/快照或纯规则；不能为对比再次完成、花费或写回同一工作。真正入口的权限检查仍由原 owner 负责。模型不在关键事务内执行，不持有 Goal/receipt/lease 锁等待网络。

仅 D1 初版落在 Decision Context。D2/D3 等留在各自 owner。共同传输/超时/解码可在出现第二个真实 caller 后抽取；不得为六个讨论项先建设 provider marketplace、全局场景开关矩阵或注册中心。

### 5.2 关闭、基线与增强三个可用状态

这是产品行为描述，不要求加三套全局 enum：

- **关闭：** 现有流程不变，key 即使存在也不查、不调用。显式 inspect 可输出关闭说明，既有普通命令不变。
- **基线运行：** 场景显式请求，但 Jev 缺 key、不可用或不允许调用；返回有效本地结果及增强未执行说明。
- **增强建议：** 准入后得到合法且仍适用的结果，显示独立 advisory，不把 baseline 改成已获模型认证。

有 key 不是自动启用。没有 Jev key 也不保证工作 Agent 本身不需要其原 provider 凭证；本 RFC 只消除“新增 Jev 凭证”的强制依赖，不把云 Agent 宣传成完全离线。

### 5.3 降级矩阵

| 条件 | Jev 处理 | 原业务 | 诊断信息 |
|---|---|---|---|
| 关闭/无新配置 | 不构造 client，不读 key，不联网 | 保持原行为 | 仅显式 inspect 可说 disabled |
| 已请求但 key 缺失 | 本地直接跳过，零网络尝试 | 沿原流程继续，包括原 hold | not_run / missing_credential，无 judgment |
| 有 key 但未允许上传 | 不发送，不换目的地 | 沿原规则继续 | not_run / egress_not_authorized |
| 模型预算不足 | 不发送，不占用工作花费额度伪装交付 | 原业务额度规则仍适用 | not_run / budget_unavailable |
| 必需来源不可用或基准冲突 | 不作当前判断，不从低权威内容猜补 | 原来源/gate 故障原样处理 | basis_unavailable / source_incomplete |
| 认证失败 401 | 记录失败，停止当前尝试，不重复试 key | 原流程不依赖该增强 | failed / authentication_failed |
| 429 / 529 / 暂时不可用 | 本次降级；无无界等待/自动重试 | 原流程继续 | failed / rate_limited 或 unavailable |
| timeout / 断网 / 进程中断 | 不确定发送则记录 may_have_been_sent | 不回滚主事务 | failed，未知费用不填零 |
| 请求错误 / 非法响应 / NaN / 不认识的 model | 拒收模型结果，暴露实现故障 | 不改变原决策 | failed / contract_error 或 invalid_response |
| 合法结果但弃权 / 低信心 | 保留原始判断及不确定性；不使用其改变排序/行为 | 走原路径 | completed-but-not-used，不伪称 API 失败 |
| 基准变化 / 关闭 / 迟到结果 | 不能采纳为当前建议 | 原状态保持 | historical / unusable |

API 故障可隔离，编程错误不能靠 `except Exception: pass` 静默吞掉。原权威存储不可用时不能因为“降级”改读旧 Markdown 并放行。若基线本来 blocked，降级后仍 blocked；若原来 requires review，仍需要 review。

### 5.4 输出语义与错误码

第 5.8 节定义拟议的局部结果封装；它不是修改 Core packet 的新协议。最少表达：基线引用、是否尝试/完成推断、未运行原因、实际 provider/model（未执行则无实际模型）、是否使用建议和 judgment。没有推断时 judgment/probability/confidence 必须为 null 或缺省，不能填 false/0/1 冒充结果。

外层业务命令退出码仍归原领域：原成功可带“增强未运行”，原失败不能变成功。独立 `doctor` 或显式要求证明模型可用性的资格命令，缺 key 时返回 unavailable/非零是合理的；它不是普通工作继续的前置。不要给所有命令套一个无条件 exit 0 的规则。

受治理 review、required verifier 和将来获批的控制点若本来要求特定证据，不能用本 optional policy 绕过。若将来把模型推广为 mandatory，必须新审 fail-closed/manual 路线和无 key 行为；不属于本 RFC 当前准入。

### 5.5 配置、来源和兼容

每个 caller 沿已有配置 owner 显式启用场景、provider、数据范围、预算和保留。D1 的原 `decision_context_profile_v0` 是严格形状；第 5.9 节建议由 Decision Context 管理显式 v1 迁移，不强迫其他方向共用它。旧版本不能静默丢弃新的数据出站约束，key 的存在也不能自动升级 profile。

新增可选 adapter 默认不增加核心强制依赖；lazy load，普通 import/install/test 路径不初始化第三方 SDK、下载模型或发起网络。使用 stdlib 并不自动满足总 deadline、重定向、TLS、限长和脱敏，须实测。模型版本固定于试点 profile，实际响应版本记录；不得静默退回 `latest`。

### 5.6 替代提供方和缓存

第一版默认 fallback 是原有流程，不是别的 LLM。已被用户授权、原流程一直使用的人工/Agent 复核继续存在，不因本设计新增额外模型调用。未来替代 provider 需要显式列表、各自数据授权、预算和资格；不借用其他环境变量中的 key，不把一个模型的 confidence 套在另一个模型上。

首版不新增隐式缓存降级。历史结果可读但不冒充新推断；若后续准许精确缓存，必须绑定同输入、来源版本、问题、model、policy、授权与新鲜度，并标 cached。启用过模型的旧结果不能使禁用配置继续增强。只匹配 Goal ID 或文字相似不足以复用。

### 5.7 首个完整切片与归属建议

建议首切片明确选择 **D1：显式 operator CLI 试点**。D1 缺少合格证据时返回 `basis_unavailable`，不自动切成 D2；改选 D2 需记录范围决定并满足本地探针前提。以下名称均为拟议，当前不可执行。

实施前的放置记录：

- **Capability：** 沿用 catalog id `decision-context`（packet 内为 `decision_context`），不新建内置 semantic-assistance capability。
- **Provider：** 拟议 `jev` 推理 provider，独立可选 extension 包放在拟议 `packages/loopx-jev/`；复用原 extension 生命周期，不另造 provider registry。本次文档改动不添加生产包。
- **Core owner：** Decision Context 最近的领域模块持有已完成窗口、本地基线、输入准入与私有结果读回；包负责有界传输和解码。不暗改 `DecisionSourceProvider` 或 recall `ContextProvider` 的含义。
- **Policy：** 复用原 typed acceptance/progress/Replan owner，不把规则复制进 Python 或 provider。特别是官方 main 的 Replan discharge 已领先于本分支基线的旧 Python 实现；场景局部建议不成为共享状态词汇。

拟议使用链路：

1. `loopx decision-context assess-progress` 沿用 Goal/Agent/profile 作用域，输入一个显式有界的已完成工作窗口。baseline 模式只作已授权本地读取；单独显式执行 opt-in 才允许推理。最终 flag 拼写由实施评审确定。
2. 通过 `inspect_goal_acceptance` 读取有效 canonical acceptance，保留 revision/digest 和 ready 任务绑定；读取 host 验证的产物版本、验证结果和去重 Turn 身份。作者自述标成自述。权威或必需材料不可用时，返回已有事实和缺口，不伪造基准。
3. 复用来源 `scan`/`exact_read` 与 coverage 语义，原文只短暂驻留；原 cursor proposal 不提交。基线返回 typed repeat 与可得的 acceptance/验证事实；不为了这个只读对照执行验证命令或重做工作。
4. 在仅为推理扩展材料或发送前，检查场景启用、Goal/Agent、来源权限、目的地/数据同意、凭证和辅助预算。缺 key 零网络尝试，只组装被允许的文本。
5. provider 单次调用有总 deadline、请求/响应限额，不重定向、不隐式重试；返回后复核 acceptance/source/profile revision 和启用状态。晚到或基准已变只作历史结果。
6. 展示基线、缺失来源、独立 alignment/novelty 建议；拟议 `assessment-status` 提供私有读回。读回不推理、不结算评审、不推进 cursor、不改变工作状态。

原 private pending-settlement 文件**不能**作为模型结果库：其 profile/cursor CAS 绑定的是 review settlement。只增加为读回与发送不明恢复所必需的有界私有 assessment/attempt 记录；复用原私有文件保护/原子写模式，不复用结算 schema，不建另一套 Goal/usage 权威。

### 5.8 最小局部结果与尝试契约

拟议 `decision_progress_assessment_v0` 仅属于 D1。以下终态结果必须用校验过的可辨识联合类型表达，不用散落布尔组合或文案分类：

| 变体 | 必需信息 | 不得推导 |
| --- | --- | --- |
| `not_run` | 本地原因、baseline/coverage、可得基准；dispatch 为 `not_sent`；没有 judgment/actual model | 未推理不等于没有问题 |
| `failed` | 有界错误原因，dispatch 为 `not_sent` / `may_have_been_sent` / `response_received`，用量 observed/estimated/unknown | 未知费用不是零；失败不能批准工作 |
| `completed` | 固定/实际 model、两题 typed answer、问题/policy revision、来源基准、费用来源；advice use 为 `displayable` / `abstained` / `low_certainty` / `stale` | 推理完成不是工作完成或评审回执 |

基准绑定 Goal/Agent、acceptance revision/digest、任务绑定、有序窗口身份、产物版本、获准输入摘要、profile 与问题 policy revision；摘要也保留私有。历史不可得要标缺口，不能伪作没有历史尝试。缺题、未知选项、非有限/越界概率、实际模型不兼容属于解码失败，不是弃权；校验完整选项集，并用文档明确的数值误差校验分布和。

两题分别用 Choice：alignment 为 `direct_progress`、`necessary_prerequisite`、`off_contract`、`insufficient_evidence`；novelty 为 `material_new_evidence`、`no_material_new_evidence`、`insufficient_evidence`。它们是拟议 D1 局部答案，不扩展 Core enum。合法的证据不足是 abstention；低置信度是另行校准的使用 policy。多个原因并存时，use status 按 stale、abstained、low_certainty、displayable 的优先级确定，保留详细原因。保留两份分布，不平均成单个 progress score，也不从新颖性推定因果成功。

尝试身份绑定显式 request id 与完整 basis/input/policy；同 id 不同输入拒绝。尝试生命周期与终态结果分开：`reserved` → `in_flight` → `terminal`，在此私有作用域原子完成 request-id 准入与额度预留；并发重复请求只返回 `pending`，不能再发请求或伪造终态失败/重放。联网前先持久化保守 send intent，崩溃后视为可能已发送，绝不自动重提。重复请求只读保留记录，不产生计费重试，并标历史/重放而非新推理。并发仅预留已配置辅助额度，未知费用在核实前保守占用。没有可信限额/记账机制时拒绝增强，不能借用 worker 交付额度；这是辅助记账，不是新增 work-spend receipt 或 scheduler。

### 5.9 配置、用户入口与降版

建议同一 owner 管理 `decision_context_profile_v1`：保留全部 v0 字段与语义，增加单独可选推理段，缺省关闭；不藏进 `context_provider.config`。推理启用服从外层 `enabled` 和 `enabled_agents`，不能产生并列作用域。该段声明场景、provider、固定 model、凭证引用（绝不是密钥值）、允许目的地/数据类别、请求/响应限额、总 deadline、并发/辅助用量上限、保留期和受众。实施评审须在 live 前冻结具体数值；零/无界/未知预算不能隐式解释成无限制。

M1 保留 v0 中 enabled profile 必须有 source 或 context provider 的条件：D1 在 canonical acceptance 之外还要求至少一个显式获准的本地产物 source。acceptance 本身不是来源绑定，不允许用虚假 recall provider 凑配置校验。

新 reader 接受不变的 v0 并禁用推理；旧 reader 拒绝 v1，因此启用前验证 reader 兼容，不能在旧进程背后改共享 profile。升级显式进行、保留 v0 字段和私有备份，启用前 inspect/readback。降版先停用并清空在途增强，再恢复校验过的 v0，不能在推理仍启用时静默删除约束。未知版本/字段关闭增强；其他领域沿自己的配置。

现有配置 UI 由 descriptor 驱动：[capability configuration](../../../loopx/capabilities/configuration_ui.py) 与 [Goal settings](../../../apps/presentation/dashboard/src/features/personal-workspace/goal-capability-settings.tsx)。核对基线没有注册 Decision Context editor，所以 M1 明确只交付 **CLI operator 使用**，沿原私有 profile owner，不宣称 Dashboard/Lark/worker 链路完成；本 RFC 不改编辑器或 UI。后续 UI 切片须注册到原 descriptor，复用同一 profile/result projection，展示缺 key/过期/错误/关闭状态，验证 preview/apply/readback 和打包前端。Lark 只能接收单独获准的 public-safe 投影，默认不得发送私有评估正文。

### 5.10 Jev 传输资格边界

[官方 API](https://docs.typesafe.ai/api) 使用 `state`、按键组织的 `questions` 和请求 `model`，返回对应答案与实际 model。D1 使用 Choice，严格校验两题和选项；关闭 SDK 自动重试，或使用同等有界传输。认证、请求校验、限流和过载需可区分。

[Confidence](https://docs.typesafe.ai/confidence) 是分布统计值，Noul 没有独立 confidence；它不是权限，也不是独立实测的 LoopX 结果正确概率。按场景和语言校准。2026-09-19 读取的 [模型页面](https://docs.typesafe.ai/models) 列出 `jev-1.13.0`，只是试点候选而非合格依赖；移动 alias 不适合冻结对照。公开文档仅证明接口说明，不是真实响应、留存协议或中文场景价值证明。

## 6. 设计取舍

采用“六方向讨论＋单场景落地＋领域基线保留”，而不是：强制所有用户配置 key；为 fallback 写第二个语义推断器；把词法 overlap 改名为概率；为模型结果增全局状态机；仅因高 confidence 直接动作；把 Jev 请求放进原 L1 采集器；无 key 自动改用其他云模型。

保留旧确定性规则不是无谓双轨。它们承担必需业务和验证，模型承担可选理解；两者不应声称同一结果的两个权威。只有取代了同责冗余时才计熵减；新增有价值的评估能力本身也有维护成本，需单独衡量。

## 7. 安全、隐私和影响边界

来源、schema、身份和数据出站失败时关闭增强；业务可用性则保留原状态。发送材料最小化，不上传完整轨迹、任意仓库、凭证或未授权 private benchmark。材料/注释/日志都是不可信输入，模型无工具且不能选取新地址。未知引用/命令不得执行。

模型结果可能敏感，hash 不是匿名化保证。结果默认私有、绑定受众并有保留期；不把原文写入公开 evidence、status、PR 或 log。保存来源摘要和答案只证明当时处理过程，不证明事实真实或允许复用 peer receipt。

原 L1 observer 不变，联网评估另行声明出站。D1 首版只供 operator；D3 自愿辅助仍不批准合并；D4/D5/D6 若将结果自动注入 worker 上下文，即使不执行命令也构成需要评估的影响。不存在“可逆所以免审批”的捷径。

## 8. 迁移、禁用与回滚

RFC-only 不改运行。每次仅启用一个已批准场景，原 default/off 行为先做特征测试。禁用后停止新调用、取消未发送请求、拒用在途结果；保留或按政策删除该功能的私有记录，不回退原 Goal、receipt、cursor 或 lease。

已经发出的数据和费用不能被代码回滚撤回。混合版本、配置转换与兼容 reader 由所属场景实现；不静默删配置限制。核心依赖与打包测试须证明卸载 Jev adapter 后原命令仍可用；profile 指向缺失 provider 时显示不可用，不能 import-time 崩溃。

## 9. 验证与验收

以下为待执行要求，不是本稿测试结果。

| 测试 ID | 用例 | 必须结果 |
|---|---|---|
| F01 | feature off、无 key、普通入口 | 无 secret lookup/client/network/新文件；基线成功与拒绝均不变 |
| F02 | 显式增强＋missing key | 本地有效输出存在，not_run；零网络尝试，无虚构判断 |
| F03 | key 存在但 disabled/上传拒绝 | 不发送，不偷偷借 key/切 provider |
| F04 | 原权限/receipt/source hold＋模型缺失/乐观预测 | 原 hold 保持，不自动 APPROVE 或 skip verifier |
| F05 | 401/422/429/529、timeout、坏响应 | 可见的有限失败与相应基线，未知发送/费用如实；无无限 retry |
| F06 | 低 confidence、弃权、部分题/候选评分缺失 | 分清 completed/unusable 与失败；排名全部回到原合法顺序 |
| F07 | Goal/Agent/source 错绑、基准在途变化 | 不发送或结果过期，不借 peer 身份，不把旧结果当当前 |
| F08 | 默认 CI 无 key、无网络许可 | 离线合同/真实入口测试可跑；live qualification 跳过并标未验证 |
| F09 | D2 无 npm、D5 provider/skill缺失 | 声明支持形式仍有本地信号；原发现/使用不因 Jev 失败消失 |
| F10 | 并发、重放、关闭、重启与发送不明 | bounded reservation、无重复副作用或自动再计费尝试 |
| F11 | import/install/卸载 | 核心无强制 SDK/网络/模型下载，旧配置及 ordinary status 不变 |
| F12 | 注入、自述相反、必读材料低分 | 无权限升级、伪造事实和必需来源隐藏；模型错误可观测 |

普通离线测试用注入 provider 答案保护合同，不假装验证 Jev 智能。真实 API qualification 显式 opt-in、获准输入和预算；没有 key 时 skipped/unverified，不把 fixture response 当 live。

各方向分别冻结独立 rubric、代表性数据、开发/留出任务族、误报漏报/弃权和成本指标。公共指标包括可用性、基线 parity、故障次数、延迟和额外用量；不能把不同场景的 Choice/Score/Noul confidence 直接求平均为全项目智能分。

D1 对照完整现有链路，D2 对照本地结构提示，D3 对照原 review，D4/D5 对照原候选方案，D6 对照原 planner。观察价值、建议价值与控制干预的因果收益分别证明；方向无收益允许停止。

### 9.1 D1 验收执行方法

实施测试必须用隔离的合成 Goal/Agent/source 与注入 provider 跑真实新增 CLI，不能只测解码函数。对 credential lookup、transport、Core write 使用一旦调用就失败的 spy；把普通 CLI 结果和权限拒绝与变更前冻结基线对照，再测试显式缺 key 报告、scope/basis 失败、provider 错误矩阵、进程中断、并发预留和读回。首个 operator 试点中的 F09 随 D2/D5 延后，不能标 passed。若触及 authority 路径，按其要求跑真实 backend 集成；绝不修改 active Goal 来做测试。

价值验证是另行 opt-in 的实验：采集答案前冻结基于产物的案例、独立人工标签、rubric、中英分层、留出任务族与用量上限；比较完整原工作流与同工作流加可见建议。带分母报告误报、漏报、弃权/覆盖、分歧、时延与额外用量；保留必要前置、负实验、合理等待、只改 ID 的假新颖性、相反自述和注入案例。数值采纳门槛必须在试点前确定，不能看到结果才改。无收益可以停止；API 可用和模型高置信度均不证明 operator 价值。

当前纯文档检查（不是 M1/M2 验收）：

```bash
uv run --extra test python examples/docs-governance-smoke.py
uv run --extra test python examples/docs-asset-integrity-smoke.py
git diff --check
```

## 10. 运行体验与可观测性

显式入口应显示：“基础流程可用；Jev 未配置，本次没有模型语义判断”，而非反复弹窗要求 key。缺 key 不默认开 user gate、发通知或创建 Todo。相同失败只更新有界状态，不让每 Turn 产生相同 attention 项。

状态读取不触发模型。若可得，记录请求/实际 model、来源与问题版本、是否使用结果、原始分布、时延和费用来源；未发送可记录零远端请求，发送不明确不得记录费用零。严格后台自动重试不在首版；之后若确需周期 caller，另外定义冷却、队列、预算和恢复探测。

key 修复后只在下一次明确授权调用重新评估当前材料，不回填历史结果或自动重放所有失败任务。禁用优先于缓存和旧在途答案。Jev 费用作为辅助模型用量，不能变成 worker 成功交付的 quota receipt。

## 11. 规范性交付计划

| 阶段 | 最小交付 | 进入/退出 | 明确不做 |
|---|---|---|---|
| M0 | 六方向优先级、共同降级、首个 owner 与边界 | 记录 Q1/Q2/Q3 推荐决定；双语/引用检查；维护者接受仍待决定 | 不为六方向都建空接口 |
| M1 | 一个首选场景的无 key/关闭/失败路径与可选增强完整垂直 | 默认 D1；基准未就绪可具名选 D2；F01–F12 按适用范围真实验证 | 不只交 HTTP client，不强制 Jev key，不改变 Core 权威/结算语义 |
| M2 | 同一场景的 live 资格和 operator 价值试点 | 单独有 key 环境、获准数据和冻结预算；可结论无优势 | 不从接口成功推导推广 |
| M3 | 第二个真实场景，才验证共同 adapter 复用 | 复用收益和领域隔离证明，两个 fallback 独立通过 | 不把 D1 配置强套所有 capability |
| M4 | 依据前两场景结果重新排列 D3–D6 | 每个场景独立 owner/ROI/隐私评审 | 没有承诺全量六方向必须完成 |

本 RFC 讨论版可在 M0 完成并待运行决策；不能把每个方向实施完当成 RFC 本身评审前置。[#4447](https://github.com/huangruiteng/loopx/issues/4447) 与 [#4743](https://github.com/huangruiteng/loopx/issues/4743) 保留独立范围与关闭条件。自动动作始终是另行提案，不作为隐藏 M5。

## 12. 待决问题

| 问题 | 推荐 | 决定者与阻塞范围 |
|---|---|---|
| Q1 首批方向与顺位 | 采用 5.7 的 D1 显式 CLI 试点；D2 需记录替代范围决定 | 项目/领域 owner；只阻塞对应 M1 |
| Q2 共同代码放置 | 首个场景局部实现；第二 caller 后再抽出真正共享传输 | 两个领域维护者；不设总语义权威 |
| Q3 配置/版本与无 key 输出 | 5.9 的 D1 v1 迁移，独立推理段，保留 v0 与普通输出 | profile/CLI owner；M1 前 |
| Q4 数据、模型与预算 | 显式目的地/类别、固定模型、单次有界、无自动重试 | privacy/运维/评估 owner；live 前 |
| Q5 是否支持替代模型 | 首版不支持自动替代；后续逐一 opt-in/评估 | 用户与 capability owner；不阻塞本地 baseline |
| Q6 排序/skill/计划影响何时获准 | operator-only 先行；worker adoption 独立 treatment | host/Goal/安全 owner；只阻塞相应影响 |
| Q7 何时升级门禁 | 当前不升级。若未来必需 verifier，另审 fail-closed 与人工方案 | 当前权威 owner；不从 confidence 推定批准 |

## 附录 A：执行记录（非规范）

### 2026-09-19 — 首版源码对齐提案

- **基线：** `9f1916960306b3650d795895b89f331eeae2516e`，另查至 `cc8e28d8b58a9b15e928d7e2cee16097172567d1` 的官方 main 相关差异。
- **已交付：** 双语设计、六方向 owner 映射、推荐 D1 CLI 切片、失败/回滚/验证契约。
- **证据边界：** 源码和官方接口文档读取；本条不认证运行时测试或模型试点。
- **未完成：** 本提案未交付 M1 实现、live conformance、价值评估或 UI/worker 采纳。
- **规范影响：** 第 1–12 节首次提案待评审，不推定已接受。

## 附录 B：决策日志

| 日期 | 推荐 | 审批 owner / 状态 | 替代方案 | 章节 |
| --- | --- | --- | --- | --- |
| 2026-09-19 | D1 operator CLI、原 capability、可选 Jev 包、显式 profile v1 | Decision Context / 产品维护者；尚未批准 | D2 在本地探针后实施；兼容研究证明必要时另选配置格式 | 3、5、11、12 |

## 附录 C：证据登记

| 证据 | 主张 / 位置 | 结果与边界 |
| --- | --- | --- |
| E1 | 第 4.1 节源码 owner 表及具名基线 | 已读，只证明实现事实，不认证运行时 |
| E2 | 至具名 SHA 的官方 main 差异，Replan 与协作 owner | 已读，该有限差异中未见 Jev 实现 |
| E3 | [TypeSafe API](https://docs.typesafe.ai/api)、[confidence](https://docs.typesafe.ai/confidence)、[models](https://docs.typesafe.ai/models)，2026-09-19 读取 | 仅接口文档，没有 API 调用或质量资格 |
| E4 | [构建指导](https://docs.typesafe.ai/concepts/how-to-build-with-system-one)、[skill 建议例](https://docs.typesafe.ai/cookbooks/skill_suggestion) | 外部设计参考，不将 benchmark 成果或权限转移给 LoopX |
| E5 | F01–F12 与第 9.1 节 | 此功能待执行验收要求，live 未验证不算 passed |

## 附录 D：排除的捷径

缺 key 默认放行、规则伪装成概率、凭 key 自动启用、静默切 provider、先造新智能控制面、凭 opaque ID 判断语义、合成测试冒充 live、重试不计费用、通用 confidence 门槛、没有真实 caller 就增加 registry 字段。PR 证据评审归 `pr_review_queue`，typed presentation 是消费者而非替代者；检索相关性不是已验证记忆效用。

## 附录 E：工程减法准则

每个实施 PR 说明真实 caller、基线、可选增量、无 key 行为、保留义务和增减维护成本。本次面向后续改动的审查选择一个局部推理接缝，拒绝六套空接口；共同传输等第二 caller 证明复用价值再提取。实验无收益可以停止；业务不依赖 Jev 是可执行验证的产品性质，不是配完 key 才看得见的声明。
