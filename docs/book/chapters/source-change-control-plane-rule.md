# 修改一条 Control-Plane 规则

Control Plane 的改动很少只影响一个返回值。一条看似简单的规则，可能改变 Agent 选择哪项工作、
用户是否被打断、Host 是否继续唤醒，以及一次执行能否记为有效 spend。

因此，安全的修改顺序不是“找到 `if`，改条件”，而是：

```text
problem
  -> invariant
  -> source facts
  -> ordered decision
  -> protocol delta
  -> implementation owner
  -> independent oracle
  -> rollout and recovery
```

本章以一个合同修复为例：

> 当一个 open Gate 缺少足以判断 coverage 的 scope relation 时，LoopX 必须进入 typed repair，
> 不能把它猜成全局阻塞，也不能把它猜成已授权。

这是对现有 authority invariant 的恢复，不是新产品能力。

## 本章目标

读完后，你应该能：

- 把 bug report 改写成 source facts、invariant 与 forbidden outcomes；
- 判断变更是实现修复、协议扩展、兼容迁移还是新能力；
- 用 ordered rules 表达 precedence，包括抑制某动作的负向规则；
- 选择正确的 bounded context 和最小完整改动面；
- 从语义 oracle 设计 contract、smoke、replay 与 canary；
- 在改动高风险 public contract 时知道何时必须停下来请求设计或 owner review。

## 先区分四种变更

同一句“需要改规则”可能代表四种工作：

| 类型 | 含义 | 默认处理 |
| --- | --- | --- |
| Implementation repair | 代码违反已有协议 | 修实现并增加回归证据，通常不升协议版本 |
| Protocol clarification | 多种解释存在，文档未定 | 先完成设计评审，再同时更新合同与实现 |
| Additive protocol change | 新的合法状态、字段或 transition | 定义兼容、default、writer 与 reader |
| Breaking migration | 旧输入或输出不再合法 | 显式版本、迁移 reader、release 与 stop gate |

