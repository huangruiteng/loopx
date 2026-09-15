# RFC：语义词表收敛与提交期漂移检查（v0）

- **RFC status：** Draft
- **Delivery maturity：** Partial（M0 的注册表、生成清单与漂移 smoke 随本 RFC 一起交付）
- **Authors / owners：** LoopX 贡献者；控制面内核维护者拥有批准权
- **Created：** 2026-09-15
- **Last normative revision：** 2026-09-15
- **Implementation baseline：** `1dc6ad8d8`
- **Related contracts：** `loopx/semantics/vocabulary_v0.json`、
  `loopx/semantics/inventory_v0.json`、
  `loopx/control_plane/turn_transaction_contract.json`、
  `loopx/control_plane/coordination/coordination_state_contract_v0.json`、
  [Turn Envelope v0](../../reference/protocols/turn-envelope-v0.md)、
  [Turn Loop Controller v0](../../reference/protocols/turn-loop-controller-v0.md)、
  [TypeScript 控制面迁移 v0](typescript-control-plane-migration-v0.zh-CN.md)
- **Language mirror：** [English](https://github.com/huangruiteng/loopx/blob/main/docs/architecture/rfcs/semantic-vocabulary-convergence-v0.md)

## 文档地图与维护契约

本 RFC 同时交付英文版 `semantic-vocabulary-convergence-v0.md` 与本中文语义镜像；
两者互相链接，规范章节变更时必须同步修订。

- 第 1-10 节是持久的设计与验收契约。
- 第 11 节是规范性交付计划。
- 第 12 节是未决决策；建议答案不等于批准。
- 附录是非规范的执行账本、决策日志、证据登记与被否决方案。

RFC 成熟度与交付成熟度彼此独立。带日期的进度条目不修改规范章节。

---

## 1. 决策摘要

1. **什么成为权威。** `loopx/semantics/` 下的两份文件。策展注册表
   `vocabulary_v0.json` 为每个内核与跨运行时词表命名：允许定义它的确切
   `module::Symbol`、词表之间的关系（同一概念、共享字段名、子集）、完整投影，
   以及仓库同意只降不升的预算。生成清单 `inventory_v0.json` 映射 `loopx/` 下
   每一个闭集载体：字符串枚举、`Literal` 别名、命名闭集、TypeScript `as const`
   数组，以及在多个模块中定义的每个常量名。一支公共 smoke
   `examples/semantic-vocabulary-drift-smoke.py` 在每个 PR 的默认 `pytest` 扫描
   里用两份文件核对代码；premerge 与 full-public 舰队是附加表面（第 10 节）。
   任何扩宽词表、分叉常量、新增载体或削弱注册表的
   改动，必须在同一个 diff 里修改注册表或重新生成清单，评审者因此能把语义
   变化当作变化看见。
2. **什么不变。** 运行时行为、线上格式、枚举类本身。每个枚举继续住在自己的
   owner 模块里；注册表通过 AST 与文本扫描核对代码，不生成代码，产品代码也
   永不导入它。
3. **默认与可选边界。** 检查对仓库始终开启。它没有运行时开关，因为它从不在
   产品内运行。
4. **主要约束。** 失败即关闭、确定性、且不能仅靠改数据被削弱。任一运行时的
   未注册字面量、第二个定义模块、预算超支、注册表列出但无模块携带的值、过期
   的清单、不带符号的 owner 声明、低于记录下限的覆盖计数，每一项都让 smoke
   失败。扫描识别的分发形式写在 smoke 里而不在注册表里。smoke 只读已跟踪
   源码，不打印任何私有数据。
5. **本 RFC 不批准的事。** 把三套 Turn 结果枚举合并为一套、拆分
   `effective_action` 的三个槽位、删除任何旧的 should-run 字段、删除任何
   Python 孪生模块、重命名任何现有值。这些属于后续里程碑，各自受 `AGENTS.md`
   中 schema 缩减规则的门控。

## 2. 问题与动机

LoopX 由大量小型 agent 驱动的 PR 生长而成。每个 PR 在需要之处加上它需要的
词汇。结果不是错误行为，而是漂移：同一概念多种拼法，同一常量在多个文件定义，
同一字段名承载不同词表，以及任何模块都可扩宽而无人察觉的开放字符串集合。
评审者无法从 diff 判断一个新字面量是新状态还是拼写错误，文档也无法跟上一个
没人枚举的集合。

语义面是全仓库的，不是 Turn 内核的局部问题。清单生成器在基线上扫描 `loopx/`
下 1169 个源文件得到：

| 载体 | 数量 | 说明 |
| --- | --- | --- |
| Python 字符串枚举 | 102 | 控制面 29、capabilities 17、extensions 6 |
| 命名闭集（`NAME = frozenset/tuple` 字符串） | 490 | 66 个是字段列表、31 kinds、31 states、29 statuses |
| `Literal[...]` 别名 | 8 | |
| TypeScript `as const` 数组 | 40 | 21 个有值集相等的 Python 侧；14 个没有 |
| 命名字符串常量 | 2002 | 754 个是 `*_SCHEMA_VERSION` |
| 同名同值、跨两个运行时 | 166 | 合法的 py/ts 孪生 |
| 同名同值、同一运行时 | 25 个名字 / 58 处定义 | 分叉；其中 7 个是 schema 版本 |
| 同名不同值 | 18 个名字 / 59 处定义 | 见下 |

在基线上审计出的具体失败：

- `TURN_ENVELOPE_SCHEMA_VERSION` 定义了三次：
  `loopx/control_plane/quota/turn_envelope.py:16`、
  `loopx/control_plane/quota/turn_envelope.ts:13`，以及
  `loopx/control_plane/turn_driver/driver.py:31` 的一份私有副本。M0 删除该副本。
- `HANDOFF_MODES` 由 TypeScript owner 定义，又在
  `control_plane/testing/authority_e2e_fixtures.py:33` 以字面元组重定义。M0 让
  夹具元组从 `HandoffMode` 枚举派生。
- 同一值集跨运行时有两个名字：`work_items/delivery_outcome.ts` 的
  `MATERIAL_DELIVERY_OUTCOMES` 等于 `goals/goal_frontier/outcome_continuity.py`
  的 `VISION_OUTCOME_CHECKPOINT_MATERIAL_OUTCOMES`。两者都是 `DeliveryOutcome`
  去掉 `surface_only`；没有任何地方说明这一点。
- 同名不同值：`DECISION_CONTEXT_CAPABILITY_ID` 在
  `capabilities/decision_context/packets.py:18` 是 `decision_context`，在
  `extension_provider.py:24` 是 `decision-context`；`MCP_REQUIREMENT` 在
  `kunluncode_goal_mode/cli.py:28` 是 `mcp==1.28.1`，在
  `claude_goal_mode/scripts/install.py:83` 是 `mcp<2`。另外 16 个名字是模块内
  通用常量（`SCHEMA_VERSION`、`COMMAND`、`CAPABILITY_ID`），今天的碰撞无害，
  明天却不可见。
- Turn 结果种类靠手工维护了两份：`transaction.py:28` 的 `LoopXTurnResultKind`
  与 `settlement.ts:49` 的 `TURN_RESULT_KINDS`。今天一致；没有任何测试断言过。
  另外 11 对 py/ts 词表同样如此（settlement 的 step、binding、failure kind，
  receipt-bound phase，scheduler transition，Todo completion 的 continuation 与
  recovery，delivery outcome，delivery workspace kind，Goal amendment class，
  Todo decision scope）。
- `effective_action` 是两侧都没有枚举的开放字符串集合。Python 与 TypeScript
  共靠字符串比较分发 31 个不同字面量。其中两个（`observe_replay`、
  `block_replay`）由 `turn_journal.ts:656` 写入 Turn Envelope 的 replay
  observation 槽位，根本不是 should-run 裁决。另外两个
  （`quota_action_selection_deferred`、`quota_action_selection_rejected`）是
  `cli_commands/quota.py:279` 复制进该槽位的 quota 错误码。
  `AgentScopeFrontierAction` 的值又被写进同一 envelope 的
  `agent_scope_frontier.effective_action` 槽位。一个字段名，三套词表。
  `user_gate.py:162` 还把该槽位与 `skip` 比较，而没有任何生产者写入它。
- 三套近似同构的 Turn 结果词表并存：`LoopXTurnResultKind`（12）、
  `LoopXTurnRoute`（8）、`LoopDisposition`（8），`repair`/`repair_required` 与
  `replan`/`replan_required` 是同一裁决的不同拼法。route 到 disposition 的投影
  是 `loop_controller.py:126` 的私有字典；没有任何声明说它覆盖全部输入。真正承重的
  `decide_loop_disposition` 决策表（result kind、retryable、attempt budget、
  decision user action、durable no-follow-up）只存在于控制器协议文档的散文里。
- 文档已称为 legacy 的六个 should-run 决策字段仍各被 7 到 35 个 Python 模块
  提及，没有棘轮阻止新消费者。
- `loopx/control_plane` 下有 43 对同名 `.py`/`.ts` 模块，而迁移 RFC 是
  replacement-first。这个数量没有守卫。
- 仓库已经在运行一支 AST 支撑的控制面债务棘轮
  （`loopx/canary/maintainability_ratchet.py`），带评审化的例外生命周期，但它
  度量的是模块指标与依赖方向，不是词表形状。词表漂移没有棘轮。

现有 owner 无法在本地解决，因为每处修复天然跨模块：Turn driver、quota、
todos、capabilities 与 TypeScript 运行时各自拥有同一想法的一种拼法。

### 不变量

- **I1 单一 owner。** 每个注册词表或常量，恰有注册表列出的定义模块，且注册的
  符号名在 `loopx/` 下别无定义。其余模块一律 import。
- **I2 闭集。** 注册词表可携带的每个值都被列出。任一运行时的代码都不携带未
  注册的值，注册表也不列出代码不携带的值。
- **I3 跨运行时一致。** 词表同时有 Python 与 TypeScript owner 时，两侧集合完全
  相同。
- **I4 完整投影。** 注册投影为每个源值恰好命名一次：要么映射，要么声明拒绝。
- **I5 棘轮只降。** 退休、孪生与清单预算可在任何 PR 中调低。每个预算在 smoke
  里另由一个 `BUDGET_ANCHOR`（或 `RETIREMENT_ANCHOR`）字面量钉住，每个下限由
  一个 `COVERAGE_ANCHOR` 钉住，沿用
  `tests/control_plane/test_m6_quality_gates.py` 的 `RFC_MODULE_BUDGETS` 锚点
  模式，但有一处刻意的不同：注册表的值必须**等于**锚点。先例用 `<=` 比较，
  这会让一个已收紧到锚点以下的预算，在之后的 PR 里不改任何代码就涨回锚点。
  相等性让每次收紧都是两个文件的 diff，每次放松都是评审者可见的代码修改。
- **I6 同 diff 可见。** 语义变化与其注册表修改或清单再生成落在同一个可评审
  diff 里。
- **I7 确定性且公开安全。** 检查只读已跟踪源码，不需网络或凭据，失败文本只
  命名文件与值，绝不含私有数据。
- **I8 覆盖只增。** 注册词表数、owner 符号数、投影数、关系数、schema 版本数
  与扫描后缀集合被记录为下限。owner 只能是 `module::Symbol` 或 `null`；裸模块
  路径被拒绝，null owner 必须声明字面量扫描。扫描识别的分发形式固定在 smoke
  里。因此一次注册表修改不可能悄悄收窄守卫所见。
- **I9 两种载体形状都被度量。** 词表进入代码的形态有两种：字符串常量
  （`NAME = "value"`）与多值载体（枚举、命名闭集、`Literal` 别名、
  TypeScript `as const` 数组）。两者适用同一条冲突规则：同一个名字在两个模块
  中被定义，值集相同是孪生，值集不同是分叉。冲突预算只统计共享词表子集；
  `SCHEMA_VERSION`、`COMMAND`、`*_LABEL` 这类模块局部约定名仍保留在清单
  总数中可见，但不算漂移。
- **I10 在 PR 路径上。** 漂移 smoke 通过
  `tests/architecture/test_semantic_vocabulary_drift.py` 跑在默认 `pytest`
  扫描里，因此在每个运行 Python 测试的 PR 上失败即关闭。`examples/` 下的舰队
  发现与 `repo-architecture-budget` premerge profile 是附加表面，不是义务：
  舰队在合并后和按日程运行，premerge 按改动路径的 token 选择。
- **I11 角色互异。** 一个词表有一个 owner、若干生产者、若干解释者与若干透传者
  （第 5 节"词表的角色"）。只有 owner 定义集合，只有生产者写入值。提及、
  比较、序列化或展示一个值不带来任何所有权。开始写入值的解释者或透传者已经
  变成生产者，必须登记为生产者。自 M0.5 起强制。
- **I12 每个内核值都被生产。** 对 `kernel` 词表，未列入 `compatibility_only`
  的每个值至少有一个固定生产形式能识别的生产位点，或一条
  `variable_sourced_values`。只被比较的值是死值或兼容值，绝不是 canonical。
  `effective_action` 的 `skip` 是第一个预期失败。自 M0.5 起强制；M0 的字面量
  扫描把被比较的值当作已携带。
- **I13 生产者只写注册值。** 写入注册集合之外值的生产位点失败即关闭，与是否
  有消费者比较它无关。生产比比较更严：消费者比较一个未注册值是死代码，生产
  者写一个未注册值是协议漂移。自 M0.5 起强制；M0 的字面量扫描把两种形式合在
  一起覆盖。
- **I14 作用域靠声明而非推断。** 在多个模块中定义的名字是分叉，除非注册表把它
  声明为 `bounded_context` 并列出各上下文及每个上下文一个 owner 符号。已声明
  的名字离开分叉预算；改名不改变预算的含义，不算修复。自 M0.5 起强制；M0 把
  `SOURCE_SURFACES` 计为分叉并加备注。

## 3. 范围与非目标

### 范围内

- 注册表文件、其 schema，以及编辑它的所有权规则。
- 生成清单、带 `--check` 的生成器及其单元测试。
- 漂移 smoke 及其在 premerge 与 full-public 舰队中的位置。
- M0 注册的词表：四个 Turn 内核集合（`turn_result_kind`、`turn_route`、
  `loop_disposition`、`effective_action`）、`agent_scope_frontier_action` 与
  `lease_action`，以及基线上 Python 与 TypeScript owner 值集相等的二十个跨
  运行时集合；route 到 disposition 的投影；九条关系；Turn Envelope 的 schema
  版本；六个旧 should-run 字段；控制面孪生数量；清单的分叉与冲突预算。
- 后续里程碑：把 `effective_action` 变成类型化枚举、拆分其三个槽位、通过契约
  发布投影、按现有仓库规则退休旧字段与孪生模块。
- 扫描根是 `loopx/` 包。本 RFC 说的"全仓库"指 `loopx/` 下两个运行时的全部
  载体，不是 git 树里的每个文件。清单的 `root` 与每条 `literal_scan.roots`
  都写 `loopx`，smoke 不读其他目录。

### 非目标

- 改变任何运行时决策、载荷形状或线上格式。
- 扫描 `apps/`（基线约 90 个 TypeScript 文件）或 `examples/`（十余处 smoke 里
  的 `effective_action` 断言）。它们是消费者与测试替身，不是生产者；一个断言
  了未注册值的 smoke 对 M0 不可见，在某个里程碑扩根之前接受这一点，扩根也会
  抬高第 10 节的合并序成本。
- 手工策展每个闭集。清单映射全部闭集；只有跨模块或跨运行时边界并被分发的
  词表才带 owner、值与关系进入策展层。
- 取代 `turn_transaction_contract.json` 或
  `coordination_state_contract_v0.json`。它们仍是各自阶段与记录的 owner；本
  注册表可以引用它们，不能复述它们。
- 取代 `maintainability_ratchet.py`。它拥有模块指标与依赖方向；本注册表拥有
  词表形状。两者的例外生命周期是否合并见第 12 节 Q7。
- 用散文术语表作为强制机制。术语表是有用的伴随物，在第 12 节跟踪，但它不能
  让构建失败。

## 4. 现行系统契约

基线 `1dc6ad8d8` 上的事实：

- `turn_transaction_contract.json` 是两个运行时同时读取的唯一契约：
  `effect_program.py:160-166` 加载阶段元组，`turn_journal.ts:1` 导入该 JSON。
  这是注册表作为共享事实源所效仿的模板。
- `coordination_state_contract_v0.json` 更进一步，通过
  `scripts/generate_coordination_state_contract.py --check` 生成
  `coordination_state_contract_generated.py` 与
  `coordination_state_contract.generated.ts`，由
  `tests/control_plane/test_coordination_state_contract.py` 守卫。清单生成器
  现在效仿它，M2 提议的生成阶段之后效仿它。
- canary runner 会发现每个已跟踪的 `examples/**/*-smoke.py`
  （`loopx/canary/runner.py:392`），因此 `examples/` 下的 smoke 无需在
  `planner.py` 或 `premerge.py` 登记。
- `loopx/canary/maintainability_ratchet.py` 是现有的 AST 支撑的控制面债务棘轮。
  它带有含 `retirement_plan` 的评审化例外并检测过期例外 id。它的对象是模块
  体积、`Any` 密度、决策点数量与禁止的依赖方向；它不读取枚举或常量的值。
- `AGENTS.md` 已要求状态分类使用类型化枚举、禁止 Python 为控制面权威建立第二
  事实源、新增模块前做 scope-fit 评审、并要求任何 schema 缩减获得维护者批准。
  本 RFC 增加的是让这些规则在 diff 中可观测的检查；它不改变规则本身。
- `loopx.control_plane` 的 package data 已经打包 `*.json`；`pyproject.toml`
  增加一行，让 `loopx.semantics` 以同样方式打包其两份 JSON。

## 5. 提议架构

### 所有权与权威

注册表由控制面内核维护者拥有。任何贡献者可以调低预算，或随携带它的代码一起
新增一个值。只有维护者可以批准调高预算、删除值或迁移 owner 模块，批准记入
附录 B。

禁止的替代权威：第二份注册表、复述已注册值的模块内列表，或宣称对已注册词表
具有规范性的散文表格。

**名字的作用域（计划在 M0.5，不在 M0）。** 碰撞规则按名字归组，因此分不清
"一个分叉"与"四个恰好复用同一标识符的有界上下文"。`SOURCE_SURFACES` 是第一
个案例：它在 `global_risks.py`、`global_todos.py`、`summary_all.py`、
`pr_review.py` 的四处定义各自列出那一个 CLI 命令的数据来源，值集本来就该不
同。它今天被计入 `multi_value_forks`，且不得用改名来"修"，因为改名只让数字
下降、不改变代码含义。M0.5 的作用域子阶段增加顶层 `scope_declarations`，至少支持 `global` 与
`bounded_context`；有界上下文名字只声明一次并列出其 owner，同时从语义分叉预算
中移除，原始清单计数仍保留（I14、下方 schema 表与第 11 节的 M0.5 行）。在此之
前分叉预算是一个包含这一处已知误分类的上
限，记在注册表 `inventory_ratchets` 的备注里。

### 词表的角色

提及一个值的模块不是它的 owner，一个词表也不止一种参与者。消费者是读取或接受
值的上位角色，解释者和透传者是它的两个受跟踪子角色。注册表区分这些角色，因为
对每种角色有意义的检查不同：

| 角色 | 做什么 | 是否登记 | 检查 |
| --- | --- | --- | --- |
| Owner | 以每个运行时一个 `module::Symbol` 定义闭集 | 是，自 M0 | I1 到 I3 |
| 生产者 | 把值写入字段：赋值、dict 或对象字面量、构造函数关键字、在已登记判定函数内 `return` 字面量、访问 owner 枚举成员 | `kernel` 词表必须，自 M0.5 | I12、I13 |
| 消费者 | 读取或接受词表值；解释者和透传者都属于这个上位角色 | 通常不登记；只报告关系，不做策展 | F3 |
| 解释者 | 消费者的一种，据值分支或映射：`if`、`match`、`switch`、成员测试 | 否；由分发扫描发现，`--report` 排序 | I2、F3 |
| 透传者 | 消费者的一种，序列化、持久化、转发或展示值而不改变其含义 | 否 | F3；涉及持久化时还需 F6 证据 |

由此得到两条规则。没有生产者的值是死值或兼容值：`skip` 在 `todos/user_gate.py`
被比较却无处写入，M0 放过它，M0.5 让它失败，直到被删除或列入
`compatibility_only`。生产比比较更严：M0.5 单独扫描生产形式，对未注册的被生产
值失败（I13），M0 的字面量扫描继续捕获未注册的比较（I2）。解释者与透传者刻意
不登记；否则每次消费者改动都要碰注册表，正是第 6 节对消费者计数所拒绝的搅动。
它们与词表的关系是 `--report` 的建议性输出。

生产形式在 M0.5 固定在 smoke 里，与分发形式同理：Python 的 `x["f"] = "v"`、
envelope 或 packet 类型构造函数的关键字 `f="v"`、注册表列为生产者的函数内的
`return "v"`、对 owner 枚举的成员访问；TypeScript 对象字面量里的 `f: "v"`、
`x.f = "v"` 与条件表达式。`variable_sourced_values` 保留给生产者从扫描无法跟随
的变量构造的值。哪些词表必须列生产者：`kernel` 自 M0.5；`cross_runtime` 只在
M0.5 之后新增或删除值时；`cross_module` 只在晋升后（Q8）。持久化是生产扫描能回
答的属性：若某个已列生产者符号是 journal 或 receipt 的写方，该词表标为
`persisted`，这正是 Q2 与 Q10 等待的事实。

### 形式模型与证明边界

注册表是更大程序语义的有限规格。令 `V` 为已注册词表集合，`Val(v)` 为词表
`v` 允许的值集合，`S` 为源码位点集合。模型记录的是关系，而不只是名称：

```text
D ⊆ S × V                         定义词表
P ⊆ S × V × Val(v)                生产值
C ⊆ S × V × Val(v)                消费或据值分支
I ⊆ S × V × V                     将一个词表解释为另一个词表
T ⊆ S × V                         不改变含义地透传
G ⊆ V × V × (Val ⇀ Val ∪ {reject}) 做投影
R ⊆ S × V × Version               将值持久化
```

最低语义义务如下：

1. **生产闭包：** `Produced(v) ⊆ Val(v)`。被识别的生产者不能写入注册集合之外的值。
2. **规范值存活：** `Canonical(v) ⊆ Produced(v) ∪ CompatibilityOnly(v)`。只被比较、
   没有生产来源的值是死值或兼容值，不能是 canonical。
3. **消费者定义域闭包：** `Accepted(c) ⊆ Val(v)`，除非消费者显式声明外部定义域或部分定义域。
4. **作用域分离：** 只有声明作用域相交时，同名冲突才是语义冲突。拼写本身不能证明等价。
5. **投影全性：** 每个源值都必须映射到目标值，或显式映射为 `reject`。
6. **持久化兼容性：** 持久化词表改变时，必须保持所有读者可读，或声明带版本的迁移。

这些是不同的证明义务。M0 已建立 owner 集合相等、跨运行时 parity、声明的可执行投影
和 inventory 新鲜度。固定字面量形式与闭集载体只提供有界证据，不是全程序证明。M0.5
增加有界的生产者和作用域检查。动态代码中的完整生产者发现、`same_concept` 的行为等价、
以及持久化读者兼容性，在建模源码到结果的边之前仍然是未证明状态。注册表通过
`formal_model` 保存这条证明边界；标记为 `unproved` 的性质是显式局限，不能被当作默认通过。


### 状态模型与 schema

`loopx/semantics/vocabulary_v0.json`，`schema_version` 为
`loopx_semantic_vocabulary_v0`。键集合是封闭的；未知的顶层键或词表键让 smoke
失败。

| 键 | 内容 | 检查 |
| --- | --- | --- |
| `coverage_floor` | 词表、owner 符号、字面量扫描字段、投影、关系、schema 版本的数量；扫描后缀集合 | 实际计数不低于下限，声明的后缀覆盖下限集合，且每个下限必须等于其 `COVERAGE_ANCHOR`（I8） |
| `vocabularies.<name>.owners` | `python` 与 `typescript`，各为 `path::Symbol` 或 `null` | 枚举成员、闭集成员、`Literal` 别名或 `as const` 数组等于 `values`；该符号只在 owner 模块中定义（I1、I2、I3） |
| `vocabularies.<name>.tier`、`status` | `kernel`、`cross_runtime`、`cross_module`；`canonical`、`legacy`、`merge_candidate` | 封闭枚举 |
| `vocabularies.<name>.literal_scan` | `field`、根目录、后缀 | 固定分发形式捕获的每个字面量都已注册；每个注册值被捕获或来自变量（I2） |
| `vocabularies.<name>.variable_sourced_values` | 值到生产者模块 | 生产者仍包含带引号的该值 |
| `scope_declarations.<name>`（M0.5a） | `bounded_context` 及上下文 ID，每个上下文含一个 `module::Symbol` owner | 每个声明名对应一个 inventory 分叉，并且一次且仅一次列出全部定义模块；只从 `multi_value_forks_semantic` 排除，未声明分叉仍可见（I14） |
| `vocabularies.<name>.producers`（M0.5） | 写入该字段的 `path::Symbol` 位点，`kernel` 必填 | 每个位点只写注册值；未列入 `compatibility_only` 的每个值至少有一个位点或一条变量来源条目（I12、I13） |
| `vocabularies.<name>.compatibility_only`（M0.5） | 为让已持久化记录的读者仍能解析而保留的值 | `values` 的子集；零生产位点；每个值带 `value_notes` 理由与退休里程碑 |
| `formal_model` | 有限的集合、角色关系与层次、语义义务，以及已建立/有界/未证明的声明 | 漂移 smoke 校验精确 schema、角色层次和不变量 ID；属性实施阶段不能冒充已完成证明 |
| `formal_model.enforcement_policy` | 当前阻断、下一阶段阻断、建议性和未证明层级 | 每个形式不变量恰好出现一次，且层级与其实施阶段一致 |
| `vocabularies.<name>.value_notes`、`deprecated_values` | 逐值评审备注；计划删除的值 | 名字必须是已注册值 |
| `relations.same_concept` | `vocabulary.value` 成员组 | 每个成员可解析 |
| `relations.shared_field_names` | 一个字段名、其槽位及各槽位承载的词表或值 | 每个槽位可解析 |
| `relations.subsets` | 超集词表、排除值、子集符号的 owner | owner 符号等于超集减排除值 |
| `projections.<name>.mapping` | 源值到目标值或 `null` | 键等于源词表；映射值与 owner 函数一致；`null` 路由抛出（I4） |
| `schema_versions.<name>` | 常量名、值、owner 模块 | 唯一的定义模块就是列出的 owner 且都携带该值（I1） |
| `retirement_ledger.<group>.fields` | 每字段的 Python 与 TypeScript 模块预算 | 实际模块数不超过预算，且字段集合与每个预算与 `RETIREMENT_ANCHOR` 一致（I5） |
| `dual_runtime_twins` | 根目录与模块预算 | 同名 `.py`/`.ts` 对数不超过预算（I5） |
| `inventory_ratchets` | 同运行时分叉的名字数与定义数、冲突的名字数与定义数、schema 版本分叉数、多值孪生与分叉数，以及共享词表冲突与分叉子集的预算 | 清单摘要计数不超过预算，且每个预算必须等于其 `BUDGET_ANCHOR` 条目（I5、I9） |

`loopx/semantics/inventory_v0.json`，`schema_version` 为
`loopx_semantic_inventory_v0`，由 `scripts/generate_semantic_inventory.py` 生成，
必须与新鲜构建完全一致。它每行一条地列出 Python 枚举、闭集、`Literal` 别名、
TypeScript `as const` 数组，以及拆为跨运行时孪生、同运行时分叉、冲突值、多值
孪生与多值分叉四类的重复定义。每个多值冲突都带上全部定义模块及其值集，因此
可评审的是分叉本身而不只是计数。消费者计数由 `--report` 打印，合并候选组通过 `merge_candidate_groups` 获取，
两者均不提交，因此普通的消费者改动不会碰这个文件；合并候选是建议性的，因为值集
相同并不能证明是同一个概念。单模块的字符串常量只计数，不列出。

值是只增的。删除一个值、字段、owner 或关系属于 schema 缩减，遵循 `AGENTS.md`
规则：枚举受影响表面、调研生产者与读者、在同一 diff 中调低下限、记录维护者
批准。

### 命令或事件生命周期

检查只有一个命令：运行 smoke。它幂等且无副作用。失败文本命名词表、违规文件与
值，修复是机械的：注册该值、import 该常量，或收窄改动范围。

### Provider 或扩展契约

新词表通过一个 PR 加入：新增注册表条目、提高覆盖下限，若存在 TypeScript owner
则指名其 `as const` 数组。当一个词表被多个模块分发或跨越 Python/TypeScript
边界时，即有资格进入策展层；其余由清单映射而不策展。新增任何载体都要在同一
PR 中重新生成清单。

## 6. 备选方案与设计选择

| 备选 | 为何现在不选 |
| --- | --- |
| 一个 PR 把三套 Turn 枚举合一 | 违背 I5 式的渐进；三套枚举有不同 owner 与变化原因（settlement、route、controller）。先注册并投影，只在投影证明同一后再合并（第 12 节 Q2）。 |
| 依赖 `mypy` 的 `Literal` 类型 | 覆盖不到 TypeScript、JSON 载荷与 CLI；而漂移恰恰发生在这些边界。 |
| 仅靠文档术语表 | 不能让构建失败；仓库已有十一份自称 mental model 的文档且没有术语表，这本身就是症状。 |
| 立即从注册表生成绑定 | owner 尚未定下之前为时过早。生成是 M2，效仿协调契约先例。 |
| CI 里不带注册表的 grep 式 lint | 把允许集合编码进 linter，变成没有评审痕迹的第二份注册表。 |
| 扩展 `maintainability_ratchet.py` 而不新建注册表 | 它的对象是模块指标与依赖方向，按模块设上限；词表形状需要值、owner 与关系。两者共享棘轮思想而非数据模型。例外生命周期是否合并见 Q7。 |
| 把扫描正则放进注册表 | 数据里的正则可以在扩宽词表的同一次修改中被收窄；M0 评审表明第一版模式漏掉了全部 TypeScript `===` 分发点。形式固定在 smoke 里，后缀集合设下限。 |
| 在清单中提交消费者计数 | 每次消费者改动都会搅动文件，让新鲜度检查变成噪音。计数通过 `--report` 保持为参考信息。 |

## 7. 安全、隐私与兼容

- M0 没有任何运行时路径导入注册表；检查存在与否，产品行为不变。
- 扫描器使用 `git ls-files --cached -z` 枚举索引中的源文件路径，再读取工作树内容。
  未跟踪与忽略文件不进入清单；新增源文件需先暂存路径，再重新生成清单。已跟踪
  的符号链接与无法解析的 Python 源码使检查失败；运行时需要带 Git 元数据的检出。
- 字面量及 TypeScript 载体扫描同时识别单引号与双引号。它们仍是结构性文本
  扫描，不是完整解析器，也不做数据流分析。
- 字面量扫描根目录与后缀、孪生模块根目录与预算均有代码锚点；仅修改 JSON
  不能缩窄扫描范围或提高孪生预算。
- 失败文本只使用仓库相对路径与已注册标识符。
- 旧的读写方不受影响。预算冻结其当前分布，不删除任何一处引用。
- 构建期检查不涉及混合版本。M2 引入生成绑定时，生成器的 `--check` 模式与
  smoke 同时运行，过期的生成文件无法合入。

## 8. 迁移与回滚

- **准入。** M0 落地时注册表与清单和基线完全一致，外加两处保持行为的修改以让
  owner 检查通过：`driver.py` 中重复的 `TURN_ENVELOPE_SCHEMA_VERSION` 改为
  import，authority e2e 夹具中的 `HANDOFF_MODES` 元组改为从 `HandoffMode` 枚举
  派生。
- **回滚。** 删除 smoke、`loopx/semantics/` 包、生成器、其测试与 `pyproject.toml`
  的那一行即恢复原状，无运行时影响。后续里程碑在第 11 节各带回滚。
- **不可回退点。** M0 没有。M3 的字段删除是第一个不可逆步骤，逐个门控。

## 9. 验证与验收

| 声明 | 测试或证据 | 要求结果 | 边界 / 排除 |
| --- | --- | --- | --- |
| 基线上注册表与清单和代码一致 | `python3.11 examples/semantic-vocabulary-drift-smoke.py` | `ok` 并输出覆盖、棘轮、预算与孪生报告 | 只证明已注册词表与已映射载体的一致性 |
| 清单新鲜 | `python3.11 scripts/generate_semantic_inventory.py --check` | 退出码 0 | 仅结构性映射 |
| 扫描器分类规则 | `pytest tests/architecture/test_semantic_inventory.py` | 通过 | 夹具仓库；规则来自本 RFC 而非输出 |
| Python 侧扩宽 `effective_action` 时失败关闭 | 通过 `==`、成员测试或条件表达式加一个未注册字面量 | 失败文本命名该值与文件 | 突变练习；非提交测试 |
| TypeScript 侧扩宽 `effective_action` 时失败关闭 | 通过 `===` 或三元表达式加一个未注册字面量 | 同上 | 同上 |
| 分叉常量时失败关闭 | 在非 owner 模块重定义 `TURN_ENVELOPE_SCHEMA_VERSION` 或 `HANDOFF_MODES`，重新生成清单 | 失败列出多出的定义模块或分叉预算 | 同上 |
| Python 与 TypeScript owner 不能分叉 | 从已注册 `as const` 数组删一项，或扩宽已注册枚举 | 失败命名缺失或未注册的值 | 同上 |
| 注册表不能仅靠改数据被削弱 | 声明裸模块 owner；删掉一个 owner；把后缀收窄为 `.py`；重命名一个被关系引用的词表；加一个未知键 | 每项都失败并点名规则 | 同上 |
| 新载体可见 | 新增一个枚举而不重新生成 | 失败文本说清单过期 | 同上 |
| 冲突拼法不能增长 | 为已冲突名字加第三种值，重新生成 | 失败命名定义数预算 | 同上 |
| 多值冲突不能增长 | 让一个闭集名在两个模块中以不同值集定义，或以相同值集定义，并重新生成 | `multi_value_forks` 或 `multi_value_twins` 失败并命名新名字 | 突变练习；非提交测试 |
| 注册表不能放松自己的棘轮 | 在同一 diff 中调低任一 `coverage_floor` 计数、调高任一 `inventory_ratchets` 预算或退休预算，同时删掉它所统计的覆盖 | `COVERAGE_ANCHOR`、`BUDGET_ANCHOR` 或 `RETIREMENT_ANCHOR` 失败并命名被锚定的值 | 突变练习；挪动锚点是一次评审者可见的代码修改 |
| 已收紧的预算不能漂回过期锚点 | 只调低注册表预算而不动锚点 | 失败文本指出注册表值与锚点不等 | 用相等而非 `<=`；修法是同 diff 调低锚点 |
| smoke 在 PR 路径上 | `pytest tests/architecture/test_semantic_vocabulary_drift.py` | 通过；该测试被 `python-tests.yml` 的默认 `pytest -q` 扫描收集 | 舰队与 premerge 表面不是义务（I10） |
| premerge 会为 `loopx/` 的 diff 选中该 smoke | `loopx canary premerge --changed-file loopx/control_plane/turn_driver/loop_controller.py` | 计划在 `repo-architecture-budget` 下列出 `examples/semantic-vocabulary-drift-smoke.py` | 选择靠触发词；pytest 包装才是保证 |
| 度量覆盖两种载体形状并过滤局部命名 | `pytest tests/architecture/test_semantic_inventory.py` | 通过，含冲突与模块局部约定两组夹具 | 规则来自本 RFC 而非扫描输出 |
| 两处 owner 修正不改变行为 | `pytest tests/test_loopx_turn_transaction.py tests/test_loop_turn_loop_controller.py tests/test_turn_loop_disposition.py tests/test_loopx_turn_managed_step.py tests/control_plane -k authority` 与 `loopx canary premerge --from-git-diff` | 通过 | 在干净树上可复现的 `main` 既有环境失败除外 |
| 文档治理接受这对 RFC | `python3 examples/docs-governance-smoke.py` | 通过 | 检查镜像、链接、索引 |
| 退休预算按子串而非标识符计数 | 分别以 `in file.text` 与 `\bgoal_boundary\b` 统计 `goal_boundary` | 基线上 35 对 30 个 Python 模块 | 已知边界；M3 的零读者门需要标识符计数，见第 12 节 |
| 模块局部约定过滤器是一次代码修改 | 扩宽 `inventory.py` 的 `MODULE_LOCAL_CONVENTION` 并重新生成 | `*_semantic` 预算下降而别处无代码改动 | 已知边界；正则在代码里，扩宽是可评审的 diff，未过滤总数仍在预算内 || 无人生产的注册值失败（M0.5） | 在基线上运行生产形式扫描 | 失败并点名 `effective_action` 与 `skip`；删除 `skip` 或列入 `compatibility_only` 后通过 | 第一个预期的 I12 失败；只被比较的值不算已携带 |
| 生产未注册值失败（M0.5） | 在某个已列生产位点写 `effective_action: "brand_new"` | 即使无消费者比较它也失败，并点名位点与值 | I13；生产比比较更严 |
| 有界上下文名字只能靠声明离开语义分叉预算（M0.5a） | 为 `SOURCE_SURFACES` 声明四个上下文；另行只改名其中一处定义而不声明 | 原始 `multi_value_forks` 保持 4，`multi_value_forks_semantic` 为 3；单独改名既不改变语义计数，也不构成声明 | I14；诚实的修法是评审者看得见的注册表修改，改名不是修复 |

| 上游合并会让已提交清单过期 | 对 `upstream/main` 最近二十个合并提交，在第一父提交与合并结果之间重放扫描器 | 20 次合并中 8 次至少改变一个载体 | 提交快照的实测成本；处理规则见第 10 节与第 12 节 Q9 |
| 形式模型不能静默丢失证明义务 | 从 `formal_model` 删除不变量、角色、关系或证明边界分类 | 漂移 smoke 针对形式模型结构失败 | 该模型是有限契约和证明账本，本身不等于这些性质已经被证明 |

已知边界，写明是为了不让这个检查被过度信任：

- **改名可以洗白冲突。** 冲突按名字归组，因此把分叉的一侧改名会降低计数而
  不消除漂移。这里的评审辅助是建议性合并报告；值集相同不能做成硬预算，因为
  `CONFIDENCE_LEVELS` 与 `EDGE_CASE_COMPLEXITIES` 共享 `high/low/medium` 却
  含义不同。
- **单元素载体不可见。** 只有一个字符串成员的闭集不构成词表，因此把一个两值
  集合降为一个值会让它完全退出清单。
- **字面量扫描可能误读同一行上无关的比较。** 形如
  `log("effective_action", kind === "repair_required")` 会被捕获为
  `effective_action` 的值。为了让失败消失而登记被报告的值会扩宽词表，正确做法
  是同时登记字段名与字面量，或改写该行；失败文本会给出文件，评审时可见。
- **锚点是代码而非历史。** PR 仍可挪动锚点，但必须修改一个具名字面量，就在
  注册表改动的旁边。因为检查是相等性，锚点不可能过期，但它也不记住曾达到的
  最低值；那段历史在 git log 里。

## 10. 运维契约

标准 premerge 的 catalog 检查上限从 9 提高到 10，避免新增词表检查挤掉原有
heartbeat/quota 覆盖。quick 与 deep 档位的上限不变。

该检查不可能影响运行中的系统：它只在测试、premerge 与 CI 中执行。其操作者
界面就是失败文本。不适用可观测性、容量或值班契约。

它在哪里运行，以及哪个表面是义务：

| 表面 | 触发 | 选择 | 角色 |
| --- | --- | --- | --- |
| `pytest` 扫描，`python-tests.yml` | 每个分类为需运行 Python 测试的 PR | 经 `tests/architecture/test_semantic_vocabulary_drift.py` 始终被收集 | **提交时义务（I10）** |
| `loopx canary premerge` | 本地，开 PR 之前 | `repo-architecture-budget` profile，触发词含 `loopx/`、`examples/`、`scripts/`、`refactor` | 早期本地信号 |
| 全量公共 smoke 舰队 | push 到 `main`、每日日程、手动触发 | `examples/**/*-smoke.py` 发现 | 合并后确认；按设计不是 PR 必需检查 |

在这张表存在之前，RFC 说 smoke "在 premerge 与 CI 中运行"。在基线上这只在合并
后成立：premerge 对只改 `loopx/control_plane/` 的 diff 不会选中该 smoke，而舰队
工作流被刻意设为非 PR 必需检查。舰队能发现的 smoke 不是提交时检查，除非某个
必需的 PR 作业收集它。

**合并序风险。** `inventory_v0.json` 是整个 `loopx/` 树的已提交快照，树与快照
不一致时 smoke 失败。两个各自新增载体、各自正确再生成清单的 PR，对着它们
各自基于的 `main` 都是绿的；后合并的那个会让 `main` 的快照缺少先合并者的
条目，`main` 上的扫描在有人再生成之前是红的。对 `upstream/main` 最近二十次
合并的重放显示有八次至少改变一个载体，所以这是每周会发生的事，不是边角。
本分支第一次同步上游就复现了它：合入的十二个提交新增一个枚举与三个闭集，
检查失败直到重新生成。处理规则是第 12 节 Q9；在其决定之前的规则是：在
`main` 变红之后合并 PR 的人负责跟一个只改 `inventory_v0.json` 的再生成提交，
smoke 的失败文本会点名那条命令。

**解释器。** smoke、生成器与扫描器要求项目声明的 Python（`pyproject.toml`
中 `>=3.11`）；`zip(strict=True)` 在 3.9 上失败。舰队与 premerge 的命令按仓库
约定写作 `python3`，在 CI 解释器下运行。macOS 系统 `python3` 是 3.9，本地
premerge 需要 `PATH` 上有 3.11 环境；文档因此把直接命令写成 `python3.11`，
planner 条目则有意保留 `python3`。

## 11. 规范性交付计划

| 里程碑 | 交付行为 | 进入门 | 退出证据 | 回滚 |
| --- | --- | --- | --- | --- |
| M0 | 含 26 个词表与 9 条关系的注册表、带 `--check` 的生成清单、带固定分发形式与覆盖下限的漂移 smoke、删除两处 owner 分叉、RFC 索引条目 | 本 RFC 开启 | 第 9 节各行全绿；20 类突变失败关闭 | 删除 smoke、`loopx/semantics/`、生成器及其测试 |
| M0.5a | `scope_declarations` 的 `bounded_context` 与每上下文 owner；把语义分叉计数与原始清单计数分开 | M0 合入 | smoke 校验每个声明的上下文 owner；原始 `multi_value_forks` 仍为 4，`multi_value_forks_semantic` 为 3；未声明分叉仍受预算约束 | 删除作用域声明和语义分叉预算 |
| M0.5b | `kernel` 词表的 `producers` 与 `compatibility_only`；带两条角色检查（I12、I13）的生产形式扫描；退休预算改按标识符计数并在一个 diff 里调整六个锚点（Q11）；Q9 的合并序规则写入第 10 节 | M0.5a 完成；Q9 已决或其临时规则被接受 | smoke 在 I11 到 I14 强制下全绿；`skip` 已处理；第 9 节生产者行全绿；为 Q2 回答 `turn_route` 是否持久化 | 删除生产者字段和角色检查；预算回到 M0.5b 前的锚点 |
| M1 | 单一 owner 模块中的 `EffectiveAction` 类型化枚举；replay observation 与 frontier 槽位拆出（Q6）；生产者与消费者 import 它；注册表 `literal_scan` 收紧到枚举 | M0.5 合入；owner 模块已定（Q3）；槽位拆分已决（Q6） | smoke 绿；owner 之外零裸 `effective_action` 字面量；status/should-run 的 parity fixture 不变 | 回退为字面量；注册表保留集合 |
| M2 | route 到 disposition 的投影、`decide_loop_disposition` 决策表与跨运行时集合通过共享契约发布，生成 Python 与 TypeScript 绑定，效仿协调契约生成器 | M1 合入；Q2 与 Q7 已决 | 生成器 `--check` 与 smoke 绿；`settlement.ts` 与 `transaction.py` 读取生成集合 | 从上一版契约重新生成 |
| M3 | 逐字段退休旧 should-run 字段，每个 PR 一个字段，预算降到零并删除字段 | 经生产者/读者调研证明该字段外部读者为零 | 按 `AGENTS.md` 的 schema 缩减记录；附录 B 条目 | 从最后一个写方恢复字段 |
| M4 | 随迁移 RFC 的每次 replacement-first 切换调低孪生预算 | 每个切换 PR | 同 diff 中的预算修改 | 无需；预算跟随代码 |

没有目标的棘轮只是方向，不是计划。下表是本 RFC 完成时的状态；每一行都是一个
注册表预算或 smoke 可检查的词表属性。标为*未决*的行等待第 12 节的决策，这也
是计划在那些决策记录之前只是骨架的原因。

| 表面 | 基线（`1dc6ad8d8`） | 本 RFC 关闭时的目标 | 由谁达成 |
| --- | --- | --- | --- |
| `effective_action` 取值 | 33 个字面量，无 owner 符号 | 一个枚举 owner；`skip`、`observe_replay`、`block_replay` 与两个 `quota_action_selection_*` 码从判定槽位移出；约 28 值 | M1 |
| 同一 envelope 里的 `effective_action` 槽位 | 一个字段名下 3 套词表 | 1，或在 Q6 保留字段时为一个已注册并集 | M1（Q6） |
| Turn 词表 | 3 套、28 值、21 个不同值、7 个冗余拼法 | 保留 3 套；投影与决策表生成并校验；拼法不变，除非 Q10 决定合并 | M2（Q2、Q10 *未决*） |
| 同运行时分叉（语义） | 18 个名字 | 0 | 基线窄 PR |
| 冲突值（语义） | 2 个名字 | 0 | 基线窄 PR |
| 多值分叉 | 4（1 个误分类） | `scope` 声明有界上下文名字后为 0 | M0.5 + 基线窄 PR |
| 多值孪生 | 19 | 0 | 基线窄 PR |
| 旧 should-run 字段 | 6 个字段，124 py / 10 ts 模块提及 | 0 个字段 | M3，按标识符计数 |
| 合并候选组 | 32 组未评审 | 每组已分类；只合并 `same_semantics` 的组 | 分类表 PR，随后逐组 PR |
| 控制面 py/ts 孪生 | 43 | 跟随 TypeScript 迁移 RFC；本 RFC 不设目标 | M4 |

### 两条执行轨道与强制层级

路线图把修复已有语义债务与完善度量工具分开。轨道 A 不等待设计决策：每个窄 PR
逐步删除真实分叉、冲突、孪生和旧读者。轨道 B 改善守卫能够知道的内容：作用域声明、
有界生产者分析、标识符计数和合并序处理。轨道 A 降低债务数量，轨道 B 让这个度量更
接近真实语义。M1 及之后的阶段依赖轨道 B，因为当前度量已知并不完备。

```text
轨道 A：修复现有债务 ──────────────────────────────────────┐
                                                               ├─> M1 类型化槽位
轨道 B：作用域 + 生产者模型 + 度量边界 ─────────────────────┘       │
                                                                      ├─> M2 生成式投影
                                                                      ├─> M3 旧字段退休
                                                                      └─> M4 运行时孪生迁移
```

形式模型使用四个强制层级，避免困难性质意外变成合并阻断：

| 层级 | 性质 | 当前含义 |
| --- | --- | --- |
| `blocking_now` | F5 投影全性 | 当前 M0 smoke 已强制 |
| `blocking_next` | F1 生产闭包、F2 规范值存活、F4 作用域分离 | M0.5 后计划强制；M0 不宣称已经做到 |
| `advisory` | F3 消费者定义域闭包 | 只报告证据，不阻断普通消费者改动 |
| `unproved` | F6 持久化/版本兼容性 | 明确的证明缺口，不能报告为已通过 |

阶段完成条件是验收表中的证据，而不是出现一个公式或注册表条目。有界的源码到结果
分析存在之后，性质才可从 `unproved` 移到 `advisory`；只有记录误报/漏报边界并用突变
测试覆盖已识别形式后，才可移到阻断层。这样既严格防止静默破坏，也允许不完整的分析
为无关改动提供信息而不阻断它们。

阶段顺序如下：

1. **M0：** 保留当前结构守卫，并明确其证明边界。
2. **M0.5：** 为四个 Turn 内核词表实现 `scope`、生产形式和按标识符计算的退休预算。
3. **M1：** 在 Q3、Q6 决定后拆开过载的 `effective_action` 槽位，并引入一个类型化 owner。
4. **M2：** 通过生成的跨运行时契约发布完整决策表和两跳投影。
5. **M3/M4：** 只有在读者与迁移证据完整后，才退休旧字段并减少 Python/TypeScript 孪生。

这份路线图对依赖和退出证据具有规范效力。Issue #4447 可以承载 owner、建议日期和
运维清单，但不能另立一套目标状态。


## 12. 未决决策

1. **注册表位置。** Owner：内核维护者。M0 实现于 `loopx/semantics/`，因为范围是
   全仓库的，而 `loopx/control_plane/` 与 `docs/reference/` 都不是；该包只含两份
   JSON 与扫描器，没有任何产品代码导入它。在记入附录 B 之前这只是提案。M1 前
   需定。
2. **是否合并 `LoopXTurnRoute` 与 `LoopDisposition`？** Owner：Turn driver owner。
   投影覆盖全部输入但非单射（`blocked` 与 `wait` 都映到 `wait`），而 `stop`、
   `terminal`、`contract_error` 只在一侧存在。`same_concept` 关系记录了四个共享
   裁决。建议：两者都保留，M2 发布投影，待 managed-step 消费者成熟后再议。
   M2 前需定。保留两者的理由是合并会触及已持久化的 Turn 记录；这个前提尚未
   核实。决定之前应先用 M0.5 的生产形式扫描（I12，第 5 节）确认 `turn_route`
   是否曾写入 journal 或
   receipt，还是只在进程内流转；若是后者，合并的代价远低于本 RFC 的假设，
   适用 Q10。
3. **`EffectiveAction` 的 owner 模块。** 注册表今天不声明 owner，因为不存在任何
   符号；字面量扫描是唯一检查。选项：`quota/should_run_packet.py`（最大生产者）、
   新建 `quota/effective_action.py`，或按迁移 RFC 以 TypeScript `turn_envelope.ts`
   为 owner 并生成 Python 绑定。建议：若 M2 先落地则以 TypeScript 为 owner 并
   生成 Python 绑定；否则新建 `quota/effective_action.py`。M1 前需定。
4. **伴随术语表。** 是否新增 `docs/reference/glossary.md`，从注册表的 `meaning`
   字段与清单生成。Owner：文档维护者。建议：是，在 M1 生成以免漂移。
5. **词族命名规则。** `gate`、`scope`、`packet`、`handoff`、`settlement` 词族中的
   新标识符是否必须在评审中引用术语表条目。这是评审规则而非 smoke；建议在
   术语表存在后纳入 first-review roster。
6. **拆分 `effective_action` 的三个槽位。** decision 槽位、`agent_scope_frontier`
   槽位与 replay observation 槽位在同一个 Turn Envelope 里共用一个字段名、承载
   三套词表；`skip` 被比较却从未被生产。选项：重命名 observation 与 frontier
   槽位，或保留一个字段并注册其并集。Owner：Turn Envelope owner。建议：在 M1
   重命名，让 Q3 的枚举只有一种含义。M1 前需定。
7. **与 `maintainability_ratchet.py` 的关系。** 清单棘轮是否采用它的评审化例外
   生命周期（`retirement_plan`、过期例外检测），还是保持为纯预算。建议：在 M2
   生成落地时采用，让有书面理由的分叉可以被例外而非被预算。Owner：canary
   维护者。
8. **从清单到注册表的晋升规则。** 外部消费者模块不少于三个或存在跨运行时孪生
   的已映射载体是否必须策展。建议：现在作为评审规则采用，待清单积累一个季度
   历史后再由 smoke 强制。Owner：内核维护者。
9. **跨合并的清单新鲜度。** 两个新增载体的 PR 先后合并时，已提交快照会过期
   （第 10 节；上游最近二十次合并中八次）。选项：(a) 分支保护要求 PR 与
   `main` 同步，根除风险但拖慢所有 PR；(b) 合并者负责一个只再生成的后续提交，
   快照留在 git 历史里，接受 `main` 红几分钟；(c) 清单不入库，CI 只对 PR diff
   生成，失去对载体的 `git blame`。建议：现在用 (b)，若 `main` 变红超过每周
   一次则改 (a)。Owner：仓库维护者。这是运维决策不是代码改动；应放在跟踪
   issue 的决策清单里，而不是任务清单里。
10. **Turn 词表的终态。** 第 11 节的目标表默认保留三套与七个冗余拼法，因为
   Q2 建议保留两者。若 Q2 的 M0.5 生产形式扫描表明 `turn_route` 未被持久化，维护者
   应在 (a) 三套加生成投影（现行计划）与 (b) 两阶段合并（先双写、后退休）到
   每个概念一种拼法之间选择。没有这个决定，RFC 对其标题问题只有预算、没有
   完成定义。Owner：Turn driver owner。M2 关闭前需定。
11. **退休预算使用独立字段 token。** 六个旧字段预算现在使用
   `count_identifier_modules()`，因此 `goal_boundary_repair` 不会被算作
   `goal_boundary`。这是保守的词法指标，不等于证明不存在语义读者；计算式访问
   仍然是证据缺口。Owner：内核维护者。

## 附录 A：执行账本（非规范）

### 2026-09-15 — 随 RFC 开启 M0

- **基线：** `1dc6ad8d8`
- **交付：** 含四个词表、一个投影、一个 schema 版本、六个旧字段预算、一个孪生
  预算的注册表；漂移 smoke；`driver.py` 中重复的 `TURN_ENVELOPE_SCHEMA_VERSION`
  改为 import。
- **证据：** 第 9 节各行；见附录 C。
- **已知缺口：** 投影检查在 M2 发布之前导入私有的 `_route_to_disposition`。
- **对规范设计的影响：** 无。

### 2026-09-15 — 评审后修订 M0；范围改为全仓库

- **基线：** `1dc6ad8d8`
- **触发：** 一次评审发现第一版字面量扫描对 TypeScript 完全失明（`===` 从不
  匹配）、基线上已有两个未注册值（`observe_replay`、`block_replay`），以及
  owner 检查会静默跳过任何不带符号的 owner。
- **交付：** 注册表迁至 `loopx/semantics/vocabulary_v0.json` 并扩为 26 个词表、
  46 个 owner 符号、9 条关系与覆盖下限；生成清单 `inventory_v0.json`，带
  `--check` 的生成器与单元测试；smoke 重写为固定分发形式（比较、赋值、三元、
  成员、条件表达式）、基于 AST 的 owner 解析、owner 排他性、清单新鲜度与
  分叉/冲突预算；`HANDOFF_MODES` 夹具分叉改为从枚举派生。
- **证据：** 附录 C 的 E6 到 E10。
- **已知缺口：** 承重的 `decide_loop_disposition` 决策表仍只有散文（M2）；
  字面量扫描无法把一个字面量归到 `effective_action` 三个槽位中的某一个（Q6）；
  扫描无法跟随变量传值，因此两个 quota 错误码以"变量来源值"登记并核验生产者，
  而非被证明。
- **对规范设计的影响：** 第 1 至 5、8、9、11、12 节修订；新增 I8。记为未合入
  草案的当日修订。

### 2026-09-15 — 第二次评审后修复 M0 的度量

- **基线：** `1dc6ad8d8`
- **触发：** 第二次评审对 smoke 跑了 14 种攻击，7 种逃逸：单独调低某个
  `coverage_floor`、一次调低全部下限、调高 `inventory_ratchets` 或某个退休
  预算，以及最关键的——在同一个 diff 中删掉一个 owner 并同时调低对应的下限。
  下限与被它守护的文件在同一个文件里，且只用 `>=` 比较，因此注册表可以放松
  自己的棘轮。I5 与 I8 当时是散文，不是机器约束。
- **同时发现：** 冲突检测只跑字符串常量，599 个多值载体只被列出、从未被比较。
  基线上已经有四个同名分叉，其中 `SOURCE_SURFACES` 被定义四次、四套不同值集，
  另有 19 个隐藏孪生。另外，18 个 `conflicting_values` 名字中有 16 个是模块
  局部约定（`SCHEMA_VERSION` 出现 16 次，另有 `COMMAND`、`REQUEST_SCHEMA`、
  `SURFACE`），因此该预算主要在度量局部命名。
- **交付：** smoke 中新增锚点 `COVERAGE_ANCHOR`、`COVERAGE_SUFFIX_ANCHOR`、
  `BUDGET_ANCHOR`、`RETIREMENT_ANCHOR`，关闭全部七种逃逸；
  `multi_value_name_collisions` 让枚举、闭集、`Literal` 别名与 `as const`
  数组适用字符串常量的冲突规则，四个分叉与 19 个孪生按当日计数入预算；
  `MODULE_LOCAL_CONVENTION` 让局部名保留在可见总数中但不进入语义预算
  （`conflicting_values_semantic` 为 2，`same_runtime_forks_semantic` 为 18）；
  针对 32 组同名异名同值集的建议性合并候选报告；在独立冲突夹具上新增两个
  扫描器测试；新增 I9 并写明第 9 节的边界。
- **证据：** 附录 C 的 E11 到 E13。
- **已知缺口：** 冲突按名字归组，因此改名仍可洗白一个；单元素载体不可见；
  字面量扫描可能误读同一行上无关的比较。
- **对规范设计的影响：** I5 与 I8 从"意图"改写为"已强制"；新增 I9；第 5 节
  表格与第 9 节各行更新。现在放松预算的唯一方式是挪动锚点，而那是一次代码
  修改。
- **被收紧的未决项：** Q7 可能从"采纳 `maintainability_ratchet` 的例外
  生命周期"收敛为"共用它的锚点模式"，因为本 smoke 已经在用该模式。

### 2026-09-15 — 第三次评审后把 M0 放上 PR 路径

- **基线：** `1dc6ad8d8`
- **触发：** 第三次评审问 smoke 到底在哪里运行。对只改 `loop_controller.py`
  与 `turn_envelope.ts` 的 diff 做 premerge 规划，得到 32 条命令，不含本
  smoke；`full-public-smokes.yml` 只在 push 到 `main` 与每日日程触发，且文档
  写明刻意不作 PR 必需检查。每个 PR 都跑的唯一表面是 `pytest` 扫描，而已提交
  的测试只覆盖夹具上的扫描器。RFC 的"提交时"声明因此只在合并后成立。
- **同时发现：** 每个锚点都用 `<=`（下限用 `>=`）比较，忠实复制了
  `RFC_MODULE_BUDGETS` 先例。一个 PR 把预算收紧到锚点以下后，后续 PR 可以不
  改代码把它涨回锚点，棘轮停在锚点最后的值上。
- **交付：** `tests/architecture/test_semantic_vocabulary_drift.py` 在默认扫描
  里以子进程运行 smoke；smoke 加入 `repo-architecture-budget` premerge
  profile，与可维护性棘轮并列；三处锚点比较改为相等；新增 I10；第 10 节增加
  表面表格。
- **证据：** 附录 C 的 E14 到 E16。
- **已知缺口：** pytest 包装每次扫描约耗 3 秒；premerge 选择仍依赖触发词匹配
  改动路径。
- **对规范设计的影响：** I5 改述为相等并说明偏离先例的理由；新增 I10；第 9 节
  增三行；第 10 节从一句话改写为表面表格。

### 2026-09-15 — 第四次评审 M0：范围、合并序、终态

- **基线：** 已合入 `503991dd2`；`upstream/main` 在 `2f84af990`，领先分支十二
  个提交。
- **触发：** 第四次评审问守卫的输入依赖什么、"全仓库"覆盖什么。把十二个上游
  提交合入临时树后清单过期（一个枚举、三个闭集）；对上游最近二十次合并重放
  扫描器，八次会有同样结果。RFC 写全仓库，而清单根与每条字面量扫描都写
  `loopx/`；`examples/` 有十余处 `effective_action` 断言，`apps/` 约九十个
  TypeScript 文件，smoke 从不读取。
- **同时发现：** `SOURCE_SURFACES` 是四个 CLI 命令各列自己的数据来源，不是分
  叉；按名归组的规则无法表达这一点。退休预算按子串计数（`goal_boundary` 35
  对 30 个标识符模块）。计划有预算但没有终态，四个入口决策没有 owner 期限。
- **交付：** 第 3 节把扫描根固定为 `loopx/` 并把 `apps/` 与 `examples/` 列为
  非目标；第 5 节预告 M0.5 的 `scope` 字段并以 `SOURCE_SURFACES` 为首例；第 9
  节增三行已知边界；第 10 节增合并序风险与解释器两段；第 11 节增终态表；第
  12 节增 Q9 到 Q11 并给 Q2 加核实说明；注册表 `inventory_ratchets` 增一条关于
  误分类分叉的备注。代码与预算未变。
- **有意不做：** premerge planner 保留 `python3`，因为舰队所有命令都这样拼写，
  runner smoke 也断言了这段文本；改为记录解释器要求。
- **证据：** 附录 C 的 E17 到 E20。
- **对规范设计的影响：** 第 3 节范围收窄以匹配代码；第 11 节有了完成定义；第
  12 节增三条决策。

### 2026-09-15 — 角色与作用域模型写入契约

- **触发：** RFC 使用"生产者"与"消费者"十九次却从未定义，Q2 与 Q10 依赖一个
  文中从未说明的"生产者检查"，`scope` 只存在于一段预告，且第 1 节在第 10 节
  把 pytest 扫描定为义务之后仍写 smoke "在每次 premerge 与 full-public 运行"。
- **交付：** 第 5 节新增"词表的角色"（owner、生产者、解释者、透传者）与三行
  schema（`scope`、`producers`、`compatibility_only`）；第 2 节新增 I11 到 I14，
  每条标注自 M0.5 起强制；第 9 节新增三行 M0.5 验证；第 11 节新增 M0.5 里程碑，
  M1 改为以它为门；Q2 与 Q10 指向 I12 而非未定义的检查；第 1 节与第 10 节一致。
  代码、注册表值与预算未变；M0 的 smoke 尚未强制 I11 到 I14。
- **对规范设计的影响：** 新增四条带明确强制里程碑的不变量；计划有了"被生产"
  的定义，M3 的零读者门与 Q2 的持久化问题都能使用它。

## 附录 B：决策日志

| 日期 | 决策 | Owner / 批准 | 备选 | 变更的规范章节 |
| --- | --- | --- | --- | --- |
| — | 尚无记录 | — | — | — |

## 附录 C：证据登记

| 证据 id | 声明 | 基线 / 环境 | 产物或命令 | 结果 | 隐私 / 有效性边界 |
| --- | --- | --- | --- | --- | --- |
| E1 | envelope schema 常量有三处定义 | `1dc6ad8d8` | `rg -n 'TURN_ENVELOPE_SCHEMA_VERSION\s*=' loopx` | 3 个文件 | 仅源码 |
| E2 | `loopx/` 下 28 个不同的 `effective_action` 字面量 | `1dc6ad8d8` | smoke 的 `literal_scan` | 28 | 受正则约束；不含散文提及 |
| E3 | 控制面下 43 对 py/ts 孪生 | `1dc6ad8d8` | smoke 孪生报告 | 43 | 仅同名规则 |
| E4 | 旧字段分布 | `1dc6ad8d8` | smoke 预算报告 | 见注册表 | 模块提及数，非调用点 |
| E6 | 闭集载体全局普查 | `1dc6ad8d8` | `python3.11 scripts/generate_semantic_inventory.py` 摘要 | 102 枚举、490 闭集、8 别名、40 数组、2002 命名常量、166 孪生、25/58 分叉、18/59 冲突 | AST 与 `as const` 文本扫描；仅模块级 |
| E7 | 第一版扫描模式捕获零个 TypeScript 站点 | `1dc6ad8d8` | 对每个含 `effective_action` 的 `.ts` 行应用该模式 | 7 个分发文件中 0 个匹配；`===` 总是失败 | 受模式约束 |
| E8 | 第一版 smoke 全绿时基线上已有两个未注册 `effective_action` 值 | `1dc6ad8d8` | `turn_journal.ts:656` 三元表达式 | `observe_replay`、`block_replay` | 同上 |
| E9 | owner 检查跳过了裸模块 owner | `1dc6ad8d8` | 第一版 smoke 的 `if "::" in python_owner` | `effective_action` 的 owner 从未被检查 | 读码加突变 |
| E10 | 二十个漂移突变全部失败关闭（TS `===`、TS 三元、Python 成员、经 `or ""` 的 Python `==`、裸 owner、删 owner、收窄后缀、重命名词表、分叉符号、删 TS 值、扩宽枚举、改投影、旧字段回涨、清单过期、第三种冲突拼法、死值、变量生产者消失、子集破坏、schema 版本分叉、注册表未知键） | `1dc6ad8d8` + 本地改动，改动新增载体时重新生成清单，每次运行后恢复 | 临时改动后以 `python3 -B` 运行 smoke | 20/20 退出码 1 并点名规则、值或文件 | 本地练习，非提交测试 |
| E5 | 九个漂移突变全部失败关闭（含数字与不含数字的未注册字面量、分叉常量、删除 TS 种类、扩宽 Python 枚举、改投影、旧字段回涨、注册表死值、新 py/ts 孪生） | `1dc6ad8d8` + 本地改动，每次运行后恢复 | 临时改动后以 `python3 -B` 运行 smoke | 9/9 退出码 1 并命名违规值或文件 | 本地练习，非提交测试；同尺寸同秒改写需 `-B` 绕过过期字节码 |
| E11 | 注册表可以在一个 diff 内放松自己的棘轮 | `1dc6ad8d8` + 本地改动 | 十四种注册表突变：调低一个下限、调低全部下限、在删掉它统计的 owner 的同时调低下限、调高全部 `inventory_ratchets` 条目、调高单个条目、调高一个退休预算 | 锚点前 7 种逃逸，锚点后 0 种；每个被捕获的失败都命名被锚定的值 | 本地练习，非提交测试 |
| E12 | 599 个多值载体只被列出、从未被比较 | `1dc6ad8d8` | 对枚举、闭集、`Literal` 别名与 `as const` 数组应用冲突规则 | 基线上已有 4 个同名分叉（10 个定义）与 19 个孪生，均未入预算；仅 `SOURCE_SURFACES` 就有四套不同值集 | 按名字归组；一次改名会把一个名字移出比较 |
| E14 | smoke 不在 PR 路径上 | `1dc6ad8d8` + M0 | `loopx canary premerge --changed-file loopx/control_plane/turn_driver/loop_controller.py --changed-file loopx/control_plane/quota/turn_envelope.ts`；`.github/workflows/full-public-smokes.yml` 的触发条件 | 规划 32 条命令，smoke 缺席；舰队只在 push 到 `main` 与日程运行 | 按路径 token 选择；CI 接线读自工作流文件 |
| E15 | 已收紧的预算可以漂回锚点 | `1dc6ad8d8` + M0 | smoke 中的 `ratchets[key] <= BUDGET_ANCHOR[key]` 与 `floor[key] >= anchored` | 收紧后的预算与锚点之间的任何值都能通过 | 代码阅读；先例用同样的比较 |
| E16 | 相等性关闭停滞，包装进入扫描 | `1dc6ad8d8` + M0 | 只调低一个 `inventory_ratchets` 条目而不动锚点，然后在干净树上跑 `pytest tests/architecture/test_semantic_vocabulary_drift.py` | 突变失败并同时命名两个值；包装约 3 秒通过 | 本地练习加已提交测试 |
| E17 | 上游合并会让已提交清单过期 | `upstream/main` `2f84af990`，最近 20 个 first-parent 合并 | 对每个改动的 `loopx/**/*.{py,ts}` 在第一父提交与合并结果之间比较扫描器事实 | 20 次合并中 8 次至少改变一个载体；本分支自己的上游同步新增 1 个枚举与 3 个闭集 | 事实级比较，等价于完整再生成 |
| E18 | 声明范围超出扫描根 | `503991dd2` + M0 | 从注册表读 `literal_scan.roots` 与清单 `root`；在 `examples/` 下 `grep` `effective_action` 分发字面量；统计 `apps/` 下 `.ts`/`.tsx` | 根只有 `loopx`；`examples/` 12+ 处断言；`apps/` 90 个文件 | 消费者与测试替身，非生产者 |
| E19 | `SOURCE_SURFACES` 是四个有界上下文，不是分叉 | `503991dd2` | 从清单读出四个 `multi_value_forks` 定义 | 每个模块列出自己 CLI 命令的数据来源，值互不相交 | 读值后的判断；规则本身做不出 |
| E20 | 退休预算按子串高估 | `503991dd2` | 对 `loopx/**/*.py` 分别用 `'goal_boundary' in text` 与 `\bgoal_boundary\b` | 35 对 30 个模块 | 标识符计数才是 M3 门的度量 |
| E13 | 冲突预算主要在度量局部命名 | `1dc6ad8d8` | 对 `conflicting_values` 与 `same_runtime_forks` 名字应用 `MODULE_LOCAL_CONVENTION` | 18 个冲突中 16 个、25 个分叉中 7 个是模块局部约定；语义子集分别为 2 与 18 | 分类是名字模式，已在扫描器中说明并由夹具测试钉住 |

## 附录 D：被否决或取代的方案

见第 6 节。单 PR 合并枚举被否决，因为三套枚举变化原因不同；可重开该决策的证据
是 M2 之后投影被证明为双射。

## 附录 E：事故与评审教训

- 跨运行时手工同步的平行常量列表在其中一侧改变之前总能通过评审；接受第二份
  副本之前必须先有一致性检查。
- 在大模块里私有抽一份共享常量看起来无害，却是 schema 版本分叉最常见的方式。
  测试夹具是第二常见的方式：`HANDOFF_MODES` 被复制进了一个 e2e 夹具。
- 只接受 `[a-z_]` 的字面量扫描在 M0 突变练习中悄悄放过了 `_v2` 拼法。应捕获
  所有带引号字符串并单独校验形状，让畸形值被报告而非被忽略。
- 按 Python 例子写出的扫描模式在 TypeScript 上一个都不匹配；一个在含违规的
  基线上仍然全绿的守卫，只证明守卫是盲的。在宣称不变量之前，对注册表声称
  覆盖的每个运行时做突变测试。
- 当注册表既是规范又是校验器的输入，一次数据修改就能削弱校验器。把识别形式
  留在代码里、给覆盖计数设下限、拒绝不是 `module::Symbol` 的 owner。
- 只按名字计数的棘轮会放过已冲突名字的第三种拼法。定义数与名字数都要预算。
- 舰队能发现的 smoke 不是提交时检查。要问它被哪个必需的 PR 作业收集，并用
  一个只改被守护代码的 diff 做规划，看选择是否找到它。如果答案是"合并后"，
  这条不变量就是报告，不是门。
- 用 `<=` 比较的锚点只钉住写下它时的值。之后的每次收紧都无保护，直到有人记得
  挪锚点。用相等性比较，两个值就分不开。
- 同一个字段名可以在一个 envelope 里承载多套词表；看得见字段的扫描看不见
  槽位。把槽位记为关系，让歧义成为已登记的事实，而不是注册表背书的意外。
- 整棵树的已提交快照让守卫的输入依赖别人的合并。提交它之前先量一下树在它
  之下变化的频率，并写下 `main` 变红时由谁再生成。
- 按名归组的碰撞规则需要一种方式说"这些是共用一个名字的不同东西"。没有它，
  诚实的修法与不诚实的修法（改名）降低的是同一个数字，评审者分不出来。
- 文档比代码更快地扩大范围时，两者必须朝更便宜的那个方向对齐，但必须一致。
  扫描器没有实现的范围声明是一条假不变量。
- 只降不升的预算描述的是方向。在第二个里程碑之前写出目标表，否则没人能说
  工作何时完成。
- 等待一个 RFC 从未定义的"检查"的决策，是披着审慎外衣的悬空引用。点名交付
  该检查的不变量与里程碑，否则决策没有输入，永远关不掉。
- 用了十九次角色词（生产者、消费者）不等于定义了它。在角色成为一张每行带检查
  的表之前，"谁写入这个值"是每个评审者答案都不同的问题。
