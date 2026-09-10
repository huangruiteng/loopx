"""Runner policy tests never start a real model, including under ordinary CI."""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release_goal", REPO / "scripts/qualify-native-goal-release.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_default_does_not_even_probe_model_environment(monkeypatch, capsys):
    def forbidden(*args):
        raise AssertionError("default must not touch a model host")
    monkeypatch.setattr(runner, "prerequisite_failure", forbidden)
    monkeypatch.setattr(runner, "qualify", forbidden)
    assert runner.main([]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "skipped", "reason": "release_opt_in_required", "model_executed": False}


def test_missing_release_environment_is_explicit_skip(monkeypatch, capsys):
    monkeypatch.setattr(runner, "prerequisite_failure", lambda _: "codex_auth_unavailable")
    assert runner.main(["--release-live"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "skipped"


def test_attempted_release_failure_is_not_converted_to_skip(monkeypatch, capsys):
    monkeypatch.setattr(runner, "prerequisite_failure", lambda _: None)
    def failing(*args):
        raise RuntimeError("sensitive diagnostic sentinel")
    monkeypatch.setattr(runner, "qualify", failing)
    assert runner.main(["--release-live"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "failed", "error_kind": "RuntimeError"}


def test_release_timeout_must_be_positive():
    with pytest.raises(SystemExit):
        runner.main(["--timeout-seconds", "0"])


def test_synthetic_fixture_real_cli_projects_identity_reentry(tmp_path):
    project, _, launcher = runner.setup(tmp_path)
    assert (project / "TASK.md").read_bytes() == (runner.FIXTURE / "TASK.md").read_bytes()
    quota = runner.cli(launcher, "quota", "should-run", "--runtime-profile", "codex_cli",
                       "--goal-id", runner.GOAL, "--agent-id", runner.AGENT)
    assert quota["should_run"] is True
    assert quota["selected_todo"]["todo_id"] == "todo_reducer"
    actions = quota["interaction_contract"]["cli_channel"]["next_cli_actions"]
    assert len(actions) == 1 and "--turn-instance-id" in actions[0]
    assert "spend-slot" not in actions[0]

    # Qualify the fixture's terminal shape without paying for a model run. A
    # missing user section is not proof of zero user obligations.
    state = project / "ACTIVE_GOAL_STATE.md"
    state.write_text(state.read_text().replace("- [ ]", "- [x]").replace(
        "status=open", "status=done no_followup=true",
    ))
    terminal = runner.cli(launcher, "quota", "should-run", "--runtime-profile", "codex_cli",
                          "--goal-id", runner.GOAL, "--agent-id", runner.AGENT)
    assert terminal["should_run"] is False
    assert terminal["interaction_contract"]["mode"] == "terminal_no_followup"

    state.write_text(state.read_text().replace("## User Todo\n\n", ""))
    incomplete = runner.cli(launcher, "quota", "should-run", "--runtime-profile", "codex_cli",
                            "--goal-id", runner.GOAL, "--agent-id", runner.AGENT)
    assert incomplete["interaction_contract"]["mode"] != "terminal_no_followup"


@pytest.mark.parametrize("mutation", ["unbound", "duplicate"])
def test_settlement_oracle_rejects_missing_identity_and_duplicate_spend(tmp_path, mutation):
    rows = [{"classification": "quota_slot_spent", "todo_id": todo,
             "settlement_identity": {"effect_id": todo}} for todo in sorted(runner.TODOS)]
    if mutation == "unbound":
        rows.append({"classification": "quota_slot_spent"})
    else:
        rows.append(rows[0].copy())
    index = tmp_path / "goals" / runner.GOAL / "runs/index.jsonl"
    index.parent.mkdir(parents=True)
    index.write_text("\n".join(json.dumps(row) for row in rows))
    todos = [{"todo_id": todo, "status": "done"} for todo in runner.TODOS]
    with pytest.raises(AssertionError):
        runner.verify_settlement(tmp_path, todos)
