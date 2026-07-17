# LoopX Developer Guide / LoopX 开发者指南

This directory is the stable entry point for contributors changing LoopX
runtime behavior, public contracts, tests, or release gates. Product users do
not need these documents to start LoopX.

本目录是修改 LoopX 运行时、公开合同、测试和发布门禁时的稳定入口。普通产品
用户接入 LoopX 时不需要先阅读或配置这些开发者能力。

## Start Here / 从这里开始

1. Read [Contributing](../../CONTRIBUTING.md) for repository boundaries and the
   pull-request checklist.
2. Follow the [control-plane developer course](control-plane-course/README.md)
   for an eight-lecture, code-led path through the real CLI and state machine.
3. Read [Testing and quality](testing-and-quality.md) before changing agent-facing
   output, scheduler decisions, todo/gate semantics, onboarding, or release
   promotion.
4. Use [Architecture](../architecture.md) and the
   [core control-plane graphs](../product/core-control-plane/README.md) to find
   the bounded context that owns the behavior.
5. Check [Public/private boundaries](../public-private-boundary.md) before adding
   fixtures, examples, evidence, or provider-backed evaluation.

1. 先阅读[贡献指南](../../CONTRIBUTING.md)，了解仓库边界和 PR 检查项。
2. 按顺序学习[控制面开发者 8 讲](control-plane-course/README.md)，沿真实 CLI、
   状态机和核心函数建立代码心智模型。
3. 修改 agent-facing 输出、调度决策、todo/gate 语义、新用户接入或发布流程前，
   阅读[测试与质量体系](testing-and-quality.md)。
4. 通过[架构文档](../architecture.md)和
   [控制面核心图](../product/core-control-plane/README.md)定位真正拥有该行为的
   bounded context。
5. 添加 fixture、示例、证据或模型测试前，检查
   [公开/私有边界](../public-private-boundary.md)。

## Core References / 核心参考

| Area / 领域 | Reference / 文档 |
| --- | --- |
| Control-plane code reading / 控制面代码领读 | [Eight-lecture developer course](control-plane-course/README.md) |
| Quality layers and commands / 质量分层与命令 | [Testing and quality](testing-and-quality.md) |
| Agent-facing size budgets / Agent 输出体积预算 | [Interface budget contract](../interface-budget-contract.md) |
| Status and decision payloads / 状态与决策载荷 | [Status data contract](../status-data-contract.md) |
| Quota and spend semantics / Quota 与 spend 语义 | [Quota allocation](../quota-allocation.md) |
| Model-behavior shadow qualification / 模型行为影子验证 | [Model behavior qualification v0](../reference/protocols/model-behavior-qualification-v0.md) |
| Release outcome comparison / 发布结果基线 | [Release outcome baseline v0](../reference/protocols/release-outcome-baseline-v0.md) |
| Release promotion / 发布晋级 | [Release readiness](../product/release-readiness.md) |
| Benchmark development / Benchmark 开发 | [Benchmark developer workflow](../benchmark-developer-workflow.md) |

## Change Loop / 变更闭环

Keep one shipped behavior as the source of truth. Characterize it first, make a
small change in its owning module, then choose validation by risk. Do not create
a second product path solely for a test.

始终只保留一套真实交付行为作为 source of truth：先刻画现状，在行为所属模块中做
小变更，再按风险选择验证层。不要为了测试而维护第二套产品路径。

The usual loop is:

```text
issue or regression
  -> deterministic characterization
  -> focused implementation
  -> focused tests and durable smoke
  -> catalog-selected canary
  -> owner review when behavior is sensitive
  -> release outcome observation when needed
```

通常闭环为：问题或回归 -> 确定性刻画 -> 聚焦实现 -> 单测与 durable smoke ->
catalog 选择的 canary -> 敏感变更 owner review -> 必要时观察发布结果。
