# 外发消息前的指导召回

[English](OUTBOUND.md)

这个可选的 Reward Memory surface 会在 Agent 发送消息前召回已经审阅过的
操作偏好。它不是消息传输、文本分类器或发送权限。首个正式调用方是绑定
Goal/Agent 的 `loopx lark-inbox send` 和 `reply`；本次集成不拦截其他工具，
也不拦截 Goal Topic 自动回复。

## 启用与验证

使用现有 Agent 级 Reward Memory 实验配置：把
`outbound_message.before_send` 加入 corpus、standing policy 与 `surfaces`，
adapter 使用 `scoped_feedback`，`peer_ref` 必须精确为
`agent:<agent-id>`，并启用 `automation.automatic_recall`。建议采用一次查询、
小结果上限的 function-boundary profile。只写入明确审阅过且可公开的
`soft_preference`；不要上传消息草稿或私有事故记录。

```sh
loopx configure-goal --goal-id <goal-id> \
  --reward-memory-config .loopx/config/reward-memory.json \
  --reward-memory-agent <agent-id> --execute
loopx reward-memory experiment-status --goal-id <goal-id> --agent-id <agent-id>
loopx lark-inbox send --goal-id <goal-id> --agent-id <agent-id> \
  --route-key <configured-route> --text '<message>' \
  --message-purpose help --provider-preflight --format json
```

Provider preflight 先校验身份、群成员、mention 和 provider dry-run，再执行
召回；不带 `--provider-preflight` 的普通预览不会调用任何 provider。启用后，
结果中会包含 `outbound_guidance`，但不会发消息。有相关指导时，即使第一次
带了 `--execute`，也会返回 `agent_review_required` 且写入次数为零。

执行 Agent 需要阅读指导，核对当前事实、替代方案、收件方和重复消息；仍然
应该发送时，用同一条 send/reply 命令加上 `--execute` 和返回的
`--reviewed-guidance-digest`。这是 Agent 的审视步骤，**不是用户审批**。
摘要绑定了指导、用途、scope、发送方、目标、placement 和消息；任一变化都会
让旧摘要失效。它只能证明 Agent 确认过指导，不能证明推理质量。原发送器继续
负责幂等和 readback。

用途包括 `help`、`progress`、`urgent` 和默认的 `unspecified`，不根据消息
文本猜测用途。紧急通知会召回指导但不会等待复审；记忆为空或 provider 不可用
时保留既有发送路径，不会生成用户卡点。原有权限或发送方校验仍会正常阻断。
本适配器不把 hard-policy 记忆解释成软性指导。

通用实现位于 `reward_memory.outbound`，Lark 适配器只收到不透明的意图摘要。
原始文本、群 ID 和发送 profile 不进入召回查询；指导只出现在调用方私有结果，
不会被发送给收件方，也不会写入公开 registry。

## 关闭与覆盖范围

将 `automation.automatic_recall` 设为 `false` 可关闭该实验的召回；仅移除
这个 surface 可单独关闭外发召回。未配置的 Agent 与现有直接 provider 调用
保持原行为。启用不会授予 provider 凭证或外部写权限。

测试覆盖真实召回核心、readback、Agent scope、意图变化、provider 不可用、
紧急通知及两个真实发送入口的合成传输。实时验证只能做只读 provider 检查；
测试不得以 smoke 的名义向群里发送消息。
