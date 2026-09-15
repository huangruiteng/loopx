# Terminal-Bench 4.0：codex × LoopX 评测

裸 `codex`、codex 原生 `goal`、以及 LoopX 三种续跑模式（`ssh-goal` / `codex-cli` / `heartbeat`）
在 **Terminal-Bench 4.0**（harbor-framework，tag `v4.0.0`）52 个 matched 任务上的对照。
模型 `GPT-5.6 Sol`，思考深度统一 **`xhigh`**；agent 预算压至任务时限的 ~30%
（`agent_timeout_multiplier=0.3`）；共 260 trial（52×5，每格 1）。
目标是在终端长程领域产出可复算的一手对照，为"无人自动化默认姿势"提供评测证据。

> **性质**：单次、每格 1 trial、多机制同变的**探索性观察**。TB4 为二值 reward，
> 故解出率 ≡ Mean Reward、Solve@1.0 ≡ 解出任务数。数值为描述性统计，机制陈述为假设，
> 需重复的匹配实验方能证实。
>
> **数据边界**：仅发布运行/评分代码与 public-safe 聚合结论。逐 trial 原始轨迹按
> LoopX benchmark 契约保留私有。

## 1. 模式

| 模式 | 归属 | 说明 |
|---|---|---|
| `plain` | baseline① | 裸 codex（goals off），objective 固定；走 app-server 通道 |
| `goal` | baseline② | codex 原生 Goal（app-server），无 LoopX |
| `ssh-goal` | LoopX | Codex App over SSH，visible Goal 续跑 |
| `codex-cli` | LoopX | Codex CLI 可见 `/goal` 续跑 |
| `heartbeat` | LoopX | 心跳模式，外部 driver 拥有唤醒 |

两组对照锚点：`plain→goal` 衡量 codex 原生 goal 的价值；`goal→{ssh-goal, codex-cli, heartbeat}`
衡量 LoopX 三种续跑机制各自的增量。五臂的模型、effort、工具面、沙箱、容器完全一致，**唯一变量是 harness**；
三个 LoopX 臂共用同一个 agent 类，靠运行编排传入的模式开关区分。

## 2. 评分口径

- TB4 是 harbor 通用的**二值 reward**（不写 `partial_score`），主指标即解出率（`Solve@1.0`）。
  另可从 verifier 的 pytest 报告（`ctrf.json`）派生一个细粒度**测试通过率** `passed / tests`
  作为辅助口径——它比二值更能反映"做到几成"，但 TB4 测试多为全或无门禁，故仅作参考、非官方分。
  注意：52 题里有 **5 个是非 pytest verifier**（`cumulative-layout-shift` / `heat-pump-warranty` /
  `ks-solver-cpp` / `legacy-utility-triage` / `music-harmony`，用自定义校验脚本，只落二值 reward、不写
  `ctrf.json`），这些题**没有逐测试明细**，`test_pass_rate` 恒为 `null`（数据不存在，与 reward 是否为 1 无关），
  且不计入 partial 分母。
- 分母统一取 **52 个 matched 任务**：全部 55 个跑过 `xhigh` 的任务，减去环境不可解的
  `freecad×3`（verifier 镜像 vtk 构建冲突）与 `risk-scorer-replay`。无单臂剔除，五臂共用同一分母。
- 每个 (task,arm) 的轨迹由 `scoring/verdict.py` 判 `OK / RETRY / RESOURCE / PENDING`：
  跑满预算正常收尾计 OK；`serverOverloaded`/断流风暴/空跑判 RETRY 重跑；账号/环境不可解判 RESOURCE。
  **区分"瞬时基础设施失败"与"任务难 / 预算紧导致 reward=0"，是本对照可信度的关键**——只有前者重跑，
  后者作为观测结果计入。

## 3. 结果（52 个 matched 任务）

主指标是二值 `Solve@1.0`（TB4 官方口径）；另附从 pytest 报告派生的细粒度**测试通过率**
`partial`（`ctrf.json` 的 `passed / tests`，分母为 5 臂都产出 pytest 报告的 42 题 matched 子集）。
其余 10 题因非 pytest verifier 或该臂缺 xhigh 明细而无逐测试数据（`cells` 里记 `test_pass_rate=null`，
表示数据不存在、不等于 0），不计入 partial 分母。

