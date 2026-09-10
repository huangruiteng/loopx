# DeepSWE behavior discoveries / DeepSWE 行为发现

[Open the published standalone article](https://huangruiteng.github.io/loopx/benchmarks/deepswe/behavior-discovery/),
or [download this source file](index.html) and open it in a browser. CSS and the
scoped JSON downloads are inline; the page uses system fonts, needs no build or
network access, and includes no raw trajectories. GitHub may show HTML source;
download the raw file to view the article.

## Scope / 阅读范围

This is an exploratory behavior note, **not a full benchmark result release or
a population-level uplift claim**. The setting is DeepSeek V4 Flash, max reasoning,
with Codex through ARK API. The article separates observations from mechanism
hypotheses and keeps relevant counterexamples and limitations visible.

- The same frozen 113-task cohort contributes two bounded process views:
  per-task feature-pass rates are macro-averaged within each hint condition,
  and raw wall-clock is reported for each arm. Feature coverage describes how
  much of the public requirement was implemented; it is not task success.
- Selected case comparisons illustrate requirement retention, handling of failing
  probes, and validation that can overturn an implementation assumption.
- A post-hoc slice ranks tasks by the mean raw wall-clock across all four arms
  and uses the highest-duration quartile (29 tasks). Both compared arms receive
  SWE hint. This symmetric rule prevents one Base or Test arm from deciding
  cohort membership, but runtime is still a post-treatment observation rather
  than an independent measure of intrinsic task complexity.
- Duration comparisons are descriptive raw wall-clock, including successful and
  failed runs. Exact bug-adjusted time is separately labeled. Lower duration
  alone does not establish equal-quality acceleration or token savings.

本篇分享局部行为发现，不发布完整四臂成绩、全量成功率或排名。同一冻结 113 题
只公开两类有边界的过程视图：按单题 feature pass rate 等权汇总的需求覆盖，以及
各臂原始 wall-clock。Feature coverage 不等于任务成功。精选案例和事后长时切片
用于提出值得复验的机制假设，不能外推成总体结论；保留失败样本、选样偏差和
验证预期不独立等限制。

## Toolkit records

[findings.json](findings.json) contains four `benchmark_behavior_finding_v0`
records. Their evidence digests refer to producer-reviewed, unshared summaries;
they do not let a reader independently verify the original trajectories. No
manifest, run ledger, score dashboard, or raw evidence is required to consume
these records. The standalone page embeds the same findings plus its bounded
display data and report projection.

To reproduce the toolkit projection in a fresh local store, split the findings
into individual JSON objects and follow the
[behavior-finding workflow](../../../docs/reference/benchmark-behavior-findings.md#local-workflow).
Use `--record-kind behavior_finding`, `--benchmark-id deepswe`, and
`--study-id behavior-sharing-v2`. Then read the selected records:

```sh
loopx benchmark behavior-report --store findings.jsonl \
  --benchmark-id deepswe --study-id behavior-sharing-v2 --format json
```

The local upload provider does not publish or submit anything remotely. A
behavior report has `score_authority: false`; existing scored-study and exact-run
case-insight rules are unchanged.
