# Active User Assisted Pilot V0

Checked at: 2026-06-10T16:08:00+08:00.

This fixture defines the first deterministic active-user assisted pilot for
LoopX long-horizon benchmark research. It is a public-safe pilot shape,
not a real benchmark run and not an official score claim.

## Purpose

The pilot tests whether a controlled active user simulator can be evaluated on
a case where autonomous modes already produced a compact negative result. The
first reference case is `terminal-bench@2.0/train-fasttext`, using only compact
public-safe facts:

- autonomous baseline score: `0.0`;
- passive LoopX treatment score: `0.0`;
- assisted score: `not_run`;
- raw runner logs, worker transcripts, local artifact paths, hidden tests, and
  expected solutions are unavailable to the simulator.

The pilot asks whether assisted user intervention could be studied without
mixing assisted collaboration evidence into official benchmark evidence.

## Pilot Shape

The local schema is `active_user_assisted_pilot_v0`. A deterministic smoke
should bind the `active_user_simulator_injection_v0` intervention contract and
emit one compact `operator_simulator_run_v0` row that references the failed
case and records:

- the failed autonomous modes used as the pilot trigger;
- active user simulator setting and seed;
- proactive user messages with visible evidence basis;
- frequency-budget audit;
- no-oracle audit per intervention;
- official score reference with `assisted_score_kind=not_run`;
- separate collaboration hypothesis and next-run decision.

## Intervention Policy

The simulator may proactively inject direct user-style feedback. It can say
what to do next, challenge the current path, or force a validation order. The
pilot controls risk through budgets and audits:

- maximum proactive interventions: `2`;
- minimum worker events between proactive interventions: `2`;
- maximum characters per intervention: `800`;
- every intervention must list allowed visible evidence;
- every no-oracle audit field must be false;
- any suspected oracle leak or overguidance must become a failure label.

## Worker Channel

The first public implementation uses an audited external update loop rather
than a direct Codex chat-session injection. The simulator appends compact
user-style messages to a worker-visible feed, and the worker polls
`loopx worker-bridge active-user-observe` after its own start marker.

This channel is intentionally pull-based:

- the worker must observe an intervention with `seq > worker_start_seq`;
- observation is recorded as compact JSON without raw paths or transcripts;
- simulator append commands must emit single-line JSONL before redirecting to
  the feed;
- compact worker observation can be ingested through `benchmark_run_v0` as
  assisted-collaboration evidence while leaving official score as `not_run`;
- direct Codex chat injection remains a separate optional surface;
- official score and leaderboard claims remain disallowed for assisted runs.

## Claim Boundary

This pilot can support only assisted-collaboration claims. It cannot be used as
an official Terminal-Bench score, a leaderboard result, or proof that Goal
Harness improves autonomous solve rate.

The deterministic smoke is:

```bash
python3 examples/active-user-assisted-pilot-smoke.py
python3 examples/worker-bridge-active-user-feed-smoke.py
python3 examples/worker-bridge-active-user-after-start-observation-smoke.py
python3 examples/benchmark-run-v0-active-user-observation-ingest-smoke.py
python3 examples/terminal-bench-active-user-assisted-observation-fixture-smoke.py
```

It performs no model call, no benchmark run, no Docker or cloud sandbox use, no
paid compute, no private artifact read, and no leaderboard upload.
