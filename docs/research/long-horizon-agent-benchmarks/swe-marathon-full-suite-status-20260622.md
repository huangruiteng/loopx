# SWE-Marathon Full-Suite Status 2026-06-22

This is the public-safe sweep table for the pinned 20-case SWE-Marathon suite.
It uses public upstream task manifest metadata plus the compact public
benchmark run ledger. It does not copy raw task text, raw logs, trajectories,
verifier output, local paths, credentials, or hidden test material.

- source repo: `abundant-ai/swe-marathon`
- source commit: `0128be1c2f05fe0255dc2ffb083d503c6913486e`
- machine source: `swe-marathon-full-suite-status-20260622.json`
- current policy: run the CPU/no-CUA subset first; keep GPU, ML-training,
  browser/full-stack, and large rewrite lanes separate until the first CPU
  subset produces stable compact evidence.

## Summary

| Metric | Value |
| --- | ---: |
| Total cases | 20 |
| Cases already represented in public ledger | 3 |
| Not-started cases | 17 |
| GPU-required cases | 4 |
| Fresh CPU/no-CUA candidates | 3 |

## Next Case Decision

Next fresh case: `vliw-kernel-optimization`.

Reason: it is a fresh CPU/no-GPU non-browser optimization case with a short
public expert estimate, small build timeout, no prior compact run in the public
ledger, and fewer attribution layers than the web/full-stack, GPU, ML-training,
or large rewrite cases.

Secondary fresh case: `wasm-simd`.

Do not repeat `zstd-decoder` immediately. Its PR #467 prompt-polling treatment
already verifies product-path materialization and returns official `0.0`; the
next same-case repeat should first add public-safe edit/build/test/verify phase
counters or an approved redacted trajectory summarizer.

## Case Table

| Case | Resource | Tier | Ledger Status | CPU | GPU | Internet | Expert h | Next Action |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | --- |
| `biofabric-rust-rewrite` | cpu_online | defer_large_rewrite | not_started | 4 | 0 | yes | 80 | Defer until the initial CPU/no-CUA sweep has at least two fresh compact outcomes. |
| `embedding-eval` | gpu_offline | defer_gpu_or_ml | not_started | 4 | 1 | no | 4 | Defer until the GPU lane has stable capacity and cache policy. |
| `excel-clone` | cpu_online | defer_browser_or_fullstack | not_started | 4 | 0 | yes | 380 | Defer from the first CPU/no-CUA sweep because it is a browser/full-stack clone. |
| `find-network-alignments` | cpu_online | already_has_baseline_zero | baseline_failed_treatment_candidate | 4 | 0 | yes | 20 | Add phase counters or run a matched prompt-polling treatment; do not treat the baseline zero as infra failure. |
| `jax-pytorch-rewrite` | gpu_online | defer_gpu_or_ml | not_started | 8 | 1 | yes | 8 | Defer until GPU runner parity is tracked separately from the CPU/no-CUA lane. |
| `kubernetes-rust-rewrite` | cpu_offline | defer_large_rewrite | not_started | 4 | 0 | no | 200 | Defer until shorter CPU/no-CUA cases establish runner and treatment confidence. |
| `mastodon-clone` | cpu_online | defer_browser_or_fullstack | not_started | 4 | 0 | yes | 75 | Defer because browser/full-stack signals add another attribution layer. |
| `nextjs-vite-rewrite` | cpu_offline | defer_browser_or_fullstack | not_started | 4 | 0 | no | 400 | Defer as a browser/framework rewrite until non-browser CPU cases are sampled. |
| `parameter-golf` | gpu_offline | defer_gpu_or_ml | not_started | 4 | 1 | no | 8 | Defer until the GPU lane is intentional. |
| `post-train-ifeval` | cpu_online | defer_gpu_or_ml | not_started | 4 | 0 | yes | 4.5 | Defer because ML training semantics are a separate lane. |
| `ruby-rust-port` | cpu_online | defer_large_rewrite | not_started | 4 | 0 | yes | 110 | Defer until shorter CPU/no-CUA cases provide treatment signal. |
| `rust-c-compiler` | cpu_online | already_has_baseline_and_packet_observation | single_arm_recorded | 4 | 0 | yes | 30 | Run comparable prompt-driven treatment only after phase counters or a fresher CPU case. |
| `rust-java-lsp` | cpu_online | p1_fresh_cpu_no_cua_candidate | not_started | 4 | 0 | yes | 20 | Candidate after `vliw-kernel-optimization` or `wasm-simd`. |
| `s3-clone` | cpu_online | p1_fresh_cpu_service_candidate | not_started | 4 | 0 | yes | 60 | Candidate after lower-attribution CPU cases. |
| `slack-clone` | cpu_online | defer_browser_or_fullstack | not_started | 4 | 0 | yes | 60 | Defer until non-browser CPU and service-only cases are sampled. |
| `stripe-clone` | cpu_online | p1_fresh_cpu_service_candidate | not_started | 4 | 0 | yes | 14 | Fresh CPU candidate after non-service optimization/systems cases. |
| `trimul-cuda` | gpu_offline | defer_gpu_or_ml | not_started | 4 | 1 | no | 40 | Defer until GPU capacity/cache lane is explicit. |
| `vliw-kernel-optimization` | cpu_online | p0_next_fresh_cpu_no_cua_candidate | not_started | 4 | 0 | yes | 8 | Launch the next native Goal baseline or matched base/test pair under the no-upload compact-result boundary. |
| `wasm-simd` | cpu_online_unspecified_gpu_field | p0_next_fresh_cpu_no_cua_candidate | not_started | 4 | n/a | yes | 12 | Secondary fresh CPU/no-CUA candidate after `vliw-kernel-optimization`. |
| `zstd-decoder` | cpu_offline | already_has_paired_negative | paired_treatment_regressed | 1 | 0 | no | 12 | Do not repeat immediately; add phase counters or a redacted trajectory summarizer first. |

## Follow-Up

1. Run `vliw-kernel-optimization` next as a native Goal baseline or matched
   base/test pair, keeping no-upload compact-result boundaries.
2. Keep `find-network-alignments`, `rust-c-compiler`, and `zstd-decoder` in
   the analysis lane until public-safe solution-phase counters exist.
3. Do not mix GPU/ML/browser/full-stack results into the first CPU/no-CUA
   signal; they are valuable, but they need separate capacity and attribution
   lanes.