| 模式 | 归属 | Solve@1.0 | Mean Reward | 测试通过率 partial (n=42) |
|---|---|---:|---:|---:|
| `plain` | baseline（裸 codex，goals off） | **9 / 52** | **0.173** | 0.633 |
| `ssh-goal` | LoopX · Codex App over SSH | 4 / 52 | 0.077 | **0.718** |
| `codex-cli` | LoopX · Codex CLI 可见 /goal | 4 / 52 | 0.077 | 0.640 |
| `heartbeat` | LoopX · 心跳唤醒 | 3 / 52 | 0.058 | 0.668 |
| `goal` | baseline · codex 原生 /goal | 2 / 52 | 0.038 | 0.594 |

> **两种口径排序不同**：二值下 `plain` 第一；细粒度测试通过率下**续跑臂 `ssh-goal`(0.718) / `heartbeat`(0.668)
> 反超 `plain`(0.633)**。即续跑臂在更多题上"更接近通过"（过的测试更多）却没跨过完全通过线；plain 完全解出的题多、
> 但其余题上的测试通过率并不占优。caveat：TB4 测试多为全或无门禁，测试通过率是派生代理、非官方按比例分。

## 4. 观察（描述性；机制为假设）

1. **统一 effort 后 plain 领先**：解出 9，约为次高（ssh-goal / codex-cli 各 4）的 2×+。挂 Goal 的三臂
   （goal / ssh-goal / heartbeat）互有高低但都不高于 plain；`codex-cli` 与 `ssh-goal` 并列次高。
2. **plain 的领先主要靠解集广度**：plain 在 5 题上是唯一解出的臂
   （html-js-filter / heat-pump-warranty / intrastat-meldung / vf2-speedup-networkx / atrx-vep-crispr），
   而这些题其余四臂都跑出结果拿 0（不是没机会）。裸 turn 在 TB4 这批"一次成型"题上并不吃亏。
3. **续跑臂各有独占解**：`ssh-goal` 独解 `embedding-drift-monitor`，`goal` 独解 `wdm-design`，
   `codex-cli` 独解 `interleaved-vigenere` 与 `sound-change-cascade`。各臂解集互有出入、非包含关系，
   说明续跑机制并非纯粹开销。

4. TB4 是"任务不长但容易踩坑"型题目，Goal 模式常因早退而失败：这批任务的时限本就不长，胜负多取决于是否踩中隐藏边界/陷阱，而非能否长程坚持。原生 goal（app-server）在这种形态下常自判"已完成"提前收工——objective 只是"完成任务并提交"、任务细节在 task 文件与 Todo 里，Goal 路径容易在可见测试一过就宣告 done、在触到隐藏陷阱前早退，从而拿 0。这与 goal 解出最少（2）、且它解出的题 plain 也大多解出一致。外部门控的 heartbeat / codex-cli 靠 Todo + 交付校验续跑，能压住早退，但在这批"一次成型"题上净增益有限（假设，非因果证明）。
5. **细粒度看，续跑臂在"接近通过"上反超 plain**：二值 Solve@1.0 只记完全通过，而测试通过率 partial 上
   `ssh-goal`(0.718) / `heartbeat`(0.668) 高于 `plain`(0.633)（§3）。这说明续跑并非无效——它在更多题上多过了一批
   测试、把工作推得更远，只是没跨过 TB4 全或无门禁的最后一档。二值口径会完全抹掉这段进度差异，
   两种口径合看才不至于把"续跑有推进但没解出"误读成"续跑没用"。

## 5. 逐任务矩阵（被 ≥1 臂解出的 14 个任务，其余 38 个五臂全 0）

| 任务 | plain | goal | ssh-goal | codex-cli | heartbeat |
|---|:--:|:--:|:--:|:--:|:--:|
| atrx-vep-crispr | ✅ | 0 | 0 | ✅ | 0 |
| biped-contact-dynamics | ✅ | 0 | ✅ | ✅ | ✅ |
| cumulative-layout-shift | ✅ | ✅ | ✅ | 0 | ✅ |
| embedding-drift-monitor | 0 | 0 | ✅ | 0 | 0 |
| heat-pump-warranty | ✅ | 0 | 0 | 0 | 0 |
| html-js-filter | ✅ | 0 | 0 | 0 | 0 |
| interleaved-vigenere | 0 | 0 | 0 | ✅ | 0 |
| intrastat-meldung | ✅ | 0 | 0 | 0 | 0 |
| mp-checkpoint-consolidation | 0 | 0 | ✅ | 0 | ✅ |
| pretrain-shard-corruption | ✅ | 0 | 0 | 0 | 0 |
| retro-console-soc | ✅ | 0 | 0 | 0 | 0 |
| sound-change-cascade | 0 | 0 | 0 | ✅ | 0 |
| vf2-speedup-networkx | ✅ | 0 | 0 | 0 | 0 |
| wdm-design | 0 | ✅ | 0 | 0 | 0 |
| **合计** | **9** | **2** | **4** | **4** | **3** |

