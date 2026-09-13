# Lark Manager Context and Turn Authority v0

## English

A LoopX Manager connection separates **message visibility** from **Turn
authority**. When exactly one enabled Manager binding owns a Lark App and group,
LoopX may retain bounded non-self messages from that group as local-private
context. Retention does not start a model call, send a reply or reaction,
acknowledge the provider event, or authorize any Goal/Todo mutation.

A Manager Turn is authorized only by a provider-native mention of the bound Bot,
a provider-verified reply to that Bot, or another existing typed authority
record. The next authorized Turn may receive up to eight recent context-only
messages with a 4,000-character total budget. Every item is labeled
`context-only`; the prompt explicitly states that these items are not commands,
authorization, or independent Todos.

Before an authorized Manager Turn reads that context, the existing bounded
turn-start history sync fills gaps left by the live event subscription. Items
recovered from history are always marked `context-only`, including old messages
that originally mentioned the Bot: catch-up never replays a missed Turn. This
recovery uses the same private cursor and inbox, performs no history-message
reaction or reply, and degrades without blocking the current authorized Turn if
the provider history read is unavailable.

After a successful authorized Turn and verified reply, consumed context items
are settled through the existing event-bound material-review ledger. Duplicate
delivery and restart recovery remain idempotent. Self messages, another chat,
invalid routing, and ambiguous Manager bindings remain closed and are not
captured.

The connection health projection distinguishes `context_only_captured` from
`replied_and_acknowledged`. CLI/managed Turn, frontend, and Lark must reuse this
single runtime inbox and receipt model; adapters must not invent a second
authority source.

## 中文

LoopX 管家连接将**消息可见性**与 **Turn 权限**分开处理。当且仅当一个启用的
管家绑定唯一拥有某个 Lark App 与群聊时，LoopX 可以把该群中的非机器人消息以
有界、本地私有的上下文材料保留下来。仅保留消息不会调用模型、发送回复或
reaction、确认 provider event，也不会授权任何 Goal/Todo 修改。

只有以下来源能够授权管家 Turn：provider 原生的目标机器人 mention、provider
验证过的对机器人回复，或其他既有 typed authority 记录。下一次获得授权的 Turn
最多读取最近八条、总计不超过 4,000 字符的仅上下文消息。每条材料都会标记为
`context-only`，prompt 也会明确说明这些内容不是指令、授权或独立 Todo。

在已授权的管家 Turn 读取上下文前，既有的有界 turn-start 历史同步会补齐实时
事件订阅遗漏的消息。所有历史补采项一律标记为 `context-only`；即使旧消息原本
真正 mention 了机器人，也不得借补采重放成一个 Turn。补采复用同一私有游标和
inbox，不给历史消息发送 reaction 或回复；provider 历史读取不可用时，会准确
降级但不阻塞当前已授权 Turn。

获得授权的 Turn 成功完成且回复验证通过后，已使用的上下文材料通过现有的、
绑定事件的 material-review ledger 结算。重复投递与重启恢复保持幂等。机器人
自身消息、其他群聊、无效路由以及多重歧义的管家绑定继续安全关闭且不采集。

连接健康投影会区分 `context_only_captured` 与
`replied_and_acknowledged`。CLI/managed Turn、frontend 与 Lark 必须复用同一份
运行时 inbox 和 receipt 模型；适配器不得另造权限来源。
