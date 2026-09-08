"""Heartbeat prompt rule constants inside the heartbeat bounded context."""


DEFAULT_MATERIAL_QUEUE_RULE = "Do not consume the learning material queue unless the user explicitly asks."
DEFAULT_PERMISSION_RULE = "Do not ask for permissions when the current Codex session is already trusted."
OPERATOR_LANGUAGE_RULE = (
    "Language=user; fallback=English; mix only if asked/scoped-bilingual."
)
OPERATOR_LANGUAGE_RULE_THIN = "Lang=user; default=en; mix=asked/scoped."
USER_TODO_FINAL_MESSAGE_RULE = (
    f"{OPERATOR_LANGUAGE_RULE} "
    "`interaction_contract.user_channel.notify` controls output: "
    "NOTIFY=action; DONT_NOTIFY=quiet. "
    "Due/peer work is not a prompt. Missing action: specific user Todo "
    "is not projected; repair LoopX state projection. With `DONT_NOTIFY`, repair "
    "the projection internally and stay quiet."
)
HEARTBEAT_NOTIFICATION_RULE_SHORT = (
    f"{OPERATOR_LANGUAGE_RULE} "
    "`user_channel.notify` OUTPUT only: NOTIFY=show; DONT_NOTIFY=no output. "
    "Work iff `heartbeat_recommendation.agent_must_attempt`/"
    "`execution_obligation.must_attempt_work`. Due/peer != prompt; "
    "missing action->repair Todo projection."
)
HEARTBEAT_NOTIFICATION_RULE_THIN = (
    f"{OPERATOR_LANGUAGE_RULE_THIN} OUTPUT only:N=show,D=none. Work iff "
    "agent_must_attempt/execution_obligation.must_attempt_work; due/peer not "
    "prompt; repair no action."
)
HEARTBEAT_VISION_WRITEBACK_RULE_SHORT = (
    "writeback: no-change=`surface_only`/no spend; "
    "unchanged->`--vision-unchanged-reason`; material->actual outcome."
)
SCHEDULER_HINT_APPLICATION_RULE = (
    "`scheduler_hint` no-spend. host_action=pause_or_delete_current_heartbeat -> "
    "automation_update stop once, verify, end; else apply_needed -> RRULE via "
    "automation_update; unavailable -> fallback_hint.cli_args (SQLite/app API "
    "bypass - fallback only), then ack; further failure -> failure_hint; "
    "ack_needed -> ack."
)
SCHEDULER_HINT_COMPACT_RULE = (
    "host_action=pause_or_delete_current_heartbeat: automation_update stop; "
    "else RRULE apply via automation_update, fallback_hint when unavailable, "
    "then ack/fail. No spend."
)
SCHEDULER_HINT_THIN_RULE = (
    "host_action=pause_or_delete_current_heartbeat->automation_update stop(no-spend); "
    "else RRULE/fallback_hint/ack/fail."
)
RUNTIME_CAPABILITY_PROJECTION_THIN_RULE = (
    "Observed capabilities -> `--available-capability`; never user gates."
)
RUNTIME_EXECUTION_ROUTING_RULE = (
    "Normal turns use CLI `interaction_contract`; use `loopx-project` for "
    "lifecycle/registry and `loopx-self-repair` for runtime/projection drift."
)
HOST_LOOP_QUOTA_DISPATCH_RULE = (
    "After quota, use selection_command when required; otherwise run "
    "next_cli_actions[0]."
)
HOST_LOOP_TODO_CLOSEOUT_RULE = (
    "Done -> successor first; final -> accountable refresh, spend, then "
    "no-follow-up completion."
)
HOST_LOOP_TODO_CLOSEOUT_COMPACT_RULE = (
    "Done->successor first; final->refresh->spend->no-follow-up."
)
CODEX_NATIVE_GOAL_UNCHANGED_WAIT_RULE = (
    "\n\nNative Codex `/goal` owns blocked state. Recheck quota at the "
    "`scheduler_hint.unchanged_poll` limit. Third identical blocked turn with no "
    "progress: call `update_goal` with `status=blocked`; no spend or LoopX "
    "completion. Only user `/goal resume` reactivates it; rerun quota after resume."
)
