# LHTB five-arm GPT-5.6 Sol max study

This directory contains the public-safe aggregate used by the LoopX LHTB
research brief at `/benchmarks/lhtb/`.

The study compares 46 matched LHTB tasks across:

1. Plain Codex app-server.
2. Native Codex Goal.
3. LoopX SSH-Goal.
4. Legacy LoopX 0.5.3 Heartbeat over app-server.
5. LoopX 1.0.3 Heartbeat using `generic_cli` and a fresh `codex exec` per wake.

All arms use `openai/gpt-5.6-sol`, `reasoning_effort=max`, and disabled Codex
Web Search. `data.json` contains only aggregate rewards and disclosed runtime
metadata. It intentionally excludes raw trajectories, local filesystem paths,
gateway addresses, credentials, and verifier artifacts.

## Evidence boundary

- Each task-arm cell contributes one effective trial. This is not a
  repeated-seed estimate.
- The primary reading compares the 1.0.3 Heartbeat arm with Plain and Native
  Goal. Runtime and budget differences prevent a single-variable causal or
  equal-budget efficiency interpretation. SSH-Goal and Legacy Heartbeat are
  retained as historical context.
- The effective aggregates include designated replacement trials. Some New
  Heartbeat replacements used longer budgets.
- Historical cost is estimated from retained token telemetry. New Heartbeat
  cost is recorded runtime telemetry, so the page treats cost as descriptive.
- LHTB reward and the `>= 0.95` solved threshold remain benchmark-native.

The runnable current Heartbeat implementation lives in `benchmark/LHTB/`.

## Reading the baseline comparisons

The brief derives these comparisons from the 46 `tasks` rows in `data.json`,
without modifying the experiment data:

| LoopX 1.0.3 Heartbeat versus | Mean reward delta | Relative mean gain | Wins / ties / losses | Strict solves (LoopX / baseline) |
| --- | ---: | ---: | --- | --- |
| Plain | +0.0731 | +17.3% | 17 / 13 / 16 | 7 / 7 |
| Native Goal | +0.0473 | +10.6% | 23 / 13 / 10 | 7 / 4 |

Mean delta is the mean of per-task differences; relative gain divides that
unrounded delta by the baseline mean. Wins, ties and losses compare published
unrounded rewards strictly; equality is not statistical equivalence. Display
rounding is applied only afterwards. The historical `heartbeat_comparison`
summary is retained in the source archive but is not used for these comparisons.

The task matrix defaults to Plain, Native Goal and LoopX Heartbeat; readers can
expand both historical arms. Case scores come from the same task rows rather
than a separate editorial copy. The recorded scores support outcome comparisons;
reported recovery or regression cases are mechanism clues, not causal estimates.

## Exploratory task-type analysis

`task-groups.json` supplies an exhaustive, analyst-defined **post-hoc** partition
of these 46 tasks. It changes no rewards, arms, scoring or trial selection.
The brief computes group deltas and win/tie/loss counts from `data.json` using
the same reducer as its overall comparison. Selecting a group reveals its
complete membership in the task matrix; search and baseline filters intersect.

The nine headings resemble the upstream introduction, but upstream website,
README and task metadata do not supply one consistent task-to-category map.
This is **not an official category leaderboard**. Membership follows the main
deliverable: paper-method pipelines and inverse modeling; constraint puzzles;
staged professional matters; perception/reconstruction; physical simulation;
earth/energy tools; software/toolchain repair; games; or systems optimization,
performance and security. These boundaries overlap (e.g. a research task also
requires software); they describe tasks, not measured causes of success.

### Complete membership and outcomes

Δ = mean(task LoopX 1.0.3 Heartbeat reward − task baseline reward).
Every task has equal weight within its group. Counts are strict W/T/L on
unrounded values; rounded zero or a tiny win does not mean statistical equality
or meaningful superiority. These small, selected groups are descriptive.

