# Change Quality Qualification

Change Quality Qualification gives a LoopX-managed goal a provider-neutral
final-diff review contract. It is default-off. A machine may define a live
default policy, and a Goal may pin a complete override. The selected policy
chooses two independent controls:

| Policy | Meaning |
| --- | --- |
| `safe_fix` | Permit one bounded repair pass before the final review receipt |
| `strict_receipt` | Require a passing receipt for the exact current diff at premerge |

`safe_fix` permits a bounded repair only inside authority the caller already
holds; it does not grant mutation authority. `strict_receipt` grants none.
Projects may enable either, both, or neither after enabling the capability.

## Configure A Goal

Install the release-owned workflow into each connected project and host that
should discover it:

```bash
loopx project-skill install \
  --project . \
  --skill loopx-change-quality \
  --surface codex \
  --execute
```

Use `claude-code` or `opencode` for those surfaces. This controls discovery,
not activation. Preview goal policy before applying:

```bash
loopx configure-goal \
  --goal-id <goal-id> \
  --change-quality-enabled \
  --change-quality-safe-fix \
  --change-quality-strict-receipt

loopx configure-goal \
  --goal-id <goal-id> \
  --change-quality-enabled \
  --change-quality-safe-fix \
  --change-quality-strict-receipt \
  --execute
```

To return a Goal to live machine-default inheritance:

```bash
loopx configure-goal \
  --goal-id <goal-id> \
  --clear-change-quality-configuration \
  --execute
```

Machine defaults use the same Dashboard preview/apply/rollback flow as other
machine namespaces. An explicit Goal policy always wins as one complete value;
clearing it restores live inheritance. Removing the machine namespace restores
the capability default, where all three values are false. Neither scope grants
file, permission, or merge authority.

## Protocol

1. `change-quality prepare` hashes the committed, staged, unstaged, and
   untracked content relative to a base ref. It emits
   `change_quality_prepare_packet_v2`.
2. The packet projects path-only repository context: applicable instruction
   files, ownership files, build manifests, language hints, changed surface
   roots, and a provider-neutral validation plan. It does not copy instruction
   text, task bodies, or manifest contents into the control plane.
3. A host or model reviews that exact scope simplify-first. It writes one
   grounded `reuse` conclusion, one grounded `simplification` conclusion,
   sparse triggered `risks[]`, and selected `validation[]`. Type/API
   boundaries, configuration, runtime ownership, efficiency,
   error/supervision, test/validation, documentation/comments, and
   security/release remain guardrail categories, but the Agent does not fill
   an all-clear row for each one. The result uses
   `change_quality_agent_result_v2`.
4. If policy allows it, the host may perform one bounded safe-fix pass. Any edit
   invalidates the old fingerprint, so prepare and final review run again.
5. `change-quality record --execute` validates those four result blocks against
   the current fingerprint, derives guardrail states from sparse risks and
   validation outcomes, and writes a compact local runtime receipt. Failed
   validation, skipped required validation, and unresolved blocker risks fail
   closed.
6. `change-quality verify` checks the current exact scope and v2 protocol.
   Earlier experimental receipt schemas are invalid and must be requalified.
7. `canary premerge --goal-id <goal-id>` enforces `strict_receipt`.

```bash
loopx --format json change-quality prepare \
  --goal-id <goal-id> --repo-path .

loopx --format json change-quality record \
  --goal-id <goal-id> --repo-path . \
  --result-json <ignored-or-temporary-result.json> --execute

loopx --format json change-quality verify \
  --goal-id <goal-id> --repo-path .

loopx canary premerge --from-git-diff --goal-id <goal-id>
```

Receipts live under goal runtime state, not in the repository. They retain the
two primary conclusions, sparse risks, typed validation evidence, and the
system-derived guardrail summary. Evidence references are typed and
cross-checked against exact changed paths, projected instructions, and
validators. Receipts do not retain raw model transcripts, credentials, private
context, or validator logs.

## Provider Boundary

