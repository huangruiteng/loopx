# DeepSWE GPT xhigh v1 Archive

> **Historical results notice:** The
> [current SWE Marathon publication](swe-marathon/README.md) withdraws SSH Goal
> and Codex CLI data and conclusions pending revalidation. Their rows in the
> frozen v1 README are preserved historical text, not currently validated claims.
> **历史结果提示：** SSH Goal 与 Codex CLI 两组数据及结论已撤回、待复验；
> v1 原始表格仅作为历史记录保留，不代表恢复这些结论。

This snapshot follows the canonical
[archive placement rules](README.md#archive-placement). It is an inert historical
reference, outside active benchmark execution and current-practice guidance.

This PR publishes only the original v1 code and historical result summary in
[deepswe-gptxhigh-v1](deepswe-gptxhigh-v1/README.md). The revised execution package
has been removed from this PR. No later admission, retry, gateway, concurrency,
or termination changes are applied to v1.

## Snapshot Identity

The contributor's source record identifies local commit
`98c262a8487ff5688d38091f603a87f7e2a78c64`, subtree
`benchmark/deepswe-five-arm/`. That commit is not reachable in this upstream
repository; it is provenance metadata, not independently verifiable upstream
commit history. Only the containing directory name changes in the export.

The publicly verifiable identity of the 14 archived files, including their
contents and executable modes, is Git tree
`1bc5d2b3b74761a97d34ba3f3612e977fd610340`. Readers can verify that identity
against this PR's archived directory and the read-only checker without access
to the contributor's source commit. Tree equality verifies the exported bytes,
not the claimed experiment's execution or results.

The evaluated LoopX revision was `2cef51d`. The original README's references to
"this branch's base" and an in-progress v2 are historical text, not current
project status. No new benchmark results are included here.

## Executability Checks

From the repository root, with Python 3.11+ and Bash installed:

```sh
python3 benchmark/check_deepswe_v1.py
```

This read-only check verifies the archive's actual file bytes and modes, parses
all Python files and the two embedded `_RUNNER` / `_BOOTSTRAP` constants, and runs
`bash -n` on the launchers. It makes no model calls and does not run task code.
Exit zero means those checks passed, **not that a complete benchmark ran**.
The report explicitly records `standalone_runnable: false`.
The repository's ignored Python bytecode (`*.pyc` and bytecode-only
`__pycache__/` directories) is excluded from the identity check, so compilation
by the premerge gate does not change the snapshot identity. Extra source files,
non-bytecode cache entries, symlinks, and changes to archived bytes or executable
modes still fail. `.gitattributes` pins the archive to LF line endings even when
Git checks out other text files with `core.autocrlf=true`.
Generated validator programs and Python inside shell heredocs are not separately
compiled by this check; it does not claim exhaustive embedded-program coverage.

An additional local smoke imported the original adapters and dispatched all
five arm selectors using Python 3.12.13 and `datacurve-pier` 0.3.1 with external
experiment modules available. No agents were instantiated and no task/model
execution was attempted. This is import/dispatch compatibility evidence only,
not a full dependency lock or an end-to-end reproduction.

## Runtime Prerequisites

The original snapshot is an export from an external experiment workspace,
not a standalone distribution. Running it requires all of the following:

| Requirement | Original interface |
| --- | --- |
| Python environment | Python 3.11+, compatible `datacurve-pier`; archived launchers expect `.venv-user-395647/bin/python` |
| LoopX source | A separate clean checkout of evaluated revision `2cef51d08b2a0103f4ba026bf47fd70dc8acee30`, selected with `MR_LOOPX_ROOT` |
| Plain arm support | Original external `plain_appserver_runner.py` beside `goal_codex.py` |
| Launch environment | External `run.sh` and its gateway, host-environment, and reporting dependencies |
| Task selection | `goal30_subset.py`, `hard24_subset.py`, `remaining4_subset.py`, and `remaining59.txt` |
| Task definitions | DeepSWE task definitions under `upstream/tasks/`, including independent verifier environments |
| Container runtime | Docker, Compose, task images, and external `docker-compose-modelonly.yaml` |
| Provider access | Separately configured gateway reachable from the task containers; sanitized loopback placeholders are not a complete deployment configuration |

Assemble these inputs in a **new, isolated experiment workspace**, then place
the archived files there without rewriting them. Keep the published archive
unchanged, and do not overlay files into an ongoing benchmark workspace.
Record the external dependency versions and hashes with that run. Credentials,
raw task text, model configuration, and trajectories are intentionally absent
from this public repository.

The five documented selectors are `plain`, `goal`, `loopx-native`,
`loopx-native-codex-cli`, and `loopx-native-heartbeat`. Legacy Claude and
`MR_CODEX_ARM=loopx` paths are preserved as source history; they are not an
additional supported reproduction claim.

## Known Limits

Original defects remain visible: missing external support files, hard-coded
environment assumptions, the remaining-59 launcher's 54-task admission mismatch,
profile initialization races, and launcher/retry failure handling.
These defects prevent a claim that the unchanged archive is fully runnable or
that its admission receipts reliably validate every future run.
Guaranteeing a clean end-to-end run requires separately reviewed execution
changes and validation in the actual runtime environment; silently changing
v1 to achieve that would invalidate the immutable snapshot boundary.

The former revised package remains available in the previous PR commit
`a8fa4f9cf842557ee11ba24056c46a1410763c8c`, outside the final PR file set.
It is not the currently running new benchmark and has no attributed results.

No benchmark was rerun for this PR. The
[current SWE Marathon publication](swe-marathon/README.md) withdraws SSH Goal and
Codex CLI data and conclusions pending revalidation. The unchanged historical
v1 summary does not override that correction.

## 中文说明

本 PR 仅保留旧 v1 原始代码及结果，已移出 `v1-revised`。
原始 14 个文件的内容和权限不变；没有混入正在运行的新 benchmark 结果。

新增的归档检查命令只验证文件完整性、Python 文件、两个指定内嵌常量及 Shell 语法，
不调用模型、不执行任务，也不代表完整实验已跑通。运行仍需上表中的外部依赖，
原始执行缺陷同样保留。不能在不改原逻辑、未验证真实环境的前提下保证端到端可执行。