本章案例属于第一类。现有
[`decision_scope_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/decision-scope-v0.md)
已经规定 Gate 是 scoped authority；[State Machines](https://github.com/huangruiteng/loopx/blob/main/docs/product/core-control-plane/state-machine.md)
也把 ambiguous scope 导向 repair。

如果实现把它变成全局 wait，应该修实现，而不是新增一个“允许全局猜测”的兼容字段。

## 第一步：冻结问题的语义

先写 source facts，不写当前实现输出：

```text
F1: an agent todo requires decision scope S1
F2: an open user gate exists
F3: the gate has no valid scope relation
F4: no explicit global authority is present
```

再写 invariant：

```text
authority cannot be inferred from prose or missing data
```

由此得到允许结果：

```text
the affected gated action does not run
the ambiguity becomes a typed repair or concrete decision question
explicitly independent work may continue only when safety is still provable
```

以及禁止结果：

```text
missing scope grants S1
missing scope becomes an implicit global gate
the gate disappears from the user channel
the host reconstructs authority from display text
```

这一步是后续测试的独立 oracle。不要先运行当前代码，再把它的 JSON 复制成期望结果。

## 第二步：画出规则拥有的协议链

这个修复至少经过以下边界：

```text
Gate/Todo source
  -> scope projection
  -> coverage decision
  -> goal and agent frontier
  -> interaction contract
  -> scheduler hint
  -> repair writeback
```

逐层标记 owner：

| 边界 | 合同责任 | 本次是否应改变 |
| --- | --- | --- |
| Gate/Todo source | 保存 typed scope 与 lifecycle | 否，已有字段足够 |
| Scope projection | 保留 missing/invalid diagnostics | 可能，若这里丢失诊断 |
| Coverage decision | matching、unrelated、ambiguous、global | 是，若错误发生在 policy |
| Frontier | 排除不可授权 action，保留可证明独立工作 | 只在 selection 错误时 |
| Interaction contract | 分开 user、agent、CLI channel | 可能，需要暴露 repair |
| Scheduler hint | 消费最终 decision | 不应重新发明规则 |
| Writeback | 记录修复、decision 或 blocker | 复用现有 lifecycle |

这样可以避免两个极端：

- 只改 policy，却让 projection 继续丢失诊断；
- 因为链条跨模块，就顺便重构整套 status、quota 和 scheduler。

改动面应覆盖第一处错误及其必要消费者，不覆盖无关结构。

## 第三步：把 policy 写成 decision table

先用表格表达互斥结果：

| Gate facts | Todo requirement | Expected mode | Forbidden mode |
| --- | --- | --- | --- |
| Valid matching scope | Requires same scope | `operator_gate` | normal gated delivery |
| Valid unrelated scope | Requires another scope | independent frontier | global wait |
| Non-blocking `user_action` | Requires protected scope | scope remains unmet | authorized delivery |
| Missing/invalid scope | Requires protected scope | typed repair | approval or implicit global gate |
| Explicit global gate | Any covered action | global operator gate | independent covered delivery |
| Other-agent scoped gate | Current Agent unrelated | current safe frontier | cross-agent freeze |

这张表至少包含三类证据：

1. **正例：** matching Gate 确实阻塞；
2. **反例：** unrelated Gate 不应阻塞；
3. **非法状态：** ambiguous Gate 不能被任意解释。

只写 happy path 会漏掉 Control Plane 最危险的错误：两个局部合理的布尔值组合后产生越权。

## 第四步：显式规定 precedence

真实 quota decision 还会同时看到：

- registry 或 projection health；
- autonomous replan；
- handoff owner route；
- capability 与 workspace guard；
- due monitor；
- throttle 与 pause。

因此，需要说明本规则位于哪个优先级，而不是只写一个 predicate。

一种可审阅的表达是：

```text
1. invalid source/projection relation -> repair owns the transition
2. valid matching authority gate -> ask/wait for that scoped decision
3. valid independent frontier -> bounded delivery may continue
4. no runnable work -> wait/replan/terminal according to existing contracts
```

这里第 1 条必须先于普通 Gate wait。否则系统会把“无法判断 scope”伪装成“已正确判断为阻塞”，
projection gap 永远不会被修复。

第 3 条是负向规则：它证明 Gate 与候选 action 无关时，不能让低层 `open_gate_count` 抢占。
负向规则与触发 repair 的正向规则同样需要名字、理由和测试。

### First-match 规则的审查方法

对每一行问：

- 哪些 facts 必须同时成立？
- 哪个更高优先级规则会先截获它？
- 它是否产生 obligation，还是明确抑制 obligation？
- reason code 能否解释为什么命中？
- 加入一个无关 Gate、Todo 或 Agent 后，结果是否保持不变？

最后一个问题会自然导出 metamorphic test，而不是脆弱的整份 JSON snapshot。

## 第五步：决定协议是否需要变化

本案例不需要增加新 source 字段，因为现有协议已经能表达：

- valid scoped Gate；
- explicit global Gate；
- required decision scope；
- missing/ambiguous relation；
- repair 与 user/agent channel。

因此合理结论是：

```text
protocol semantics: unchanged
implementation conformance: repaired
new public field: none, unless current output cannot expose typed repair
migration: none
```

如果必须增加 public field，继续回答：

1. 它是 canonical source，还是 derived diagnostic？
2. 谁写，谁读？
3. 缺失时的 default 是什么？
4. old reader 会忽略、降级还是出错？
5. 它何时可以删除？
6. 是否触发 output budget、dashboard、Host 或 release compatibility？

不能回答这些问题时，不要以“方便调试”为由把字段放进默认热路径。

## 第六步：选择实现归属

根据 change reason 分配责任：

- scope schema 与 lifecycle 属于 Todo/Gate owner；
- agent-scoped selection 属于 Agent/Todo read model；
- precedence 与 interaction mode 属于 Quota policy；
- cadence 属于 Scheduler；
- Markdown/JSON 呈现属于 Presentation；
- controlled repair writeback 属于原 lifecycle writer。

不要创建一个泛化 `gate_utils.py` 来容纳所有碰巧读取 Gate 的代码。共享的是 authority knowledge，
不是字符串处理的外观。

### 何时需要新模块

只有在以下条件同时成立时，才考虑新模块：

- 有一个内聚、可命名的规则族；
- 它有真实调用方；
- 输入与输出可以形成稳定 contract；
- 现有 owner 因 change reason 不合适；
- 有 characterization/parity 保护移动；
- 旧内部入口可以删除，或确有外部兼容窗口。

大文件是重新审视 ownership 的信号，不是自动抽 helper 的理由。

## 第七步：设计最小完整验证

验证从语义风险向外扩展。

### 1. Contract / decision-table test

用上一节的 source facts 直接检查：

- matching；
- unrelated；
- non-blocking notice；
- ambiguous；
- explicit global；
- cross-agent isolation。

预期来自协议表，不从 product builder 生成。

### 2. Negative 与 metamorphic coverage

至少加入：

- 把 unrelated Gate 数量从 1 增加到 8，当前 decision 不变；
- 修改 renderer 文案，authority 不变；
- 把 `user_action` 文本改成 “approved”，仍不授予 scope；
- 增加 other-agent backlog，不改变 current Agent 的 repair；
- 补齐 valid scope 后，repair 可以转成匹配 Gate 或独立 frontier。

这类测试直接保护“不相关变化不能改变决策”。

### 3. Focused integration

运行真实 source-to-quota 路径，确认：

- projection diagnostics 没有丢失；
- final `interaction_contract` 选择 repair；
- scheduler 消费最终结果；
- gated action 没有进入 TurnEnvelope；
- 无 validation/writeback 时没有 quota spend。

### 4. Public-safe replay

Fixture 只保存最小 source facts、独立 invariant 和 expected outcome。不要保存：

- raw active state；
- transcript 或完整 prompt；
- 私有 Issue/PR 链接；
- 本机 registry 路径；
- stdout/stderr tail。

Replay 应重新执行真实 decision path，而不是只验证 fixture schema。

### 5. Risk-based canary

如果改动触及 quota、scheduler、todo/gate 或 agent-facing output，让 canary 根据 Git diff 选择相关
surface。Canary 是跨边界补充，不替代前面的聚焦回归。

## 第八步：定义失败与恢复

一条规则不完整，常常不是因为正常输出错，而是因为失败后没有合法下一步。

本案例至少需要区分：

| 失败 | 状态 | 下一步 |
| --- | --- | --- |
| Source 缺 scope | typed source/projection repair | 补齐或明确 global scope |
| Parser 丢 scope | projection gap | 修 read model 并重算 |
| Conflicting duplicate Gate | repair with diagnostics | 由 lifecycle owner 去重或 supersede |
| User 无法决定 | deferred Gate | 写 supported `resume_when` |
| Repair writer 冲突 | revision conflict | fresh read 后重试，不覆盖他人写入 |
| Host 无 repair capability | capability blocker | 保留具体 owner action |

“继续等待”不能成为所有错误的 fallback。等待必须有对象、恢复条件和 freshness 策略。

## 第九步：处理兼容与迁移

如果规则修复会让过去被接受的输入变成 invalid，先判断那些输入是否：

- 真实 public contract；
- 只存在于本地 runtime state；
- 旧版本的 canonical event；
- 测试 fixture 的偶然形状；
- 已经错误但被实现容忍的状态。

只有真实兼容承诺才需要长期 reader。迁移通常采用：

```text
legacy input
  -> explicit migration reader
  -> exactly-once normalized event
  -> canonical output contains only new shape
```

不要让 legacy 字段继续出现在新 writer 中，也不要用永不删除的 wrapper 保存错误 ownership。

如果修复只恢复已有协议，兼容目标应是合法行为，不是继续支持越权结果。

## 第十步：把文档更新放在正确位置

协议变更时，文档责任不同：

| 文档 | 应记录什么 |
| --- | --- |
| Protocol | source、state、invariant、transition、failure |
| State machine / seam map | precedence、owner 与组合关系 |
| Contributor guide | 如何开发、验证、提交 |
| User guide | 用户能观察和处理的行为 |
| Changelog / release | 兼容、默认值或迁移影响 |

不要把所有解释都追加到一个课程章节，也不要让 Book 变成 LoopX protocol 的影子事实源。本书解释
方法；具体字段与当前状态仍由官方协议拥有。

## 一个完整的改动说明

开始实现前，可以写成：

```text
Problem:
  Ambiguous Gate scope is currently projected as a global wait.

Invariant:
  Missing authority data grants nothing and cannot imply global scope.

Protocol status:
  Existing decision_scope_v0 behavior; implementation repair only.

Rule delta:
  Ambiguous relation selects typed repair before ordinary operator-gate wait.

Unaffected:
  Valid matching scopes, explicit global gates, independent safe work,
  Host capability declarations, and lifecycle storage.

Evidence:
  Decision table, metamorphic cases, source-to-quota integration,
  public-safe replay, and diff-selected canary.

Recovery:
  Repair writes through the existing lifecycle path with revision checks.
```

Reviewer 不必先理解所有实现，就能判断这项修改是否完整、是否超出 scope。

## 常见失败方式

### 只测试一个新结果

没有抑制条件与反例，通常会改变其他 Agent、monitor 或 Gate 的 precedence。

### 给每个分支增加布尔值

多个布尔值很快产生非法组合。优先使用 closed state、typed reason 和 ordered transition。

### 让 renderer 修 policy

修改文案不能修复 source 或 authority；反过来，policy 也不应依赖 Markdown 字符串。

### 为未来 Host 增加空 adapter

没有真实调用方、capability 和 receipt 的 adapter 只增加维护面。

### 用 characterization 证明正确

Characterization 证明“过去如此”，不证明“应该如此”。发现与 invariant 冲突时要修规则，而不是
刷新 golden。

### 顺手重构所有相关模块

协议链跨模块不等于 PR 应包含所有可能清理。只修改本次 invariant 所需的完整链条。

## 本章检查表

修改规则前，确认：

- [ ] 已区分 implementation repair、clarification、additive change 与 breaking migration；
- [ ] Source facts、invariant、allowed 与 forbidden outcomes 已独立写出；
- [ ] Protocol chain 和每个 owner 已画清；
- [ ] Decision table 同时覆盖正例、反例与非法状态；
- [ ] Precedence 和 negative rules 可以被审查；
- [ ] 新字段、模块、CLI 或 adapter 都有真实调用方和生命周期；
- [ ] Oracle 不来自当前实现输出；
- [ ] Failure、retry、idempotency 与 recovery 已定义；
- [ ] Compatibility 只保护真实合同，不保护错误行为；
- [ ] 文档更新回到各自的 authoritative home。

需要把这套方法映射到 Kernel bounded context、ordered rule、schema、projection 和 smoke 的真实
源码链时，继续阅读
[Control-Plane Course 第 7 讲](/loopx/docs/development/control-plane-course/07-engineering-a-control-plane-rule/)。
本章负责外部贡献的端到端方法；课程负责更深的实现推导与评审练习。

下一章把这项规则修复从本地验证推进到 PR：如何选择质量层、组织 commit、扫描公开边界，并给
reviewer 一份协议级证据包。
