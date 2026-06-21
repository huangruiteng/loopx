# Xiaohongshu / Launch Narrative Draft

## 首屏核心

**Always-on agent teams, governed by human judgment**

**Gate-aware human-in-the-loop control plane**

**让多个 agent 昼夜接力，把人的判断留在控制面。**

LoopX 把目标、用户决策、agent todo、认领关系、scope、safe fallback、run history 和 quota 放进同一层状态：该等人的地方明确等人，不该空等的安全侧路继续推进。

## Current Positioning

LoopX 的发布重点不是“又做了一个 agent 框架”，而是一个更小、更真实的产品问题：

> 当 Codex / Claude Code / Cursor 这类 agent runtime 已经足够强，下一步缺的是一层 human-in-the-loop 控制面：让人的多个 agent 可以昼夜接力，同时在等待人类判断时不空等、不越界，并且把每一次 fallback、验证和边界都留下证据。

这不是把 todo 写得更细。

更准确的产品价值是：人不再扮演调度器，agent 也不再在 gate 前呆等。控制面负责把目标、用户决策、fallback work、验证证据、quota 和公开边界组织成一个长期可运行的系统。

适合首发的角度：

- 面向已经高强度使用 AI coding 工具做真实项目的人；
- 强调长程任务里的 human gate、fallback work、run history、quota 和 public/private boundary；
- 用一个脱敏 good case 解释产品体验，而不是只讲架构；
- 不夸大成自动化平台，先讲“为什么 agent loop 需要控制面”。

## Title Options

1. AI Agent 最怕的不是不会干活，而是被一个确认卡住
2. 我给 Codex 做了一层 LoopX：让它等待人时也不空等
3. 长程任务里，Agent 需要的不是更长聊天，而是控制面
4. 开源 LoopX：让 AI Agent 的目标、证据和人类决策不再散落在聊天里
5. 我越来越确定：AI Coding 产品会从 prompt 竞争走向 control plane 竞争

## Draft

最近我在做一个小工具：`loopx`。

它不是新的 agent 框架，也不替代 Codex / Claude Code / Cursor。它解决的是另一个问题：当 agent 已经能长时间干活，人类不应该继续做手动调度器。

短任务里，agent 的上下文基本就是任务现场。

长程任务不一样。状态会散到代码、文档、benchmark、run artifact、用户反馈、权限边界和历史决策里。模型可以继续生成下一步，但人会被迫反复回答：

- 现在到底卡在哪里？
- 这个卡点需要我判断，还是 agent 可以自己修？
- 如果核心任务被 gate 住了，agent 能不能先推进别的安全工作？
- 这轮有没有越过私有材料、生产环境、公开 claim 或 leaderboard 边界？
- 下一轮 agent 怎么知道这次 fallback 只是 fallback，而不是新的主线？

LoopX 把这些问题抽成一层本地控制面：

```text
goal state
  + user / agent todos
  + operator gate
  + run history
  + quota / spend
  + public-private boundary
        |
        v
Codex / Claude Code / Cursor / benchmark runner
```

一个最有代表性的 case 是 benchmark rotation。

当时 agent 在交替推进 Terminal-Bench、SkillsBench 和 ALE 三类 benchmark。ALE 新增了本地 Docker 路线，但首次执行前需要获取一个很大的本地镜像，这显然应该由用户判断是否安排。

很多 agent 产品在这里会停住：等用户点选项，或者反复提醒“需要确认”。

LoopX 的做法是：

1. 把 ALE 大镜像获取写成具体 user todo；
2. 说明这是核心 lane 的 gate，不消耗 delivery quota；
3. 保持 ALE 为 source/runner-ready but image-blocked；
4. 自动退回到 Terminal-Bench / SkillsBench 的安全 no-upload 轮转；
5. 在 run history 里记录这次是 blocked-priority fallback，不把 fallback 误当主线。

这个体验看起来只是一个细节，但我认为它是长程 agent 产品很关键的分水岭。

用户看到的是：

- 哪个核心问题需要自己判断；
- agent 为什么还能继续干别的；
- 继续干的事情是否仍符合最新方向；
- 这轮有没有花 quota、有没有越界、有没有可复核证据。

这比“agent 很勤奋”更重要。

真正有价值的长程自动化，不是每隔几分钟催一次模型，也不是把上下文窗口拉长。

它应该知道什么时候继续，什么时候闭嘴，什么时候把人的决策显式投影出来，什么时候把安全 fallback 暴露成 fallback。

这也是我现在对 LoopX 的定位：

- Prompt engineering 解决“怎么说”；
- Context engineering 解决“给模型看什么”；
- LoopX 解决“这个 agent 如何在受控边界里长期行动、被观察、被评估、被接手”。

仓库：`github.com/huangruiteng/loopx`

如果你也在用 AI coding 工具做长期项目，我更想知道：你现在最大的痛点是模型不够强，还是目标、状态、验证和交接不够稳？

## Image Ideas

1. Control-plane screenshot: a high-priority user gate plus safe fallback work in the same heartbeat.
2. Simple diagram: `human gate -> fallback lane -> run history -> next heartbeat`.
3. Terminal screenshot: `quota should-run` returning action-required false for fallback, while preserving blocked gate metadata.
4. Public/private boundary checklist before publishing a benchmark or case note.

## Follow-Up Post Ideas

- 为什么长程任务不是聊天变长，而是状态变复杂。
- AI agent 产品下一阶段：从 prompt / context 到 control plane。
- Human-in-the-loop 不是“每次都问人”，而是把人类判断变成可继承的控制面信号。
- 一个 good case 如何沉淀成 run history、case analysis 和产品改进。
- 为什么 LoopX 不是 agent framework，而是 agent loop 的 backstage control plane。
