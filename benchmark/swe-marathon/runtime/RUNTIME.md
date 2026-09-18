# SWE-Marathon execution

Use the [shared Codex runtime](../../runtime/RUNTIME.md), retaining SWE-Marathon's
native dataset, task environment, phase/feedback rules and scoring. The entry
`benchmark.runtime.harbor:BenchmarkCodex` is also used by LHTB. A native job
agent fragment is available in `../configs/shared-heartbeat.yaml`.

The previous modes/ and turn/ implementations are retired. They duplicated
installation and continuation, and the old Turn validator accepted empty commits
or subsequent no-op iterations after the first changed HEAD. Public Turn CLI
execution and caller-provided independent validation replace that behavior.

Named agent imports remain thin compatibility entries. codex_loopx_agent now
selects loopx-goal explicitly. Retired WEN/assisted controls fail with migration
guidance; select execution_mode and iteration_context for new studies.

Prior code is preserved in Git at 8330a974cc2631ffd006d1fb7bd1627d2d690e85.
Historical results and withdrawal notices are unchanged and do not describe the
new runtime. Consumers of the former runtime directories, including pending TB4
work, must migrate to the shared entry before claiming compatibility.