> plain 独占 7 题，是解集扩张的主要来源；`biped-contact-dynamics` 被 4 臂解出、
> `cumulative-layout-shift` 被 4 臂解出，是共识较高的题。

### goal 家族为什么没在二值口径上超过 plain

在 **plain 解出的 9 个任务**上，逐 (task,arm) 看各 goal 家族臂的续跑轮数、墙钟与测试通过率
（数据源为 verifier 的 pytest 报告与 harbor 计时，聚合为下表；逐 trial 明细与原始轨迹按 LoopX 契约私有、不随本目录发布）：

| 臂 | 也解出 | 平均续跑轮 | 平均墙钟 | 平均测试通过率 |
|---|---:|---:|---:|---:|
| `goal` | 1/9 | 0.0 | 1744s | 0.638 |
| `codex-cli` | 0/9 | 0.1 | 1108s | 0.619 |
| `ssh-goal` | 2/9 | 1.7 | 2957s | 0.679 |
| `heartbeat` | 2/9 | 1.4 | 3777s | 0.760 |
| `plain`（基准） | — | — | 2165s | — |

两种失败模式：

- **不续跑、早退（`goal` / `codex-cli`）**：平均续跑轮≈0、墙钟明显短于 plain。原生 `goal` 在可见测试一过附近就自判"完成"收工；`codex-cli` 的 guard 为人值守 TUI 设计（不带 `--begin-turn`），无人自动化下同样醒不过来。结果是测试只过一部分（0.62~0.64）就停，在触到隐藏陷阱前早退。
- **续跑但被全或无门禁挡住（`ssh-goal` / `heartbeat`）**：真的续跑（1.4~1.7 轮）、墙钟比 plain 还长、测试通过率也最高（0.68~0.76），把工作推得更远，只是没跨过 TB4"全通过才算数"的最后一档，故二值 Solve@1.0 仍未超过 plain。

续跑并非无用：`ssh-goal` 独解 `embedding-drift-monitor`、`ssh-goal`+`heartbeat` 独解 `mp-checkpoint-consolidation`、`codex-cli` 独解 `interleaved-vigenere`——这些是 plain/goal 都拿不到的"需坚持"题。两族解集互有出入、非包含关系：plain 靠一次成型题的广度取胜，续跑臂在需要跨 turn 坚持的题上净赢。

## 6. LoopX 使用真实性

- harness 层（模式开关选模式 + goal body 注入 + 续跑再唤醒）：三个 LoopX 臂 52/52 生效。
- 破自锁开关 `LOOPX_UNGATED=1` 在所有 LoopX 臂上启用：body 规定第三次相同阻塞轮就
  `update_goal status=blocked`，而 benchmark 里没有 user `/goal resume` 能复活它，不开就测成自锁而非 harness 能力。
- 续跑真实性逐轨迹可核：`verdict.py` 从 `goal_receipt.json` 读 `continuation_turn_completed_count`
  与 `error_event_count`；`mp-checkpoint-consolidation` 等题的续跑臂轨迹含多轮 continuation。
- 逐臂"agent 自调 `loopx` CLI 次数"的精确审计仍属私有轨迹范畴，本版不公开单臂计数。

## 7. 机制观察（假设）

保留 `mp-checkpoint-consolidation` 个案：仅续跑臂（`ssh-goal` / `heartbeat`）解出，`plain` / `goal` 均 0。
该个案与"需坚持"题续跑净赢一致——外部续跑能跨过单 turn 预算边界继续推进。但这是单点观察，不构成因果证明。