The packet does not require a particular model, language, framework, or skill
host. Its review lenses name engineering outcomes rather than tools. A custom
runner may deliver the project-scoped `loopx-change-quality` skill or inject
equivalent instructions from the same LoopX revision. The global installer
intentionally skips project-scoped skills. The project still owns its tests,
lint, type checking, security checks, build commands, and repository-specific
rules; LoopX records which oracles ran and their outcomes instead of pretending
that one universal checker understands every language.

The validation plan discovers only repository-declared task identities from
structured manifests. Initial adapters understand Poe and Hatch task names in
`pyproject.toml`, Cargo aliases in `.cargo/config.toml`, and package scripts in
`package.json`. Each candidate carries a category, runner kind, task name, and
source reference; script bodies stay in the repository and execution remains a
host decision. Missing format, lint, typecheck, or test categories stay
explicitly unresolved instead of being filled with guessed commands. Applicable
`AGENTS.md` and `CLAUDE.md` files are projected as required reads, not parsed as
shell input. Manifests under fixture, testdata, vendor, third-party, or
dependency directories are reported as ignored references and never promoted
to project oracle candidates.

A blocking finding must be a concrete correctness, security, privacy, contract,
or required-validation failure. Subjective style advice remains nonblocking.
A failed validator is independently non-passing even when a reviewer forgot to
repeat it as a blocker finding.

Turn may carry the packet or receipt reference inside one bounded execution.
It does not own policy or enforcement. The authoritative merge decision stays
in `canary premerge`.

## Initial Scope

This version deliberately qualifies one final diff with at most one safe-fix
pass. It does not recursively review reviews, build a model hierarchy, or
require several agents to reach consensus. Language and build-system hints are
discovery inputs, not hardcoded validator policy. The initial matrix proves the
same output contract for Python, Rust, and TypeScript while preserving distinct
Poe, Cargo, and package-script runner identities. It does not invent a shared
compactor or silently execute any task.

The semantic calibration uses five public control-plane PRs covering a
registry boundary extraction, benchmark read-model move, recoverable Turn
stages, Vision replan repair, and capability-envelope propagation. The replay
keeps the benchmark-sensitive manual hold independent from receipt success and
proves that only one coherent safe-fix pass can be reported. The v2 fixture
also demonstrates the output-budget change directly: five cases no longer
carry fifty authored lens rows. These fixtures calibrate review behavior; they
are not project-specific production policy.

## Model-Behavior Shadow

Schema replay proves that a receipt is structurally valid; it does not prove
that a model will identify removable complexity or avoid inventing churn. The
separate `change_quality_shadow_matrix_v0` therefore pairs:

- five final, accepted public PR diffs that should remain free of speculative
  findings; and
- three behavior-preserving Python, Rust, and TypeScript changes whose tests
  still pass but whose implementation adds one-use wrappers or low-value
  helpers.

The live runner compares its historical v0 and simplify-first v1 shadow
prompts using the same model and exact case; those labels version the shadow
experiment, not the receipt protocol. It scores result-schema validity,
primary simplify coverage, simplify finding precision and
recall, false positives on accepted PRs, simplification decisions, safe-fix
eligibility, tracked-file mutation, output tokens, and latency:

```bash
python3 scripts/qualify-change-quality-model-shadow.py \
  --repo-root . \
  --model gpt-5.6-sol \
  --reasoning-effort low
```

This is a manually triggered, low-frequency qualification, not a PR smoke or
ordinary premerge step. Model actors run in disposable repositories. The
runner retains only result digests, bounded scores, usage, and latency; prompts,
model responses, stderr, command logs, and temporary worktrees are discarded.
A passing shadow may recommend strict-receipt promotion, but the receipt
explicitly sets `automatic_policy_mutation_allowed=false`. Repository policy
still changes through its normal owner and control-plane path. `--case-id`
runs remain useful diagnostics, but only a run over the complete currently
declared matrix may emit that promotion recommendation; an older receipt also
becomes ineligible when the matrix grows.
