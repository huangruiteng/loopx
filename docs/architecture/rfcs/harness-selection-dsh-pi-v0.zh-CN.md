# DSH / Pi：L1 观察与 Managed Runtime 选型

状态：有证据的实现评估，不是运行时晋级声明。
范围：[Reliability Diagnostics](./long-running-agent-reliability-diagnostics-governed-delivery-v0.zh-CN.md)
与 [Desktop Execution Frontends](./desktop-execution-frontends-v0.zh-CN.md) 的共同目标。
[English](./harness-selection-dsh-pi-v0.md)

## 决策

保留 **DSH 作为 L1 首个事件源**，但不据此宣布它已成为生产 Mode B 的最终首选。
Pi 保留为 managed runtime 候选。前者利用已存在的被动 observer 降低验证成本；后者
必须证明生命周期、provider、崩溃恢复和真实结果，插件事件 fixture 不能替代这些证据。
本评估不提供缺乏测量依据的评分或性能排名。

## 证据基线

LoopX 检查基线为 `bf217e1e01bec79f357c9ecbd580cf2dfa73db8b`：

- `packages/dsh-loopx-plugin/src/observer.ts`：完整身份激活、事件压缩、首次落盘安全、
  有界 buffer 和 flush 隔离。
- `loopx/capabilities/reliability_diagnostics/{receipt,projection}.py`：独立验证、
  integrity 分类和无控制权限的诊断输出。
- `loopx/dsh_goal_mode/turn_host_adapter.py`：有界 Turn、session lineage、SDK 调用和
  失败映射，并不是完整 Desktop 外循环。
- `loopx/pi_goal_mode/{loopx-goal.ts,pi-goal-loop-runtime.mjs}`：有绑定及 continuation
  行为的可见宿主集成，不是被动 observer。
- `apps/desktop/loopx-control-plane/src-tauri/src/services.rs`：已有服务进程管理不等于
  RFC 所要求的完整 managed Agent 生命周期。

2026-09-06 独立检查的上游版本，不等同于 LoopX 已验证的安装版本：

- [DSH d347e703 README](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/README.md)：
  Cordis/plugin 架构，明确处于可能不兼容升级的 developer preview。
- [Pi 9767ba27 SDK](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/docs/sdk.md)：
  subscribe、session 操作及 runtime replacement API。
- [Pi 9767ba27 extensions](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/docs/extensions.md)：
  部分 hook 可以注入上下文、阻止工具调用、修改结果。

历史 Pi 仓库地址目前跳转至 `earendil-works/pi`，本次 SDK 文档使用
`@earendil-works/pi-coding-agent`。这是升级时要核对的差异，不是立即替换本地依赖
或假定新旧 API 兼容的理由。

## 按产品要求对比

| 要求 | DSH 证据 | Pi 证据 | 对选型的影响 |
| --- | --- | --- | --- |
| 被动观察 | 已有独立 observer entry、三个 session publication hook、首次落盘拒绝 | SDK 提供 subscribe，extensions 还提供干预型 hook | DSH 已有可验证切片；Pi 应优先订阅而非拦截，并证明隔离 |
| 身份与恢复 | Turn connector 派生 lineage；observer 另外要求精确 goal/session/run | SDK 将 AgentSession 与负责 replacement/resume 的 AgentSessionRuntime 分开 | 两边都要测重启、fork 后身份；有 API 不等于恢复可靠 |
| 单次有界执行 | 已有 timeout 和失败映射 | 当前 Pi Goal 集成含 continuation/pause | 不允许 native loop 与 Desktop supervisor 同时充当外循环 |
| 打包 | 独立 export/bundle、packed smokes | SDK resource loading 会发现 extensions | 检查实际加载的包及 profile；二者都不是 OS 进程隔离 |
| Provider | connector 版本与 SDK 约束明确 | SDK 暴露 runtime/model 构造 | 同 route/model/tools/budget 验证，harness 选择不代表 provider 兼容 |
| 数据安全 | producer/consumer 独立校验，共享反事实 | 工具/context hook 可接触和修改原文 | Pi 需补首次落盘安全及负向测试，不能复制 transcript |
| 开销 | 已有 buffer/count/flush 统计，没有本次匹配实测 | 有订阅接口，没有本次 LoopX observer 测量 | 未实测前不作数字排名 |
| 维护 | 上游明确可能 breaking，LoopX connector 有固定验证版本 | 当前包名与 runtime API 不能直接套用旧集成假设 | 两边升级分别固定版本，不拿已安装 DSH 对比未验证最新 Pi |

