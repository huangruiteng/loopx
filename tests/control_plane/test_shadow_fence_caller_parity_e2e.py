"""Fenced sibling-caller parity through the real CLI (Stage 2C E2E).

Every row runs one public command against a workspace whose durable legacy
writer fence is in one state, and compares the complete printed envelope, the
exit status, and the primary-record effect with the literal expectation in
tests/fixtures/control_plane/legacy_writer_fence_caller_parity_v0.json.
Nothing is mocked; the fence is engaged by the real TypeScript owner.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
import json
from pathlib import Path
import shutil
import sys

import pytest

from test_shadow_observable_e2e import Caller
from test_shadow_observable_native_e2e import native

pytestmark = pytest.mark.stage2c_e2e

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "control_plane" / "legacy_writer_fence_caller_parity_v0.json"
BUILDER = (
    "from loopx.control_plane.coordination.runtime_shadow import build_todo_runtime_shadow_projection as build; "
    "import json,sys; value=build(goal_id='observable', todos=json.loads(sys.argv[1])); "
    "value['handoff_mode']='hard_lease'; print(json.dumps(value))"
)
PLACEHOLDERS = ("runtime_root", "todo_a", "todo_b", "todo_gate")


class Workspace:
    """One seeded goal; rows are executed against it in fixture order."""

    def __init__(self, path: Path, mode: str, name: str) -> None:
        self.w = Caller(path, mode, name)
        self.ids: dict[str, str] = {}
        self.lease_version = 0
        self.control: dict[str, dict] | None = None

    def call(self, *args: str) -> dict:
        return self.w.call(*args)

    def exit(self) -> int:
        return int(self.w.rows[-1]["exit"])

    def outbox(self) -> set[str]:
        return {k for k in self.w.files() if k.startswith("runtime/authority-shadow/outbox/")}

    def fence_path(self) -> Path:
        from loopx.control_plane.coordination.legacy_writer_fence import legacy_coordination_writer_fence_path

        return legacy_coordination_writer_fence_path(runtime_root=self.w.root, goal_id="observable")

    def normalize(self, value: object) -> object:
        text = json.dumps(value)
        text = text.replace(json.dumps(str(self.w.root))[1:-1], "{runtime_root}")
        for key in ("todo_gate", "todo_b", "todo_a"):
            if key in self.ids:
                text = text.replace(self.ids[key], "{" + key + "}")
        return json.loads(text)

    def observe(self, args: tuple[str, ...]) -> dict:
        before, outbox_before = self.w.primary(), self.outbox()
        envelope = self.call(*args)
        after, outbox_after = self.w.primary(), self.outbox()
        return {
            "envelope": self.normalize(envelope),
            "exit": self.exit(),
            "effect": {
                "added": sorted(k for k in after if k not in before),
                "removed": sorted(k for k in before if k not in after),
                "changed": sorted(k for k in after if k in before and after[k] != before[k]),
            },
            "outbox_added": sorted(outbox_after - outbox_before),
        }


def seed_and_fence(ws: Workspace, todo_keys: tuple[str, ...]) -> None:
    records = [ws.w.read(ws.ids[key]) for key in todo_keys]
    projection = ws.w.invoke(
        [sys.executable, "-c", BUILDER, json.dumps(records)], ["fixture-projection", json.dumps(records)]
    )
    assert native(ws.w, "seed", projection)["status"] == "applied"


def build_seeded(path: Path, mode: str, name: str, *, gate: bool) -> Workspace:
    ws = Workspace(path, mode, name)
    assert ws.call("handoff-mode", "set", "--mode", "hard_lease")["ok"] is True
    ws.ids["todo_a"] = ws.w.add("Parity target A")
    ws.ids["todo_b"] = ws.w.add("Parity leased B")
    if gate:
        gate_add = ws.call("todo", "add", "--role", "user", "--task-class", "user_gate", "--global-gate",
                           "--text", "Approve the parity plan")
        assert gate_add["ok"] is True, gate_add
        ws.ids["todo_gate"] = gate_add["todo_id"]
    ws.control = {"cli-task_lease_acquire-absent": ws.observe((
        "task-lease", "acquire", "--todo-id", ws.ids["todo_b"], "--owner", "agent-a",
        "--idempotency-key", "parity-lease", "--ttl-seconds", "3600"))}
    lease = ws.control["cli-task_lease_acquire-absent"]["envelope"]
    assert lease.get("acquired") is True, lease
    ws.lease_version = int(lease["lease"]["version"])
    seed_and_fence(ws, ("todo_a", "todo_b", "todo_gate") if gate else ("todo_a", "todo_b"))
    return ws


def build_w3(path: Path) -> Workspace:
    ws = build_seeded(path, "absent", "fence-parity-invalid", gate=False)
    marker = json.loads(ws.fence_path().read_text(encoding="utf-8"))
    marker["state"] = "disengaged"
    ws.fence_path().write_text(json.dumps(marker), encoding="utf-8")
    return ws


def build_w4(path: Path) -> Workspace:
    ws = build_seeded(path, "absent", "fence-parity-unreadable", gate=False)
    ws.fence_path().unlink()
    ws.fence_path().mkdir()
    return ws


def build_w5(path: Path) -> Workspace:
    ws = Workspace(path, "absent", "fence-parity-no-store")
    assert ws.call("handoff-mode", "set", "--mode", "hard_lease")["ok"] is True
    ws.ids["todo_a"] = ws.w.add("Parity target A")
    ws.fence_path().parent.mkdir(parents=True, exist_ok=True)
    ws.fence_path().write_text(json.dumps({
        "schema_version": "loopx_legacy_coordination_writer_fence_v0", "state": "engaged", "goal_id": "observable",
        "fence_id": "caller-fixture", "source_version": "caller-fixture",
        "source_projection_sha256": "a" * 64, "expected_shadow_provider_revision": "file:1:aaaaaaaaaaaaaaaaaaaaaaaa",
    }), encoding="utf-8")
    return ws


def lease_args(ws: Workspace, verb: str) -> tuple[str, ...]:
    todo_b, version = ws.ids.get("todo_b", ""), str(ws.lease_version)
    if verb == "acquire":
        return ("task-lease", "acquire", "--todo-id", ws.ids.get("todo_a", ""), "--owner", "agent-a",
                "--idempotency-key", "parity-acquire", "--ttl-seconds", "3600")
    common = ("task-lease", verb, "--todo-id", todo_b, "--owner", "agent-a",
              "--idempotency-key", "parity-lease", "--expected-version", version)
    if verb == "renew":
        return (*common, "--ttl-seconds", "7200")
    if verb == "transfer":
        return (*common, "--new-owner", "agent-b", "--new-idempotency-key", "parity-transfer")
    return common


def row_args(ws: Workspace, caller: str) -> tuple[str, ...]:
    a = ws.ids.get("todo_a", "")
    b = ws.ids.get("todo_b", "")
    gate = ws.ids.get("todo_gate", "")
    version = str(ws.lease_version)
    table: dict[str, tuple[str, ...]] = {
        "task_lease_acquire": lease_args(ws, "acquire"),
        "task_lease_renew": lease_args(ws, "renew"),
        "task_lease_transfer": lease_args(ws, "transfer"),
        "task_lease_release": lease_args(ws, "release"),
        "todo_complete": ("todo", "complete", "--todo-id", a, "--agent-id", "agent-a",
                          "--evidence", "validation://parity", "--no-follow-up"),
        "todo_update_status": ("todo", "update", "--todo-id", a, "--agent-id", "agent-a", "--status", "deferred"),
        "todo_supersede": ("todo", "supersede", "--todo-id", a, "--agent-id", "agent-a",
                           "--text", "Parity successor", "--evidence", "validation://parity"),
        "todo_archive_completed_execute": ("todo", "archive-completed", "--execute"),
        "todo_archive_completed_preview": ("todo", "archive-completed"),
        "todo_capture_followups": ("todo", "capture-followups", "--follow-up", "Parity follow-up.",
                                   "--evidence", "parity fixture"),
        "todo_capture_followups_dry_run": ("todo", "capture-followups", "--follow-up", "Parity follow-up.",
                                           "--evidence", "parity fixture", "--dry-run"),
        "handoff_mode_set": ("handoff-mode", "set", "--mode", "soft_claim"),
        "todo_complete_dry_run_gate": ("todo", "complete", "--todo-id", gate, "--agent-id", "agent-a",
                                       "--decision-outcome", "approve", "--evidence", "validation://parity",
                                       "--no-follow-up", "--dry-run"),
        "todo_supersede_dry_run": ("todo", "supersede", "--todo-id", a, "--agent-id", "agent-a",
                                   "--text", "Parity successor", "--evidence", "validation://parity", "--dry-run"),
        "todo_complete_dry_run_leased": ("todo", "complete", "--todo-id", b, "--agent-id", "agent-a",
                                         "--task-lease-idempotency-key", "parity-lease",
                                         "--task-lease-expected-version", version,
                                         "--evidence", "validation://parity", "--no-follow-up", "--dry-run"),
    }
    return table[caller]


WORKSPACES = {
    "w1": lambda path: build_seeded(path, "absent", "fence-parity-engaged", gate=True),
    "w2": lambda path: build_seeded(path, "enabled", "fence-parity-engaged-capture", gate=False),
    "w3": build_w3,
    "w4": build_w4,
    "w5": build_w5,
}


def load_rows() -> list[dict]:
    if not FIXTURE.exists():
        # Keep the module importable for the fixture recorder; the test itself fails loudly.
        return [{"id": "fixture-missing", "surface": "cli", "workspace": None}]
    return [row for row in json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"] if row["surface"] == "cli"]


@pytest.fixture(scope="module")
def workspaces(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Callable[[str], Workspace]]:
    built: dict[str, Workspace] = {}

    def get(key: str) -> Workspace:
        # Single-row mutation probes need only this row's workspace. Keep reuse
        # and ordered mutations within a module, never across worker processes.
        if key not in built:
            built[key] = WORKSPACES[key](tmp_path_factory.mktemp(key))
        return built[key]

    yield get
    for ws in built.values():
        shutil.rmtree(ws.w.path, ignore_errors=True)


def observe_row(ws: Workspace, row: dict) -> dict:
    if ws.control and row["id"] in ws.control:
        return ws.control[row["id"]]
    return ws.observe(row_args(ws, row["caller"]))


@pytest.mark.parametrize("row", load_rows(), ids=[row["id"] for row in load_rows()])
def test_fence_caller_parity(workspaces: Callable[[str], Workspace], row: dict) -> None:
    if row["id"] == "fixture-missing":
        pytest.fail(f"parity fixture is missing: {FIXTURE}")
    observed = observe_row(workspaces(row["workspace"]), row)
    assert observed["exit"] == row["exit"], observed
    if row.get("match") == "subset":
        assert {key: observed["envelope"].get(key) for key in row["expect"]} == row["expect"], observed
    else:
        assert observed["envelope"] == row["expect"], observed
    assert observed["effect"] == row["effect"], observed
    assert observed["outbox_added"] == row.get("outbox_added", []), observed


def test_baseline_annotations_are_not_stale() -> None:
    for row in load_rows():
        for revision, delta in (row.get("baseline") or {}).items():
            if revision == "note":
                continue
            assert delta != row["expect"], row["id"]
