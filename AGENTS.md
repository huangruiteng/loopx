# Agent Instructions

## Commit And PR Hygiene

For non-trivial repository changes, especially anything that touches benchmark
adapters, smoke tests, public docs, or commit/push workflows, use the
`git-split-commit-pr` workflow before staging:

1. Establish ground truth with `git status --short --branch`,
   `git diff --stat`, `git diff --name-only`, and
   `git ls-files --others --exclude-standard`.
2. Classify every changed path before staging:
   - core product code;
   - core documentation;
   - durable validation smoke;
   - local/private state;
   - low-value or obsolete artifact.
3. Scan candidate paths for credentials, private state, local absolute paths,
   raw benchmark logs, trajectories, verifier output, and internal links.
4. Stage by explicit pathspecs only. Do not use `git add .`.
5. Split commits by reviewer logic:
   - runtime/API behavior;
   - public docs and protocol notes;
   - focused validation or cleanup.
6. Push a branch and open a PR for reviewable batches instead of pushing broad
   mixed commits directly to `main`, unless the user explicitly asks for a
   direct `main` push.

For small, low-risk PRs, maintainers may self-merge after validation when all
of the following are true:

- the PR only touches public docs, contributor metadata, or narrow cleanup;
- the change is single-purpose and easy to review from the diff;
- required checks or focused smokes have passed;
- private state, raw benchmark evidence, credentials, local paths, and
  generated logs are excluded;
- there is no runtime behavior, benchmark adapter, permission, destructive git,
  or public evidence-policy change that needs separate review.

After self-merging, sync local `main`, leave unrelated untracked local artifacts
alone, and continue with the next safe project batch.

## Smoke Retention Policy

Keep a smoke test only when it validates a durable public behavior:

- shipped CLI/runtime behavior;
- a reusable control-plane contract;
- public/private boundary enforcement;
- a regression that previously stranded automation;
- a representative fixture that is likely to catch future bugs.

Do not keep one-off smokes whose main purpose is to assert the exact text of a
dated research note, candidate ranking packet, temporary run review, or
transitional benchmark decision. Preserve that information in the research doc
itself, and cover shared invariants with a data-driven aggregate smoke.

When a smoke grows beyond roughly 300 lines, re-check whether it is really one
test. Prefer splitting reusable logic into product modules and keeping the
smoke as a thin public behavior check. Large integration smokes are acceptable
only when they cover a real end-to-end adapter contract that smaller unit tests
cannot cover.

Benchmark smokes must never require raw task text, raw trajectories, raw logs,
verifier output tails, credentials, uploads, leaderboard submissions, or local
private artifact paths.

## Benchmark Smoke Classification

Use this classification when cleaning or reviewing benchmark-related changes:

- Keep focused boundary smokes such as
  `examples/benchmark-candidate-source-boundary-smoke.py`; they guard a reusable
  public/private source contract.
- Keep ledger and analysis smokes such as
  `examples/benchmark-run-ledger-smoke.py` and
  `examples/benchmark-case-analysis-smoke.py` while the corresponding JSON/MD
  assets are shipped public surfaces.
- Keep state/control-plane regression smokes such as
  `examples/state-projection-gap-smoke.py`; they protect automation from known
  stuck states.
- Treat large adapter integration smokes such as
  `examples/skillsbench-benchmark-run-smoke.py` as high-value but expensive:
  keep them only while they cover real runner/ledger behavior that smaller
  tests do not yet cover, and split them when a stable smaller seam exists.
- Do not keep one smoke per dated Terminal-Bench routing packet. Preserve the
  packet docs as historical evidence and validate shared invariants with
  `examples/terminal-bench-candidate-routing-packets-smoke.py`.
