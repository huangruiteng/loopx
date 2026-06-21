# Agents' Last Exam Triage V0

Checked at: 2026-06-11T00:50:00+08:00.

This note adds Agents' Last Exam (ALE) to the LoopX benchmark planning
backlog. It is a research triage artifact only. It does not run ALE, cloud
sandboxes, GUI tooling, Codex/model APIs, paid compute, uploads, shares, or
leaderboard submission.

## Sources

- Xiaohongshu share note: `http://xhslink.com/o/1tiETi329bL`, final note id
  `6a29525a0000000022023914`, title `Agent最后的考试公布！308位作者，结果炸裂`,
  author `小梦AI大模型打卡`, published `2026-06-10T12:02:34Z`.
- Primary paper: `https://arxiv.org/abs/2606.05405`, Agents' Last Exam,
  submitted 2026-06-03.
- Public code and data surface: `https://github.com/rdi-berkeley/agents-last-exam`.

## What ALE Is

ALE is a long-horizon, economically valuable, real-world agent benchmark with
verifiable outcomes. The primary paper describes collaboration with more than
250 industry experts, 55 subfields grouped into 13 industry clusters, and more
than 1,000 tasks. The public repository describes the open evaluation framework,
150 public reference tasks across 55 industries, real OS sandboxes, hidden
references, deterministic graders, and two reference agent harnesses.

The Xiaohongshu note is useful discovery signal, but the durable planning facts
come from the arXiv paper and repository. The note's highlighted claims map to
the primary source: 307 additional arXiv authors beyond the first author, a
reported 2.6 percent average full pass rate on the hardest tier, and a benchmark
positioned around real professional workflows rather than short coding tasks.

## Why It Matters For LoopX

ALE is more aligned with LoopX's long-horizon thesis than a pure coding
benchmark because it stresses:

- sustained multi-step work on real OS sandboxes;
- workflow state and artifact management across long runs;
- hidden-reference grading and deterministic checks;
- GUI plus CLI tool use;
- failure attribution across domain knowledge, method choice, setup, and
  artifact quality.

This makes ALE a good later-stage benchmark for whether LoopX improves
continuation quality, checkpoint discipline, restartability, and evidence
writeback on GDP-relevant tasks. It should not displace the current
Terminal-Bench paired pilot yet, because LoopX already has Terminal-Bench
runner contracts, no-submit boundaries, worker bridge instrumentation, and
ingest paths. ALE needs an adapter study first.

## Planning Placement

Treat ALE as a P1/P2 follow-on lane after the first Terminal-Bench official
paired pilot:

1. Finish the Terminal-Bench `terminal-bench@2.0/fix-code-vulnerability`
   hardened-codex versus codex-loopx paired pilot or record a compact
   runner blocker.
2. Build an ALE adapter dossier from the official repo docs: runner
   requirements, sandbox provider, agent harness integration point, output
   schema, public task subset, grading artifacts, and cost/time envelope.
3. Select one public Linux/CLI-friendly ALE task before any GUI-heavy task.
4. Define the paired arms with the same hardened install rule:
   `hardened-codex` baseline versus `codex-loopx` treatment.
5. Add compact ALE result ingestion only after one public-safe sample run exists.

## Claim Boundary

Do not claim ALE uplift until there is at least one real paired ALE result with
the same task, model, sandbox provider, timeout, attempts, and grading path.
Do not compare LoopX treatment to public ALE leaderboard entries unless
the agent harness, task subset, provider, scoring, and time budget match.

## Stop Conditions

Stop before:

- running cloud sandboxes, GUI agents, model APIs, paid compute, or uploads from
  an automatic heartbeat;
- copying hidden references, task answers, raw trajectories, screenshots,
  private paths, credentials, or raw logs into public artifacts;
- treating Xiaohongshu summary claims as authoritative without primary-source
  verification;
- replacing the current Terminal-Bench first paired pilot before its runner
  blocker or first result is recorded.

## Smoke

```bash
python3 examples/agents-last-exam-triage-smoke.py
```

The smoke validates that this triage note is public-safe, source-backed, and
keeps ALE behind the current Terminal-Bench paired pilot rather than turning it
into an immediate execution path.