这是接入成本和合同差异，不是说 Pi 没有事件，或 DSH 不能使用其他模型。
两个 harness 都有控制 API；“被动”是具体 adapter 和实际加载依赖的性质。

## 数据流与权限

用户需要区分“没有证据”“执行有异常”“观察过程不可信”，而不是只得到一个绿灯：

```text
native session publication
  -> isolated observer: compact / validate / count / append
  -> independent ledger validation
  -> integrity receipt + diagnostic projection
  -> 仅供操作者展示

canonical eligibility -> Desktop supervisor -> bounded Turn -> validation/writeback
```

诊断不得反向进入 eligibility。`valid` 只代表观察合同通过，不代表任务成功；stall
信号不是重试授权，observer 故障也不能被当成 worker 故障。

## 本次落地的读取增量

```bash
loopx reliability-diagnostics status --goal-id <goal-id> --with-receipt --format json --as-of "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

上述 POSIX shell 示例使用当前 UTC 时间评估年龄；其它客户端应传入带时区的当前时间。
仅在历史重放时省略 `--as-of`：默认使用最后事件时间，因此最后事件年龄为零，不能
作为实时存活检查。分别显示观察时间和评估时间；推进评估时钟不改变 integrity。

显式选项让 receipt 与 projection 来自同一次 ledger 读取的内存结果，避免分别执行
两次 CLI 时观察到不同追加状态。不加选项保持原输出。这不提供文件并发追加的原子
快照；末尾半行仍按无效输入报告，不能悄悄丢掉。命令不激活 observer、不发现绑定、
不写 ledger、不调用模型，也不改变 Goal/Todo/lease。

这是可执行的读取接口，**不是已交付的 Mode B 面板或 supervisor**。未来面板必须
绑定精确 goal/session/run，分别展示观察时间、integrity 与任务状态；多 run 或过期
goal ledger 不得被标成当前 session 健康。输出只供操作者，不得进入 prompt 或调度。
现有 CLI 全量 ledger 读取没有大小上限，在引入经过评审的读取预算／快照策略之前，
不能直接拿这个命令做自动轮询。

## 验收方案与停止条件

1. **C0 保真**：比较 native 与 observer 关闭的 managed adapter。固定 model、route、
   tools、prompt、环境、预算、包／adapter 版本及起始 session，计入失败和重试；
   treatment 不一致则不采纳比较结果。
2. **C1 被动观察**：在通过 C0 的 adapter 上只开启 observer。记录完整身份、
   accepted/persisted/rejected/drop 数、receipt、endpoint 和 worker/scheduler influence。
   fixture 通过不等于 C1；非 valid receipt 不作为 eligible C1。
3. **开销**：成对重复测 baseline/observer 的 wall time、CPU、peak RSS、写入字节、
   吞吐、flush latency；报告样本数、分布、不确定性、冷／热启动条件。预算及验收
   阈值在运行前约定，本次不虚构阈值或性能结果。
4. **保留／删除**：owner 选择最大年龄／字节、活跃 writer 处理、支持访问、备份范围
   和删除验证。先 dry-run 盘点再删除，不能为满足大小限制截断活跃 ledger。
5. **Mode B**：在可丢弃 runtime 验证 start/resume/interrupt/close、进程崩溃、过期身份、
   重复完成、超时及 provider 失败；同一时间一个 Turn，canonical validation/writeback
   通过后才扣 quota 或请求下一 Turn。

原始日志、凭据留在 owner-local；公共材料只保留通用方法、固定版本、聚合结果和
安全引用。本文件不授权真实模型执行或删除现有记录。

## 后续交付次序

先评审对比结论和 CLI 读取增量；Mode B 面板必须先具备精确 session 读取与有界刷新，
而不是新造一套通用监控。C0/C1 与开销作为单独预算实验，仅把复用修复和安全证据
提交仓库。删除功能等 retention profile 决定后再做。若 Pi 在相同隔离及生命周期
验收下具有更低的实测接入／运维成本，或 DSH 无法通过，再调整偏好。
不得为了让 L1 实验通过而加入 L2 建议、重试权限或新 scheduler。