另一侧，plain 在 TB4 这批"一次成型"题上反而不被 Goal 的规划 / 续跑开销拖累。因此本版的
"plain 领先"应读作**任务分布**下的描述性结果，而非"续跑无用"的结论——
二者在不同题上各有胜负（§4.3、§5）。effort 一旦作为变量混入，排序就会改变（见顶部更正），
这正是本版把 effort 钉死为 `xhigh` 的原因。

## 8. 代码结构

本目录只发布 TB4 特有的 public-safe 产物；五臂 harness、skill 与 LoopX runtime **单一 owner 复用** SWE-Marathon 对照，不在此重复：

```
scoring/   评分/报告：verdict.py（轨迹判定）+ xhigh_report.py / xhigh_matrix.py（出计数与矩阵）+ check_rerun.py
data.json  pinned public-safe 聚合产物（与 §3/§5 结论对应，二值 reward；本目录唯一可被公众重算的产物）
```

复用的共享组件（唯一 owner 在 SWE-Marathon 侧，避免同一 harness 出现两份行为）：

- Harbor 适配器：[`../swe-marathon/agents`](../swe-marathon/agents)（五臂共用；三个 LoopX 臂共用 `codex_loopx_agent`，由运行编排的模式开关区分。TB4 用到的 `-u root` / 反查任务用户 / `tempfile` 等修复已回灌至此共享 owner）
- 五臂 benchmark skill：[`../swe-marathon/skills/tb4-five-arm/SKILL.md`](../swe-marathon/skills/tb4-five-arm/SKILL.md)（五臂定义、运行协议、已知坑）
- LoopX runtime（模式框架 `modes/` + turn 驱动 `turn/`）：[`../swe-marathon/runtime`](../swe-marathon/runtime)

原生 Goal 状态机以 `loopx.capabilities.benchmark_toolkit.native_codex_goal` 为唯一 owner（不再 vendored 复制）。依赖该 toolkit 与 harbor。运行编排（网关 / 代理 / 端口 / 任务集接线）属实验环境专有，**不随本仓库分发**。

## 9. 复现与血缘

公众可复算路径只到 `data.json`（下方第一段命令，无需 raw、无需私有 harness）；从原始结果树重算需要私有数据与实验环境编排（网关/代理/任务集接线不在本仓库），故仅供参考。

```bash
# 从 pinned 聚合直接重算表格（public-safe，无需 raw）
python3 - <<'PY'
import json; d=json.load(open("data.json"))
for a in d["arms"]:
    s=d["arm_summary"][a]; print(f'{a:10s} Solve@1.0={s["solved"]}/{s["n"]}  mean_reward={s["mean_reward"]}')
PY

# 从原始结果树重算（需私有数据 + 实验环境编排，不在本仓库）：逐 stamp 取 xhigh + 判 reward
export TB4_OUT=/path/to/results-tree        # <task>/<arm>/<ts>/ 结构的结果树（私有）
export TB4_ROWS=/path/to/xhigh_rows.json    # xhigh_report.py 落盘、xhigh_matrix.py 读取的中间文件
python3 scoring/xhigh_report.py             # 出各臂计数
python3 scoring/xhigh_matrix.py             # 出 matched 解出矩阵
```

原始结果树按 LoopX 契约保留私有，本目录不内嵌任何网络拓扑或凭证；`data.json` 是唯一发布的聚合产物。

**血缘 / 版本**：

| 组件 | 版本 |
|---|---|
| model | `GPT-5.6 Sol`（reasoning effort **`xhigh`（统一）**） |
| Codex | `0.151.0` |
| harness (harbor) | `0.20.0` |
| benchmark / verifier | Terminal-Bench 4.0，tag `v4.0.0`（`452bf305c6`；本地 vendor 固定 tag 复现，二值 reward） |
| 预算 | `agent_timeout_multiplier=0.3`（~30%）；`GOAL_TIMEOUT_SEC=5340` |
| 网络 | public（TB4 上游标定；66 个 task.toml 均未声明 network_mode，harbor 默认 public） |
| 分母 | 52 任务（55 个跑过 `xhigh` − freecad×3 − risk-scorer-replay） |
| 规模 | 260 trial（52 任务 × 5 模式，每格 1） |

原始完整结果树按 LoopX 契约**私有**，不随本版删除或公开。本 PR 为 exploratory research contribution；
portable harness、与 SWE-Marathon 共享的 adapter / runtime / benchmark-toolkit 的收敛，按维护者约定作为后续 follow-up。
