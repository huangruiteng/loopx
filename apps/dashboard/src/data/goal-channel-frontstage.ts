export type GoalChannelTodo = {
  todo_id?: string;
  priority?: string;
  status: string;
  title: string;
  claimed_by?: string;
  task_class?: string;
  action_kind?: string;
};

export type GoalChannelGate = {
  gate_id: string;
  kind: string;
  status: string;
  blocks?: string[];
};

export type GoalChannelLease = {
  todo_id?: string;
  owner_agent?: string;
  status?: string;
  lease_until?: string;
  write_scope?: string[];
};

export type GoalChannelEvent = {
  generated_at?: string;
  classification?: string;
  summary?: string;
};

export type GoalChannelProjection = {
  schema_version: "goal_channel_projection_v0";
  mode: "read_only";
  goal_id: string;
  display_name: string;
  generated_at: string;
  latest_status: string;
  waiting_on: string;
  next_action: string;
  source_refs: Record<string, string | null>;
  decision_frame: {
    user_action_required: boolean;
    agent_action_required: boolean;
    quiet_noop_allowed: boolean;
  };
  quota: Record<string, string>;
  user_todos: GoalChannelTodo[];
  agent_todos: GoalChannelTodo[];
  open_gates: GoalChannelGate[];
  active_leases: GoalChannelLease[];
  artifacts: Array<Record<string, string>>;
  recent_events: GoalChannelEvent[];
  source_warnings: Array<Record<string, string | string[]>>;
  truth_contract: {
    event_ledger_is_source_of_truth: boolean;
    projection_is_writable: boolean;
    recompute_rule: string;
    write_authority: string;
  };
};

export const sampleGoalChannelProjection: GoalChannelProjection = {
  schema_version: "goal_channel_projection_v0",
  mode: "read_only",
  goal_id: "demo-goal-channel",
  display_name: "Demo Goal Channel",
  generated_at: "2026-06-20T08:04:00Z",
  latest_status: "safe_side_path_running",
  waiting_on: "codex",
  next_action: "Render the read-only channel projection and keep the event ledger as truth.",
  source_refs: {
    status_generated_at: "2026-06-20T08:01:00Z",
    active_state_updated_at: "2026-06-20T08:00:00Z",
    latest_run_generated_at: "2026-06-20T08:02:00Z",
    review_packet_generated_at: "2026-06-20T08:03:00Z",
    event_ledger_source: "run_history",
  },
  decision_frame: {
    user_action_required: true,
    agent_action_required: true,
    quiet_noop_allowed: false,
  },
  quota: {
    allowed_slots: "10",
    reason: "synthetic fixture has quota",
    spend_policy: "spend after validated writeback",
    spent_slots: "2",
    state: "eligible",
  },
  user_todos: [
    {
      todo_id: "todo_user_decision",
      priority: "P0",
      status: "open",
      title: "Decide whether the gated delivery route may continue.",
    },
  ],
  agent_todos: [
    {
      todo_id: "todo_primary_route",
      priority: "P0",
      status: "open",
      claimed_by: "codex-main-control",
      task_class: "advancement_task",
      title: "Keep the primary delivery route visible while it waits.",
    },
    {
      todo_id: "todo_side_fixture",
      priority: "P2",
      status: "open",
      claimed_by: "codex-side-bypass",
      task_class: "advancement_task",
      title: "Render the productization frontstage fixture.",
    },
  ],
  open_gates: [
    {
      gate_id: "interaction_contract_user_channel",
      kind: "user_channel",
      status: "action_required",
      blocks: ["todo_user_decision"],
    },
  ],
  active_leases: [
    {
      owner_agent: "codex-main-control",
      status: "soft_claim",
      todo_id: "todo_primary_route",
    },
    {
      owner_agent: "codex-side-bypass",
      status: "soft_claim",
      todo_id: "todo_side_fixture",
    },
  ],
  artifacts: [
    {
      kind: "doc",
      label: "frontstage roadmap",
      path: "docs/frontstage-channel-lease-roadmap.md",
    },
    {
      kind: "local_state",
      label: "omitted private control-plane source",
    },
  ],
  recent_events: [
    {
      generated_at: "2026-06-20T08:02:00Z",
      classification: "validated_progress",
      summary: "frontstage fixture rendered from compact projection",
    },
    {
      generated_at: "2026-06-20T07:50:00Z",
      classification: "operator_gate_recorded",
      summary: "human decision stayed explicit",
    },
  ],
  source_warnings: [
    {
      key_names: ["path", "raw_internal_note"],
      kind: "raw_or_private_material_omitted",
      message:
        "raw/private-looking fields were omitted; inspect compact source references instead of copying raw material into the frontstage channel projection",
    },
  ],
  truth_contract: {
    event_ledger_is_source_of_truth: true,
    projection_is_writable: false,
    recompute_rule:
      "refresh from Goal Harness status/quota/run history; do not edit the channel projection as project truth",
    write_authority: "none",
  },
};
