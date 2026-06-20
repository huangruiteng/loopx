# Goal Harness

**Always-on agent teams, governed by human judgment**

**Gate-aware human-in-the-loop control plane**

**让多个 agent 昼夜接力，把人的判断留在控制面。**

Goal Harness 把目标、用户决策、agent todo、认领关系、scope、safe fallback、
run history 和 quota 放进同一层状态：该等人的地方明确等人，不该空等的
安全侧路继续推进。

Goal Harness 是一个面向长期 agent 工作的本地控制面。它让 Codex、Claude Code、
Cursor、automation 和旁路 agent 共享同一份长期目标状态：目标、gate、todo、
认领、scope、运行历史、quota、证据和项目边界在多轮工作中保持可见、可恢复、
可交接。

[English](README.md) · [快速开始](#快速开始) · [Showcases](docs/showcases/README.md) ·
[用户群与反馈](#用户群与反馈) · [产品愿景](docs/product/vision.md) · [架构](docs/architecture.md)

## 它是什么

Goal Harness 不是另一个 agent runtime，也不是要替代 Codex、Claude Code、
Cursor 或其他终端 agent。更准确地说：

| 层次 | 负责什么 |
| --- | --- |
| Codex / Claude Code / Cursor | 执行单次或连续 agent loop，写代码、读文件、运行命令、回复用户 |
| Codex goal / automation / CLI 脚本 | 触发或调度 agent loop，让 agent 在某个入口继续工作 |
| Goal Harness | 维护长期目标的控制面：当前目标、用户决策、agent todo、run history、quota、证据、边界和交接 |

一句话：Goal Harness 不是 Codex goal 的替代品，而是让 Codex goal、automation
和外部脚本触发的 agent loop 都能共享同一份长期状态。

## 为什么需要

短任务失败，常常是因为模型某一步做错了。长期任务失败，更常见的原因是
state drift：

- 用户已经做过的决策散落在聊天里，后续 agent 不知道；
- P0 卡在 user gate 上，agent 只会空等，或者绕过人类决策继续乱跑；
- 多个 agent 同时工作，却看不到彼此认领了哪些 todo；
- 上一轮到底做了什么、怎么验证的、为什么没继续，难以复盘；
- public/private 边界、benchmark no-upload 边界、生产权限边界没有被稳定投影；
- 人类反馈没有沉淀成下一轮 agent 能读懂的控制面信号。

Goal Harness 的产品判断是：强能力 agent-loop 已经存在，问题在于如何把它变成
长期可用、可控、可解释的协作系统。

换句话说，Goal Harness 想让人的多个 agent 可以持续接力，包括夜间和用户离开
后的安全工作；但接力的前提不是绕过人，而是把人类判断、scope、能力门、quota
和证据写成下一轮 agent 也能读懂的控制面。

## 它如何工作

```mermaid
flowchart LR
  U["用户判断 / gate / feedback"] --> GH["Goal Harness state"]
  P["主控 agent"] --> GH
  S["旁路 agent"] --> GH
  GH --> T["User todo / Agent todo"]
  GH --> H["Run history / evidence"]
  GH --> Q["Quota guard"]
  T --> A["下一步 bounded action"]
  Q --> A
  A --> GH
```

核心对象：

- **Lifetime goal**：能跨越单个聊天、单个 agent run、单个 todo 的长期目标。
- **User gate**：需要人类判断的位置，明确停下并把问题投影出来。
- **Safe fallback**：不依赖该 gate 的安全侧路，允许继续推进并留下证据。
- **Todo ownership**：agent 通过 `claimed_by` 认领 todo，减少并发冲突。
- **Quota guard**：每次自动 heartbeat 前判断是否应该运行、等待、通知或自修复。
- **Run history**：把每轮进展、验证、blocker、reward、quota spend 记录成紧凑历史。

## 看几个例子

| Case | 说明 | 入口 |
| --- | --- | --- |
| Blocked P0 with safe P1/P2 rotation | P0 被用户决策卡住，但 P1/P2 安全侧路继续推进，且 gate 不丢失。 | [0617 case](docs/showcases/cases/0617-blocked-p0-safe-rotation.md) |
| Goal Harness self-iteration loop | 主控聚焦 benchmark，旁路 agent 在独立 scope 里改进控制面、文档和自合并机制。 | [0619 self-iteration](docs/showcases/cases/0619-goal-harness-self-iteration.md) |
| Dynamic workflow for hardware-agent development | 模糊、多 agent、跨阶段工程协作如何收敛到同一控制面。 | [0619 redacted stub](docs/showcases/cases/0619-dynamic-workflow-hardware-agent.md) |

完整案例目录见 [docs/showcases/README.md](docs/showcases/README.md)。案例默认只保留
public-safe 信息，不提交内部截图、私有链接、raw benchmark 日志或本地状态。

## 适合什么场景

Goal Harness 适合长期、多人、多 agent 或带边界的工作：

- 多天或多周的工程、研究、benchmark、实验推进；
- Codex / Claude Code / Cursor 的 recurring heartbeat 或 monitor-style 工作；
- 需要等待 CI、benchmark、外部 owner、用户判断的项目；
- 一个主控 agent 加多个旁路 agent 的协作；
- 需要把“agent 做了什么、卡在哪、下一步是什么”翻译给非技术用户的产品；
- 发布公开材料前需要持续检查 public/private 边界的项目。

它不适合直接作为生产自动化控制器。危险权限、生产操作、私有材料公开、发布
动作仍然应该由人类或宿主项目明确授权。

## 快速开始

如果你已经在用 Codex、Claude Code、Cursor 或其他终端 agent，最快的方式是把
下面这段交给 agent，让它在当前项目里安装并连接 Goal Harness：

```text
请为这个项目端到端安装并连接 Goal Harness，不要只给计划。

如果 `goal-harness` 不在 PATH：
- 如果 ~/goal-harness 不存在，clone https://github.com/huangruiteng/goal-harness 到 ~/goal-harness；
- 运行 ~/goal-harness/scripts/install-local.sh；
- export PATH="$HOME/.local/bin:$PATH"。

然后：
1. 运行 `goal-harness doctor`。
2. 根据当前 repo 名选择稳定 goal id，除非我显式给了 goal id。
3. 读取项目目标文档（如 GOAL.md、README.md，或我指定的文档）；若没有，就问我要一句目标。
4. 运行 `goal-harness connect` 或 `goal-harness bootstrap`。
5. 读取 connect 输出里的 onboarding candidates，向我解释候选 agent todo，并问我接受、修改还是拒绝。
6. 把 `.goal-harness/` 和 `.codex/goals/` 加入当前项目 `.gitignore`。
7. 运行 `goal-harness registry`、`goal-harness status`、`goal-harness check --scan-root .`。
8. 汇报 goal id、创建文件、当前 user todo、当前 agent todo 和下一步安全动作。

不要提交 `.goal-harness/`、`.codex/goals/`、ACTIVE_GOAL_STATE、本地 registry、
raw logs、credentials 或私有本地路径。
```

也可以手动安装：

```bash
git clone https://github.com/huangruiteng/goal-harness ~/goal-harness
~/goal-harness/scripts/install-local.sh
goal-harness doctor
```

连接一个项目：

```bash
cd /path/to/your-project
goal-harness bootstrap \
  --goal-id your-project-goal \
  --objective "Improve this project through bounded, verified goal segments." \
  --goal-doc GOAL.md
```

诊断当前状态：

```bash
goal-harness diagnose
goal-harness status
goal-harness quota should-run --goal-id your-project-goal
```

## 用户群与反馈

Goal Harness 还在早期，最需要真实长期 agent 任务里的反馈：控制面帮到了哪里、
哪里太重、哪些 user gate / handoff / scope 仍然不够清楚。

- 可复现 bug、安装问题、功能建议：请优先提
  [GitHub Issue](https://github.com/huangruiteng/goal-harness/issues)。
- 文档修正、showcase 补充、小型 public-safe 示例：欢迎直接开 PR。
- 想快速交流、试用 onboarding、一起打磨 showcase：欢迎优先加入飞书用户群；
  微信群作为备用入口，二维码可能过期，失效时请先走飞书或提 Issue 提醒更新。

<table>
  <tr>
    <td align="center" width="240">
      <img src="docs/assets/goal-harness-lark-user-group.png" alt="Goal Harness 飞书用户群二维码" width="200"><br>
      飞书用户群
    </td>
    <td align="center" width="240">
      <img src="docs/assets/goal-harness-wechat-user-group.png" alt="Goal Harness 微信用户群二维码" width="200"><br>
      微信用户群，可能过期
    </td>
  </tr>
</table>

## 产品化方向

当前仓库从 coding、research 和 benchmark loop 开始，因为这些场景最容易暴露
长期 agent 工作的控制面问题。中期产品化方向会继续把 Goal Harness 推到更广的
用户场景，例如创作者/自媒体运营：

- agent 长期探测社交平台热点；
- 根据个人创作偏好形成热点地图；
- 提取 insight，辅助文章、脚本、视频选题；
- 沉淀个人素材库和语料库；
- 用友好的首屏告诉非技术用户：做了什么、正在做什么、卡在哪里、下一步是什么。

这个方向的核心不是炫耀模型能力，而是把 agent 活动转成用户能理解、能反馈、
能约束的产品对象。见 [docs/product/vision.md](docs/product/vision.md)。

## 贡献

公开、可认领的任务见 [CONTRIBUTOR_TASKS.md](CONTRIBUTOR_TASKS.md)。贡献前请读
[CONTRIBUTING.md](CONTRIBUTING.md)，尤其是 public/private 边界、smoke 保留规则和
benchmark 证据边界。

默认不要提交：

- `.goal-harness/`、`.codex/goals/`、live `ACTIVE_GOAL_STATE.md`；
- 内部文档链接、聊天截图、raw benchmark task/log/trajectory/verifier output；
- credentials、tokens、私有本地路径或生产 task id；
- 未脱敏的用户、团队、客户、项目名称。

可以提交：

- public-safe docs、case cards、synthetic demos；
- 稳定 CLI/runtime 行为的 focused smoke；
- 控制面协议、架构说明、贡献者任务；
- 明确标注 evidence boundary 的展示材料。
