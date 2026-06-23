---
description: loopx goal-mode (not Claude Code's built-in /goal). `/loopx <task>` sets up a goal and works in-session (the Stop hook keeps it going across turns); bare /loopx = ON; background = opt-in headless timer; off | status.
argument-hint: <task to do>  |  (no args = on)  |  background  |  off  |  status
allowed-tools: Bash(python3:*)
---

Run the goal-mode entry and read its output:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/goalmode_cmd.py" $ARGUMENTS`

FIRST, branch on the output — do this before anything else:
- If the output does NOT contain `READY: begin working` (i.e. `off`, a `status`
  detail block, or a "set a goal" prompt): it is already the complete,
  user-facing result — show it to the user VERBATIM and STOP. Do NOT call any
  tool, plan, or loop, and do NOT summarize a multi-line `status`/detail block
  into one line. (e.g. `off` -> show "goal-mode OFF".)

If the output says `READY: begin working`, the output already prints the exact
control-plane steps (with the goal_id, agent_id, and todo_id filled in) — FOLLOW
THEM VERBATIM. Use the wired `loopx` MCP tools (`should_run`, `claim_task`,
`complete_task`) which are zero-config — they read the goal/agent from goal-mode
state. Do NOT run `loopx --help`, probe `loopx quota ...` by hand, or guess a
goal-id; everything you need is in the output above. goal-mode STAYS ON until the
user runs `/loopx off` — do not turn it off yourself. While ON, every tool
call is gated by the loopx PreToolUse policy: read-only allowed; writes only
within the goal's write_scope; should_run=false pauses delivery; destructive
bash denied.

SAFETY OFFER (do this ONCE, before you start the loop, only when you see
`READY: begin working`): tell the user in one line that this goal will run
largely unattended, gated only by the loopx hook, and that enabling **auto mode**
(press Shift+Tab to cycle to it) adds a classifier that catches exfil/escalation
the hook can't — then ask whether they want it on. Auto mode is the user's own
toggle (you cannot force it); wait for their choice, then begin. Do not repeat
this offer on later `/loopx` calls in the same session.

NOTE: this is `/loopx` (loopx control plane), intentionally NOT named `/goal`
to avoid colliding with Claude Code's built-in `/goal`.
