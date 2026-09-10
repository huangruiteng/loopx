# SWE-Marathon：codex × LoopX 评测

> [打开双语可视化研究简报](https://huangruiteng.github.io/loopx/benchmarks/swe-marathon/)：以高信息密度方式呈现实验 setting、结果、轨迹机制、证据边界与下一轮实验建议。

裸 `codex`、codex 原生 `goal`、以及 LoopX Turn（外部调度 heartbeat）在 SWE-Marathon v1.1（Harbor）15 个任务上的对照。
模型 `GPT-5.6 Sol`，思考深度 `high`；agent 预算压至任务时限的 ~30%（`agent_timeout_multiplier=0.3`）；共 45 trial（15×3，每格 1）。
目标是在长程领域产出可复算的一手对照，为"无人自动化默认姿势"提供评测证据。

> **性质**：单次、每格 1 trial、多机制同变的**探索性观察**。数值为描述性统计，机制陈述为假设，需重复的匹配实验方能证实。
>
> **更正**：SSH Goal 与 Codex CLI 两组的数据及结论已撤回，等待重新验证。撤回覆盖这两组的全部任务，不按分数选择样本，也不据此判断两种模式的能力。此前依赖多组的 14/14 行为结论与统计图不再保留。原始记录不删除。
>
> **数据边界**：仅发布 public-safe 聚合（`data.json`）。逐 trial 原始轨迹按 LoopX benchmark 契约保留私有。

## 1. 模式

| 模式 | 归属 | 说明 |
|---|---|---|
| `plain` | baseline① | 裸 codex，objective 固定 `"Finish the task."` |
| `goal` | baseline② | codex 原生 goal（非 LoopX），注入干净 goal |
| `heartbeat` | LoopX | 外部调度器驱动的续跑/解锁（automation） |

两条对照锚点：`plain→goal` 衡量 codex 原生 goal 的价值；`goal→heartbeat` 衡量 LoopX 的增量。

## 2. 评分口径

- `reward` 为二值，紧预算下几乎全 0；主指标用任务连续分 `partial_score`。
- 构建失败（partial 被门禁归零）作为观测结果计入，所有模式共用同一 15 任务 matched 分母（无单臂剔除），另列标注。

## 3. 结果（15 个 matched 任务）

| 模式 | reward | partial | 花费 | 自收工 | 续跑 | 解锁 | 构建失败 |
|---|---:|---:|---:|---:|---:|---:|---:|
| plain | 0.267 | 0.710 | $368 | 0/15 | 0 | 0 | 0/15 |
| goal | 0.267 | 0.767 | $533 | 12/15 | 7 | 0 | 0/15 |
| heartbeat | 0.333 | 0.778 | $830 | 13/15 | 42 | 8 | 0/15 |

## 4. 观察（描述性；机制为假设）

1. `plain→goal`：partial 0.710→0.767、自收工 0/15→12/15。紧预算下"主动收尾"这一行为差异，本次数据中主要与 codex 原生 goal 同现。
2. `heartbeat` 相对 `goal` 的连续分增量为 +0.011；reward 从 0.267 上升到 0.333（多完成 1/15 个任务），成本从 $533 增至 $830。每格仅一次运行，尚不能确认稳定收益或成本优势。

## 5. 逐任务矩阵（reward | partial）

| 任务 | plain | goal | heartbeat |
|---|---|---|---|
| find-network-alignments | 0/0.00 | 0/0.88 | 0/0.86 |
| zstd-decoder | 0/0.72 | 0/0.86 | 1/1.00 |
| kubernetes-rust-rewrite | 0/1.00 | 1/1.00 | 1/1.00 |
| ruby-rust-port | 1/1.00 | 0/0.98 | 0/0.98 |
| stripe-clone | 1/1.00 | 1/1.00 | 1/1.00 |
| vliw-kernel-optimization | 1/1.00 | 1/1.00 | 1/1.00 |
| wasm-simd | 1/1.00 | 1/1.00 | 1/1.00 |
| biofabric-rust-rewrite | 0/0.98 | 0/0.96 | 0/0.97 |
| nextjs-vite-rewrite | 0/0.99 | 0/0.99 | 0/0.99 |
| rust-c-compiler | 0/0.98 | 0/0.97 | 0/0.98 |
| excel-clone | 0/0.49 | 0/0.50 | 0/0.50 |
| s3-clone | 0/0.50 | 0/0.46 | 0/0.46 |
| slack-clone | 0/0.50 | 0/0.50 | 0/0.50 |
| mastodon-clone | 0/0.50 | 0/0.41 | 0/0.44 |
| rust-java-lsp | 0/0.00 | 0/0.00 | 0/0.00 |

## 6. LoopX 使用真实性

- harness 层（goal body 注入 + 续跑再唤醒）：heartbeat 15/15。
- agent 自调 `loopx` CLI：heartbeat 4/15；轨迹中多数 "loopx" 为读 `SKILL.md`。

## 7. 机制观察（假设）

保留的 zstd-decoder 个案中，plain 在可见 fixture 通过后停止，heartbeat 继续协议验收和内存安全检查，最终 partial 分别为 0.72 与 1.00。该个案与“继续验证能覆盖可见测试之外的边界”一致，不构成因果证明或所有模式的最佳实践。

同时保留 excel-clone/heartbeat 的未完成记录（partial=0.5、续跑 9 次、解锁 8 次）；更多续跑并不保证完成。此前关于 SSH Goal、Codex CLI 的行为比较、transport/host 错配和 prompt 干扰归因均已撤回。

## 8. 代码结构

```
agents/    Harbor 适配器（LoopX treatment + codex 原生 goal baseline）
scoring/   评分/聚合/可视化（口径见 _common.py）
skills/    历史五模式 benchmark skill（不代表当前公开证据范围）
runtime/   模式框架 + turn 驱动，含 automation 唤醒循环 loopx_turn_runner.py（见 runtime/RUNTIME.md）
data.json  pinned public-safe 聚合产物
case_insights.json  非官方 draft case-insight 记录（scoring/case_insights.py 由 data.json 生成）
```

依赖 `loopx.capabilities.benchmark_toolkit` 与 harbor；内部网络拓扑与凭证未内嵌。

## 9. 复现与血缘

```bash
# 从 pinned 聚合直接重算表格（public-safe，无需 raw）
python3 - <<'PY'
import json; d=json.load(open("data.json"))
for a in d["arms"]:
    s=d["arm_summary"][a]; print(a,"partial=%.3f reward=%.3f cost=$%.0f self=%d/%d"%(
        s["partial"],s["reward"],s["cost"],s["self_complete"],s["n"]))
PY

# 从原始结果树重算 data.json（需私有数据 + harness）
python3 scoring/_aggregate.py <private_results_dir> data.json
# _compare.py 等历史五模式诊断仅用于私有复核，不作为本版公开结果。
```

**血缘 / 版本**：

| 组件 | 版本 |
|---|---|
| model | `GPT-5.6 Sol`（reasoning effort: `high`） |
| Codex | `0.151.0` |
| LoopX | `0.5.3`（repo `bd52b28a`） |
| harness (harbor) | `0.20.0` |
| benchmark / verifier | SWE-Marathon v1.1（Harbor 任务集；`partial_score` 由任务 verifier 写入 `/logs/verifier/metrics.json`） |
| 预算 | `agent_timeout_multiplier=0.3`（~30%） |
| 规模 | 45 trial（15 任务 × 3 个保留模式，每格 1） |

原始完整结果树按 LoopX 契约**私有**，不随本次更正删除或公开。公开聚合生成器只输出三个保留模式；运行适配器和私有采集仍支持历史模式。本 PR 为 exploratory research contribution；portable harness、统一 benchmark evidence、missing-score policy、重复 adapter 与 benchmark-toolkit 的收敛按维护者约定作为后续 follow-up。