| Group | n | Δ Plain; W/T/L | Δ Goal; W/T/L |
| --- | ---: | --- | --- |
| Research & modeling | 4 | +0.2802; 4/0/0 | +0.2179; 2/2/0 |
| Logic & spatial puzzles | 4 | +0.2739; 3/0/1 | +0.1374; 3/0/1 |
| APEX professional work | 4 | +0.1022; 3/1/0 | +0.0407; 3/0/1 |
| Multimodal analysis | 6 | -0.0034; 1/3/2 | +0.0058; 3/3/0 |
| Science & simulation | 7 | +0.0161; 2/2/3 | +0.0099; 3/2/2 |
| Earth, climate & energy | 6 | -0.0108; 2/2/2 | +0.0382; 3/2/1 |
| Software repair & toolchains | 6 | -0.0188; 0/4/2 | +0.0991; 2/3/1 |
| Games & strategy | 4 | -0.0112; 1/0/3 | +0.0971; 3/0/1 |
| Systems, performance & security | 5 | +0.1732; 1/1/3 | -0.1450; 1/1/3 |

Each link opens the pinned public task instructions used for structural reading:

- **Research & modeling:** [alp-paper-reproduction](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/alp-paper-reproduction/instruction.md), [foldseek-paper-reproduction](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/foldseek-paper-reproduction/instruction.md), [tabular-data-feature-covshift](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/tabular-data-feature-covshift/instruction.md), [unison-paper-reproduction](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/unison-paper-reproduction/instruction.md).
- **Logic & spatial puzzles:** [chess-mate](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/chess-mate/instruction.md), [rush-hour-campaign](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/rush_hour_campaign/instruction.md), [sokoban](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/sokoban/instruction.md), [sudoku-recovery](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/sudoku-recovery/instruction.md).
- **APEX professional work:** [apex-ib244-matter](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/apex-ib244-matter/instruction.md), [apex-investment-banking-matter](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/apex-investment-banking-matter/instruction.md), [apex-law433-matter](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/apex-law433-matter/instruction.md), [apex-management-consulting-matter](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/apex-management-consulting-matter/instruction.md).
- **Multimodal analysis:** [audio-visual-event-alignment](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/audio-visual-event-alignment/instruction.md), [dicom-radiology-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/dicom-radiology-audit/instruction.md), [document-table-layout-reconstruction](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/document-table-layout-reconstruction/instruction.md), [microscopy-cell-count-qc-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/microscopy-cell-count-qc-audit/instruction.md), [satellite-flood-change-detection-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/satellite-flood-change-detection-audit/instruction.md), [scientific-figure-data-reconstruction](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/scientific-figure-data-reconstruction/instruction.md).
- **Science & simulation:** [epidemic-inverse-control-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/epidemic-inverse-control-audit/instruction.md), [materials-phase-diagram-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/materials-phase-diagram-audit/instruction.md), [nbody-accel-iterative](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/nbody-accel-iterative/instruction.md), [opensees-seismic-structural-regression-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/opensees-seismic-structural-regression-audit/instruction.md), [robotics-slam-benchmark-repair](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/robotics-slam-benchmark-repair/instruction.md), [spice-ephemeris-regression](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/spice-ephemeris-regression/instruction.md), [su2-airfoil-regression](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/su2-airfoil-regression/instruction.md).
- **Earth, climate & energy:** [climate-netcdf-extreme-event-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/climate-netcdf-extreme-event-audit/instruction.md), [epa-swmm-stormwater-regression-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/epa-swmm-stormwater-regression-audit/instruction.md), [gdal-proj-raster-regression](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/gdal-proj-raster-regression/instruction.md), [matpower-opf-regression](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/matpower-opf-regression/instruction.md), [modflow6-groundwater-regression-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/modflow6-groundwater-regression-audit/instruction.md), [nrel-pysam-hybrid-renewables-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/nrel-pysam-hybrid-renewables-audit/instruction.md).
- **Software repair & toolchains:** [apex-openroad-ibex-signoff](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/apex-openroad-ibex-signoff/instruction.md), [commit0-multilib-tdd](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/commit0-multilib-tdd/instruction.md), [great-expectations-audit](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/great-expectations-audit/instruction.md), [langchain-version-migration](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/langchain-version-migration/instruction.md), [riscv-core-debug](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/riscv-core-debug/instruction.md), [unknown-config-semantics](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/unknown-config-semantics/instruction.md).
- **Games & strategy:** [2048](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/2048/instruction.md), [generals-bot-arena](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/generals-bot-arena/instruction.md), [snake-obstacle-campaign](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/snake_maze_campaign/instruction.md), [super-mario](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/super-mario/instruction.md).
- **Systems, performance & security:** [duckdb-optimizer-closure](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/duckdb-optimizer-closure/instruction.md), [grammar-fuzz-coverage-hunt](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/grammar-fuzz-coverage-hunt/instruction.md), [poc-exploit-craft](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/poc-exploit-craft/instruction.md), [spot-scheduler-traces](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/spot-scheduler-traces/instruction.md), [vector-db-iterative-build](https://github.com/zli12321/LHTB/blob/d78f5eb52ad754c5ee9154741af73130a85a65b8/tasks/vector-db-iterative-build/instruction.md).

### Concentration and sensitivity

- Across all 46 tasks, median paired delta is **0** against Plain and
  **0.000263888889** against Goal. Higher means do not imply a typical task gains.
- Research: without Tabular, mean deltas remain **+0.1259 / +0.1111** against
  Plain / Goal. ALP and Foldseek tie Goal; not all four beat both baselines.
- Puzzles: removing any one task leaves positive mean deltas on both sides
  (ranges **+0.1588…+0.3708** and **+0.0843…+0.2069**). Sudoku trails Goal;
  Chess trails Plain. This is still only four tasks.
- Systems: without PoC, the Plain delta changes from **+0.1732 to −0.0065**;
  without DuckDB, the Goal delta changes from **−0.1450 to +0.0111**.
  The group label hides two very different baseline-dependent cases.
- All six multimodal tasks have absolute paired deltas below 0.05 against
  both baselines. Science has zero median paired deltas on both sides.
- Software has no wins over Plain (4 ties, 2 losses). Perfect ties on
  LangChain and RISC-V indicate no headroom; all-zero OpenRoad is a failure
  floor. Neither establishes equal underlying capability.

Leave-one-out values remove exactly one task from that group's arithmetic
mean. They are sensitivity checks, not confidence intervals, revised study
results or permission to discard inconvenient tasks.

### What reading the tasks adds

The public instructions suggest testable conditions, not trajectory evidence:

- Sokoban retains solved levels when resetting the current puzzle; 2048
  retains peak scores. Tabular calls for iterative experiments and an audited
  model. Rush Hour requires manual spatial reasoning, route bookkeeping and
  replay checks, and **forbids programmatic search solvers**. These are plausible
  settings for durable progress, but Snake also retains peaks and trails Plain.
- APEX consulting has 33 dependent stages; law has 70, with exact document
  references and late corrections. Both expose a schema-only `validate`
  command. Law trails Goal: advancing stages is not evidence of semantic
  correctness. Long workflows alone do not predict an advantage.
- DuckDB requires all 22 TPC-H queries to remain correct. This illustrates a
  correctness veto and a reason to test best-version retention/rollback;
  final scores alone do not identify the trial's failure mechanism.
- Multimodal and simulation tasks require working perception/numerical
  pipelines and generalization, not just persistent task state. Small score
  differences do not show that extra continuation supplies those capabilities.

Instructions are pinned to upstream commit
`d78f5eb52ad754c5ee9154741af73130a85a65b8`, accessed 2026-09-19. Study IDs
`rush-hour-campaign` and `snake-obstacle-campaign` map to upstream folders
`rush_hour_campaign` and `snake_maze_campaign`. The extra current upstream task
`genetic-convergence-testing` is not in the 46-task study and is excluded.
The study identifies a **July 2026 snapshot without per-task source digests**;
byte identity between these public prompts and the evaluated versions is
unverified. Only representative instruction bodies were closely read; links
provide all members for inspection. No hidden tests or solutions were used.

There is one effective trial per cell, replacement trials and unequal runtime
budgets. Post-hoc grouping adds selection and taxonomy uncertainty. None of
these observations establishes statistical significance, a causal mechanism,
an equal-budget efficiency gain or generalization to another model/provider.
The next discriminating study would fix budgets, repeat matched task-arm runs,
and isolate progress retention, correctness feedback and rollback with traces.
