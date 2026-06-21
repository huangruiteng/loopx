# Public-Safe Trajectory Summary v0

LoopX benchmark attribution needs enough trajectory shape to explain
good and bad cases without copying private task text, prompts, verifier output,
tool output, or trajectory bodies. The shared reducer in
`loopx.benchmark_trajectory` records only public-safe counters.

## Contract

The reducer may record:

- event, round, user-message, assistant-message, and tool-call counts;
- normalized tool categories such as `inspection`, `edit`, `validation`,
  `loopx_cli`, `execution`, and `vcs`;
- normalized LoopX CLI command labels, with flags but without raw output;
- LoopX CLI state-usage buckets: `state_read`, `state_write`,
  `context_lookup`, and `other`;
- sandbox-path mentions and edit-signal counters, including whether an edit
  touched a path previously named by a protected-path directive.

The reducer must not record:

- raw task instructions, prompts, solutions, verifier output, or tool output;
- host absolute paths;
- credentials or raw local session material.

## Attribution Use

This contract is enough to distinguish mechanism-level causes such as:

- uplift/regression from extra interactions versus first-round behavior;
- treatment damage from protected-path edits;
- product-mode no-op from non-substantive `context_lookup` calls such as
  `loopx which goal`;
- substantive LoopX use from actual state reads or writes.

Content-level root cause still requires a stronger redacted semantic summarizer
or an explicit owner gate to inspect raw private trajectory material.
