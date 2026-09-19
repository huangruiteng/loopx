"""Stage 2C observation-foundation rows of the shared-goal-authority ladder.

These rows port the local-shadow CLI E2E and migration assertions onto the
ladder: every write goes through the real ``python -m loopx.cli`` and the
candidate is read back only from its retained bytes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from .authority_e2e_fixtures import (
    GoalWorkspace,
    JsonObject,
    LegacyMigrationSource,
    build_goal_workspace,
    build_legacy_migration_source,
    candidate_document,
    candidate_store_paths,
    hold_observation_lock,
    kill_now,
    parse_json_object,
    run_cli,
    spawn_cli,
    unique_goal_id,
    wait_until,
)
from .authority_e2e_row_support import (
    AGENT_A,
    AGENT_B,
    DEFAULT_OFF_PARITY_FIELDS,
    LOCAL_SHADOW_SUMMARY_ENABLED,
    MIGRATION_SEED_SCHEMA,
    PRIMARY_VISIBILITY_TIMEOUT_SECONDS,
    RowContext,
    RowOutcome,
    acquire_lease,
    add_todo,
    committed_observation,
    configure_shadow,
    expect,
    lease_version,
    passed,
    shadow_evidence,
)

def shadow_workspace(context: RowContext, prefix: str, *, shadow_enabled: bool) -> GoalWorkspace:
    return build_goal_workspace(
        context.root,
        goal_id=unique_goal_id(prefix),
        handoff_mode="hard_lease",
        shadow_enabled=shadow_enabled,
        runtime_root_binding="cli_override",
    )


def row_configure_enable_disable_roundtrip(context: RowContext) -> RowOutcome:
    workspace = shadow_workspace(context, "ladder-configure", shadow_enabled=False)
    preview = configure_shadow(workspace, "--local-authority-shadow-file")
    expect(preview.get("dry_run") is True and preview.get("written") is False, "preview must not write")
    enabled = configure_shadow(workspace, "--local-authority-shadow-file", "--execute")
    expect(enabled.get("written") is True, "enable must write the registry")

    observed = add_todo(workspace, "Capture one post-commit observation through the product CLI.")
    evidence = committed_observation(observed, label="todo add")
    expect(evidence["outcome"] == "captured", "first observation must be captured")
    expect(evidence["parity_verdict"] == "not_evaluated", "observation must not claim parity")
    lease = acquire_lease(
        workspace,
        todo_id=str(observed["todo_id"]),
        owner=AGENT_A,
        idempotency_key="ladder-configure-lease",
    )
    expect(lease.get("acquired") is True, "lease must be acquired")
    expect(committed_observation(lease, label="task-lease acquire")["outcome"] == "captured", "lease observation must be captured")
    document = candidate_document(workspace)
    expect(len(document.todo_ids) == 1 and len(document.leases) == 1, "candidate head must hold one todo and one lease")

    inspected = configure_shadow(workspace)
    after = inspected.get("after")
    expect(
        isinstance(after, dict) and after.get("local_authority_shadow") == LOCAL_SHADOW_SUMMARY_ENABLED,
        "configure-goal must read back the enabled shadow summary",
    )
    disabled = configure_shadow(workspace, "--clear-local-authority-shadow", "--execute")
    expect(disabled.get("written") is True, "disable must write the registry")
    before_disabled_write = document.path.read_bytes()
    after_disable = add_todo(workspace, "This local lifecycle write must not execute the observer.")
    expect(after_disable.get("ok") is True and after_disable.get("added") is True, "disabled write must still commit")
    expect("authority_shadow" not in after_disable, "disabled write must not observe")
    expect(document.path.read_bytes() == before_disabled_write, "candidate bytes must not change once disabled")
    return passed(candidate_cursor=document.cursor, head_todos=1, head_leases=1)


def row_default_off_isolation(context: RowContext) -> RowOutcome:
    enabled = shadow_workspace(context, "ladder-enabled", shadow_enabled=True)
    baseline = shadow_workspace(context, "ladder-baseline", shadow_enabled=False)
    text = "Capture one post-commit observation through the product CLI."
    observed = add_todo(enabled, text)
    committed_observation(observed, label="enabled todo add")
    default_off = add_todo(baseline, text)
    expect("authority_shadow" not in default_off, "default-off write must not carry observation evidence")
    differing = [field for field in DEFAULT_OFF_PARITY_FIELDS if observed.get(field) != default_off.get(field)]
    expect(not differing, f"default-off response fields must match the observed response: {differing}")
    expect(not (baseline.runtime_root / "authority-shadow").exists(), "default-off must not create candidate storage")
    return passed(compared_fields=len(DEFAULT_OFF_PARITY_FIELDS))


def row_candidate_failure_preserves_primary(context: RowContext) -> RowOutcome:
    workspace = shadow_workspace(context, "ladder-failure", shadow_enabled=False)
    configure_shadow(workspace, "--local-authority-shadow-file", "--execute")
    workspace.runtime_root.mkdir(parents=True, exist_ok=True)
    (workspace.runtime_root / "authority-shadow").write_text("block candidate directory", encoding="utf-8")
    result = add_todo(workspace, "The primary write survives a candidate construction failure.")
    expect(result.get("ok") is True and result.get("added") is True, "primary write must commit")
    evidence = shadow_evidence(result, label="todo add")
    expect(evidence.get("outcome") == "failed", "candidate failure must be reported as failed")
    expect(evidence.get("reason_code") == "shadow_observation_failed", "candidate failure must carry its typed reason")
    expect(evidence.get("primary_writeback_preserved") is True, "candidate failure must preserve the primary writeback")
    expect(
        str(result["todo_id"]) in workspace.state_path.read_text(encoding="utf-8"),
        "the committed todo must be present in the primary state",
    )
    return passed(outcome="failed", reason_code="shadow_observation_failed")


def row_crash_gap_loses_observation(context: RowContext) -> RowOutcome:
    workspace = shadow_workspace(context, "ladder-crash-gap", shadow_enabled=False)
    configure_shadow(workspace, "--local-authority-shadow-file", "--execute")
    first_text = "Primary commit that loses its post-commit observation."
    with hold_observation_lock(workspace):
        process = spawn_cli(
            workspace,
            "todo",
            "add",
            "--goal-id",
            workspace.goal_id,
            "--role",
            "agent",
            "--text",
            first_text,
            "--task-class",
            "advancement_task",
        )
        try:
            visible = wait_until(
                lambda: first_text in workspace.state_path.read_text(encoding="utf-8"),
                PRIMARY_VISIBILITY_TIMEOUT_SECONDS,
            )
            expect(visible, "primary Todo commit did not become visible")
            expect(process.poll() is None, "writer must still be blocked on the observation lock")
        finally:
            kill_now(process)
    expect(not candidate_store_paths(workspace), "a killed writer must leave no candidate document")
    recovered = add_todo(workspace, "A later primary commit refreshes the current full snapshot.")
    evidence = committed_observation(recovered, label="recovering todo add")
    expect(evidence["outcome"] == "captured", "recovery observation must be captured")
    expect(evidence["durable_source_outbox"] is False, "no durable outbox may be claimed")
    expect(evidence["source_transaction_correlated"] is False, "no transaction correlation may be claimed")
    expect(evidence["parity_verdict"] == "not_evaluated", "recovery must not claim parity")
    document = candidate_document(workspace)
    expect(len(document.todo_ids) == 2, "the refreshed snapshot must include both primary commits")
    return passed(lost_observations=1, refreshed_head_todos=2, candidate_cursor=document.cursor)


@dataclass
class _WriterSequence:
    workspace: GoalWorkspace
    committed: list[tuple[str, JsonObject]] = field(default_factory=list)

    def commit(self, label: str, payload: JsonObject, *, flag: str) -> JsonObject:
        expect(payload.get(flag) is True, f"{label} must report {flag}=true")
        self.committed.append((label, payload))
        return payload

    def cli(self, *args: str) -> JsonObject:
        return run_cli(self.workspace, *args, "--goal-id", self.workspace.goal_id)


def _writer_sequence_lease_lifecycle(sequence: _WriterSequence) -> str:
    """Add a todo, then acquire, update, renew, transfer, and complete it."""

    first = sequence.commit(
        "todo add",
        add_todo(sequence.workspace, "Deliver one bounded control-plane change."),
        flag="added",
    )
    todo_id = str(first["todo_id"])
    acquired = sequence.commit(
        "task-lease acquire",
        acquire_lease(sequence.workspace, todo_id=todo_id, owner=AGENT_A, idempotency_key="ladder-lease-a"),
        flag="acquired",
    )
    sequence.commit(
        "todo update",
        sequence.cli("todo", "update", "--todo-id", todo_id, "--note", "A public-safe update.", "--agent-id", AGENT_A),
        flag="changed",
    )
    renewed = sequence.commit(
        "task-lease renew",
        sequence.cli(
            "task-lease", "renew", "--todo-id", todo_id, "--owner", AGENT_A,
            "--idempotency-key", "ladder-lease-a",
            "--expected-version", lease_version(acquired, label="acquire"),
            "--ttl-seconds", "120",
        ),
        flag="renewed",
    )
    transferred = sequence.commit(
        "task-lease transfer",
        sequence.cli(
            "task-lease", "transfer", "--todo-id", todo_id, "--owner", AGENT_A,
            "--idempotency-key", "ladder-lease-a", "--new-owner", AGENT_B,
            "--new-idempotency-key", "ladder-lease-b",
            "--expected-version", lease_version(renewed, label="renew"),
            "--ttl-seconds", "120",
        ),
        flag="transferred",
    )
    sequence.commit(
        "todo complete",
        sequence.cli(
            "todo", "complete", "--todo-id", todo_id, "--agent-id", AGENT_B,
            "--task-lease-idempotency-key", "ladder-lease-b",
            "--task-lease-expected-version", lease_version(transferred, label="transfer"),
            "--evidence", "validation://ladder-complete", "--no-follow-up",
        ),
        flag="completed",
    )
    return todo_id


def _writer_sequence_supersede_and_hygiene(sequence: _WriterSequence) -> str:
    """Add a second todo, replay its acquire, supersede it, then run hygiene writers."""

    second = sequence.commit(
        "todo add (second)",
        add_todo(sequence.workspace, "Replace this bounded work with a successor."),
        flag="added",
    )
    todo_id = str(second["todo_id"])
    acquired = sequence.commit(
        "task-lease acquire (second)",
        acquire_lease(sequence.workspace, todo_id=todo_id, owner=AGENT_A, idempotency_key="ladder-lease-c"),
        flag="acquired",
    )
    replayed = acquire_lease(sequence.workspace, todo_id=todo_id, owner=AGENT_A, idempotency_key="ladder-lease-c")
    expect(replayed.get("idempotent") is True, "re-acquire with the same key must be idempotent")
    expect("authority_shadow" not in replayed, "an idempotent re-acquire must not observe")
    sequence.commit(
        "todo supersede",
        sequence.cli(
            "todo", "supersede", "--todo-id", todo_id, "--agent-id", AGENT_A,
            "--reason", "Replace obsolete work.",
            "--next-agent-todo", "Carry the bounded work forward.",
            "--task-lease-idempotency-key", "ladder-lease-c",
            "--task-lease-expected-version", lease_version(acquired, label="acquire (second)"),
        ),
        flag="superseded",
    )
    sequence.commit(
        "todo add (verification)",
        add_todo(sequence.workspace, "Verify the migrated authority projection."),
        flag="added",
    )
    sequence.commit(
        "todo archive-completed",
        sequence.cli("todo", "archive-completed", "--max-active-done", "0", "--execute"),
        flag="changed",
    )
    return todo_id


def row_every_writer_family_captures(context: RowContext) -> RowOutcome:
    workspace = build_goal_workspace(
        context.root,
        goal_id=unique_goal_id("ladder-writers"),
        handoff_mode="legacy",
        shadow_enabled=True,
        runtime_root_binding="cli_override",
    )
    sequence = _WriterSequence(workspace)
    sequence.commit(
        "handoff-mode set",
        sequence.cli("handoff-mode", "set", "--mode", "hard_lease"),
        flag="changed",
    )
    first_todo = _writer_sequence_lease_lifecycle(sequence)
    second_todo = _writer_sequence_supersede_and_hygiene(sequence)

    observations = [committed_observation(payload, label=label) for label, payload in sequence.committed]
    captured = [evidence for evidence in observations if evidence["outcome"] == "captured"]
    document = candidate_document(workspace)
    expect(document.cursor == str(len(captured)), "candidate cursor must equal the number of captured observations")
    expect(
        set(document.operation_ids) == {str(evidence["observation_id"]) for evidence in observations},
        "candidate operation ids must be exactly the observation ids",
    )
    expect(
        {str(lease.get("todo_id")) for lease in document.leases} == {first_todo, second_todo},
        "candidate head must retain the lease records of both leased todos",
    )
    expect(
        all(lease.get("status") == "released" for lease in document.leases),
        "no time-active lease may remain in the candidate head",
    )
    listed = sequence.cli("todo", "list")
    listed_ids = sorted(str(todo.get("todo_id")) for todo in listed.get("todos") or [] if isinstance(todo, dict))
    expect(sorted(document.todo_ids) == listed_ids, "candidate head todos must equal the projected todo list")
    return passed(
        writer_families=len(sequence.committed),
        captured=len(captured),
        outcomes=sorted({str(evidence["outcome"]) for evidence in observations}),
        candidate_cursor=document.cursor,
        head_todos=len(document.todo_ids),
        head_leases=len(document.leases),
    )


def _migration_arguments(source: LegacyMigrationSource) -> list[str]:
    return [
        "migrate-state",
        "--legacy-registry", str(source.legacy_registry),
        "--legacy-runtime-root", str(source.legacy_runtime),
        "--target-runtime-root", str(source.target_runtime),
        "--goal-id", source.old_goal_id,
        "--goal-id-map", f"{source.old_goal_id}={source.new_goal_id}",
        "--path-map", f"{source.source_repo}={source.target_repo}",
        "--copy-active-state",
        "--copy-runtime",
        "--no-global-sync",
    ]


def _first_entry(payload: Mapping[str, object], key: str, *, label: str) -> JsonObject:
    entries = payload.get(key)
    expect(isinstance(entries, list) and len(entries) == 1, f"{label} must report exactly one {key} entry")
    assert isinstance(entries, list)
    entry = entries[0]
    expect(isinstance(entry, dict), f"{label} {key} entry must be an object")
    assert isinstance(entry, dict)
    return {str(field): value for field, value in entry.items()}


def _assert_migration_preview(source: LegacyMigrationSource, preview: JsonObject, sentinel: bytes) -> None:
    expect(preview.get("ok") is True and preview.get("dry_run") is True, "migration preview must be a dry run")
    expect(source.target_registry.read_bytes() == sentinel, "dry run must not write the target registry")
    expect(not source.target_runtime.exists(), "dry run must not create the target runtime")
    runtime_result = _first_entry(preview, "runtime_goals", label="migration preview")
    expect(runtime_result.get("copied_file_count") == 0, "dry run must copy no runtime files")
    seed = _first_entry(preview, "authority_shadow_seeds", label="migration preview")
    expect(
        seed
        == {
            "schema_version": MIGRATION_SEED_SCHEMA,
            "goal_id": source.new_goal_id,
            "attempted": False,
            "outcome": "planned",
            "reason_code": None,
        },
        "dry run must plan, not attempt, the shadow seed",
    )
    expect(source.private_marker not in json.dumps(preview, sort_keys=True), "preview must not leak private provider bytes")


def _assert_migration_executed(source: LegacyMigrationSource, executed: JsonObject) -> JsonObject:
    expect(executed.get("ok") is True and executed.get("wrote_project_registry") is True, "execute must write the registry")
    runtime_result = _first_entry(executed, "runtime_goals", label="migration execute")
    expect(runtime_result.get("copied") is True, "execute must copy the runtime goal directory")
    lease_path = source.target_runtime / "goals" / source.new_goal_id / "task-leases" / "safe-local.json"
    copied_lease = parse_json_object(lease_path.read_text(encoding="utf-8"))
    expect(copied_lease.get("goal_id") == source.new_goal_id, "copied lease must carry the migrated goal id")
    identity = (source.target_shadow_directory / "store-identity").read_text(encoding="utf-8")
    expect(identity.startswith("file:") and identity != source.old_store_identity, "target lineage must be fresh")
    store_paths = sorted(source.target_shadow_directory.glob("authority-store-*.json"))
    expect(len(store_paths) == 1, "execute must seed exactly one candidate document")
    store = parse_json_object(store_paths[0].read_text(encoding="utf-8"))
    expect(store.get("goal_id") == source.new_goal_id and store.get("store_identity") == identity, "seeded store must bind the new lineage")
    committed = store.get("committed")
    expect(store.get("cursor") == "1" and isinstance(committed, list) and len(committed) == 1, "seed must be the first and only commit")
    serialized = json.dumps(store, sort_keys=True)
    for forbidden in (source.old_store_identity, source.legacy_revision, str(source.source_repo), source.private_marker):
        expect(forbidden not in serialized, "seeded store must not carry any legacy lineage or private byte")
    expect(not (source.target_shadow_directory / "authority-store-legacy.json").exists(), "legacy document must not migrate")
    seed = _first_entry(executed, "authority_shadow_seeds", label="migration execute")
    expect(seed.get("goal_id") == source.new_goal_id and seed.get("attempted") is True, "seed must target the migrated goal")
    expect(seed.get("outcome") == "captured", "seed must be captured")
    return store


def row_migration_seeds_new_lineage(context: RowContext) -> RowOutcome:
    source = build_legacy_migration_source(
        context.root,
        old_goal_id=unique_goal_id("legacy"),
        new_goal_id=unique_goal_id("migrated"),
    )
    sentinel = b'{"schema_version":"existing","goals":[]}\n'
    source.target_registry.write_bytes(sentinel)
    arguments = _migration_arguments(source)
    _assert_migration_preview(source, run_cli(source, *arguments), sentinel)
    store = _assert_migration_executed(source, run_cli(source, *arguments, "--execute"))
    return passed(seed_outcome="captured", seeded_cursor=str(store.get("cursor")), legacy_lineage_excluded=True)


def row_dual_runtime_root_consistency(context: RowContext) -> RowOutcome:
    """``--runtime-root`` differs from ``common_runtime_root``: one lineage per goal."""

    workspace = build_goal_workspace(
        context.root,
        goal_id=unique_goal_id("ladder-one-root"),
        handoff_mode="hard_lease",
        shadow_enabled=True,
        runtime_root_binding="cli_override_divergent",
    )
    expect(
        workspace.registry_runtime_root != workspace.runtime_root,
        "fixture must register a different common_runtime_root than the override",
    )
    added = add_todo(workspace, "Every hook of one CLI call shares one runtime root.")
    todo_id = str(added["todo_id"])
    acquired = acquire_lease(
        workspace,
        todo_id=todo_id,
        owner=AGENT_A,
        idempotency_key="ladder-one-root-lease",
    )
    updated = run_cli(
        workspace, "todo", "update", "--goal-id", workspace.goal_id, "--todo-id", todo_id,
        "--note", "Observed under the override root.", "--agent-id", AGENT_A,
    )
    second_add = add_todo(workspace, "Keep one candidate lineage per goal.")
    completed = run_cli(
        workspace, "todo", "complete", "--goal-id", workspace.goal_id, "--todo-id", todo_id,
        "--agent-id", AGENT_A, "--task-lease-idempotency-key", "ladder-one-root-lease",
        "--task-lease-expected-version", lease_version(acquired, label="acquire"),
        "--evidence", "validation://ladder-one-root-complete", "--no-follow-up",
    )
    observations = [
        committed_observation(payload, label=label)
        for label, payload in (
            ("todo add", added),
            ("task-lease acquire", acquired),
            ("todo update", updated),
            ("todo add (second)", second_add),
            ("todo complete", completed),
        )
    ]
    identities = {str(evidence.get("store_identity")) for evidence in observations}
    expect(len(identities) == 1, "every writer family must observe into one store identity")
    document = candidate_document(workspace)
    expect(document.store_identity in identities, "candidate bytes must carry the observed identity")
    expect(document.cursor == str(len(observations)), "candidate cursor must equal the observation count")
    expect(
        todo_id in document.todo_ids and len(document.todo_ids) == 2,
        "head must hold the completed todo and the second added todo",
    )
    expect(
        [lease.get("todo_id") for lease in document.leases] == [todo_id]
        and document.leases[0].get("status") == "released",
        "head must hold exactly the released lease of the completed todo",
    )
    lease_path = workspace.runtime_root / "goals" / workspace.goal_id / "task-leases" / f"{todo_id}.json"
    expect(lease_path.exists(), "lease state must live under the override root")
    expect(
        not (workspace.registry_runtime_root / "authority-shadow").exists(),
        "the registry root must not gain a candidate lineage",
    )
    expect(
        not (workspace.registry_runtime_root / "goals").exists(),
        "the registry root must not gain lease state",
    )
    return passed(
        observations=len(observations),
        store_identities=len(identities),
        candidate_cursor=document.cursor,
        head_todos=len(document.todo_ids),
        head_leases=len(document.leases),
    )


__all__ = [
    "row_candidate_failure_preserves_primary",
    "row_configure_enable_disable_roundtrip",
    "row_crash_gap_loses_observation",
    "row_default_off_isolation",
    "row_dual_runtime_root_consistency",
    "row_every_writer_family_captures",
    "row_migration_seeds_new_lineage",
    "shadow_workspace",
]
