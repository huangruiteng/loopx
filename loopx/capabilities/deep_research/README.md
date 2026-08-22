# Deep research (evidence-ledger research loop)

`/loopx-deepresearch` turns one user question into a bounded, auditable research
session: question, source, claim, and contradiction ledgers live in
`.loopx/deepresearch/research.json`, the packet (`loopx deepresearch status`)
owns what to research next and when to stop, and the final report keeps every
citation resolvable to a recorded source.

## Boundary with auto-research

The built-in `auto-research` capability and this capability both do "bounded
research" but own different truths and must not be merged casually:

| | auto-research | deep-research (this) |
| --- | --- | --- |
| Unit of work | a LoopX **goal** with role-scoped workers | one **session ledger** in a project |
| State authority | goal todos, hypotheses, rollout events | `.loopx/deepresearch/` ledger |
| Progression | worker contract + terminal decision/review | packet expeditions + stop conditions |
| Output | promoted/retired hypotheses in canonical evidence | citation-auditable markdown report |
| Use when | open exploration inside the LoopX control plane | a single user question needing an auditable, source-cited answer |

Choose one per question; they do not share state and neither can close the
other's work.

## Lifecycle

`start` opens a run; `close` is the explicit terminal transition; the next
`start` archives the closed run (state + report) under
`.loopx/deepresearch/archive/<closed-at>/` and begins fresh. `start --new-run`
auto-closes only a run whose stop conditions already fired; an active run
always requires an explicit `close` first. State files are only ever rotated by
these typed transitions — never edited by hand.

## Layout

- Domain state machine and report: `loopx/deepresearch.py`
- CLI: `loopx/cli_commands/deepresearch.py` (`loopx deepresearch …`)
- Host entry: the `/loopx-deepresearch` skill facade installed by
  `loopx slash-commands --install`
