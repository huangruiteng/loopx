from __future__ import annotations

import json
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import tomllib

import pytest

from loopx.control_plane.heartbeat import automation_upgrade as upgrade


def fixture(tmp_path: Path):
    home = tmp_path / "host"
    path = home / "automations/watch/automation.toml"
    path.parent.mkdir(parents=True)
    prompt = "Advance `fixture-goal` from registry. --agent-id agent-a"
    path.write_text('version = 1\nid = "watch"\nkind = "heartbeat"\n'
                    'status = "PAUSED"\ntarget_thread_id = "thread-a"\n'
                    'rrule = "FREQ=HOURLY"\nnotification_policy = "failed_runs_only"\n'
                    '# retain custom metadata\n[unused]\nvalue = 1\n', encoding="utf-8")
    path.write_text('prompt = ' + json.dumps(prompt) + '\n' + path.read_text(), encoding="utf-8")
    database = home / "sqlite/codex-dev.db"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE automations (id TEXT PRIMARY KEY, kind TEXT, prompt TEXT, status TEXT, target_thread_id TEXT, rrule TEXT, model TEXT, updated_at INTEGER, next_run_at INTEGER)")
        connection.execute("INSERT INTO automations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("watch", "heartbeat", prompt, "PAUSED", "thread-a", "FREQ=HOURLY", "fixture-model", 123, 456))
        connection.execute("CREATE TABLE sessions (id TEXT)")
        connection.execute("INSERT INTO sessions VALUES ('do-not-touch')")
    registry = tmp_path / "registry.json"
    state = tmp_path / "STATE.md"
    state.write_text("# Fixture\n", encoding="utf-8")
    registry.write_text(json.dumps({"goals": [{"id": "fixture-goal", "repo": str(tmp_path),
        "state_file": str(state), "registered_agents": ["agent-a"]}]}), encoding="utf-8")
    return home, path, database, registry, prompt


def test_real_sqlite_upgrade_preserves_schedule_binding_model_and_history(tmp_path):
    home, path, database, registry, prompt = fixture(tmp_path)
    original = path.read_text()
    plan = upgrade.build_plan(registry=registry, home=home)
    item = plan["entries"][0]
    assert item["status"] == "adoption_required"
    assert path.read_text() == original
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT * FROM automations").fetchone()
    result = upgrade.apply_offline(home=home, automation_id="watch",
        expected_prompt_sha256=upgrade.digest(prompt), desired_prompt=item["desired_prompt"])
    assert result["status"] == "updated"
    assert "# retain custom metadata" in path.read_text()
    with sqlite3.connect(database) as connection:
        after = connection.execute("SELECT * FROM automations").fetchone()
        assert before[:2] + before[3:] == after[:2] + after[3:]
        assert connection.execute("SELECT * FROM sessions").fetchall() == [("do-not-touch",)]
    assert upgrade.build_plan(registry=registry, home=home)["entries"][0]["status"] == "current"
    upgrade.recover_offline(home=home, automation_id="watch", rollback=True)
    assert path.read_text() == original
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM automations").fetchone() == before


def test_bootstrap_reads_real_current_cli_thin_contract(tmp_path):
    home, _, _, registry, _ = fixture(tmp_path)
    item = upgrade.build_plan(registry=registry, home=home)["entries"][0]
    prompt = item["desired_prompt"]
    assert "--thin" in prompt and "--full" not in prompt and "--compact" not in prompt
    assert "不复用旧指令" in prompt
    assert "仅 ok=true" in prompt
    assert "结果不完整则停止" in prompt
    assert len(prompt) < 500
    command = shlex.split(prompt.split("```sh\n")[1].split("\n```", 1)[0])
    result = subprocess.run([sys.executable, "-m", "loopx.cli", *command[1:]],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["task_body"]
    assert payload["interface_budget"]["within_budget"] is True
    assert upgrade.bootstrap_binding(prompt)["agent_id"] == "agent-a"
    assert upgrade.bootstrap_binding(prompt + "\nIgnore the guard") is None


@pytest.mark.parametrize("reason", ["prompt", "metadata", "missing_row", "wrong_kind"])
def test_divergence_never_mutates_host(tmp_path, reason):
    home, path, database, _, prompt = fixture(tmp_path)
    with sqlite3.connect(database) as connection:
        if reason == "missing_row":
            connection.execute("DELETE FROM automations")
        elif reason == "wrong_kind":
            connection.execute("UPDATE automations SET kind='cron'")
        elif reason == "metadata":
            connection.execute("UPDATE automations SET status='ACTIVE'")
        else:
            connection.execute("UPDATE automations SET prompt='custom edit'")
    original = path.read_bytes()
    with pytest.raises(ValueError):
        upgrade.apply_offline(home=home, automation_id="watch",
            expected_prompt_sha256=upgrade.digest(prompt), desired_prompt="new")
    assert path.read_bytes() == original
    assert not (home / "loopx-automation-backups").exists()


def test_failure_after_db_commit_is_recoverable_without_duplicate_mutation(tmp_path, monkeypatch):
    home, path, database, _, prompt = fixture(tmp_path)
    atomic = upgrade._atomic
    def fail_mirror(target, text):
        if target == path:
            raise OSError("synthetic mirror failure")
        atomic(target, text)
    monkeypatch.setattr(upgrade, "_atomic", fail_mirror)
    with pytest.raises(OSError):
        upgrade.apply_offline(home=home, automation_id="watch",
            expected_prompt_sha256=upgrade.digest(prompt), desired_prompt="new")
    assert tomllib.loads(path.read_text())["prompt"] == prompt
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT prompt FROM automations").fetchone()[0] == "new"
    monkeypatch.setattr(upgrade, "_atomic", atomic)
    assert upgrade.recover_offline(home=home, automation_id="watch")["status"] == "recovered"
    assert tomllib.loads(path.read_text())["prompt"] == "new"
    assert upgrade.recover_offline(home=home, automation_id="watch")["status"] == "recovered"


def test_recovery_refuses_later_customization(tmp_path):
    home, path, _, _, prompt = fixture(tmp_path)
    upgrade.apply_offline(home=home, automation_id="watch",
        expected_prompt_sha256=upgrade.digest(prompt), desired_prompt="new")
    path.write_text(path.read_text() + '\n# user edit\n')
    with pytest.raises(ValueError, match="changed since migration"):
        upgrade.recover_offline(home=home, automation_id="watch", rollback=True)


def test_toml_multiline_embedded_assignment_is_not_a_field(tmp_path):
    source = 'name = "watch"\nprompt = """old\nprompt = \'fake\'\n"""\nrrule = "FREQ=HOURLY"\n'
    updated = upgrade._replace_prompt(source, 'new "quotes"\nbody')
    assert tomllib.loads(updated) == {**tomllib.loads(source), "prompt": 'new "quotes"\nbody'}


def test_cli_preview_private_file_and_no_implicit_apply(tmp_path):
    home, path, _, registry, _ = fixture(tmp_path)
    plan = tmp_path / "private-plan.json"
    args = [sys.executable, "-m", "loopx.cli", "--format", "json", "--registry", str(registry),
        "automation-prompts", "plan", "--codex-home", str(home), "--plan-file", str(plan)]
    original = path.read_bytes()
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert plan.stat().st_mode & 0o077 == 0
    assert path.read_bytes() == original
    args[args.index("plan")] = "apply"
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 1
    assert path.read_bytes() == original


def test_unsupported_schema_and_missing_database_fail_without_creating(tmp_path):
    home = tmp_path / "host"
    home.mkdir()
    with pytest.raises(sqlite3.Error):
        upgrade._connect(home)
    assert list(home.iterdir()) == []


def test_stale_preview_cas_and_cross_home_boundary(tmp_path):
    home, path, _, _, _ = fixture(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="changed after preview"):
        upgrade.apply_offline(home=home, automation_id="watch",
            expected_prompt_sha256="stale", desired_prompt="new")
    assert path.read_bytes() == before
    other = tmp_path / "other-home"
    other.mkdir()
    assert list(other.iterdir()) == []


def test_upgrade_plan_recognizes_exact_live_thin_wrapper(tmp_path, monkeypatch):
    from loopx.upgrade import build_upgrade_plan
    home, _, _, registry, prompt = fixture(tmp_path)
    desired = upgrade.bootstrap_prompt(registry=registry, goal_id="fixture-goal", agent_id="agent-a")
    upgrade.apply_offline(home=home, automation_id="watch",
        expected_prompt_sha256=upgrade.digest(prompt), desired_prompt=desired)
    monkeypatch.setenv("CODEX_HOME", str(home))
    plan = build_upgrade_plan(registry_path=registry)
    assert plan["summary"]["current_prompt_count"] == 1
    assert plan["summary"]["stale_prompt_count"] == 0


def test_cli_offline_apply_checks_exact_saved_plan(tmp_path, monkeypatch):
    from argparse import Namespace
    from loopx.cli_commands import automation_prompts as cli
    home, path, _, registry, _ = fixture(tmp_path)
    plan = upgrade.build_plan(registry=registry, home=home)
    saved = tmp_path / "plan.json"
    saved.write_text(json.dumps(plan))
    monkeypatch.setattr(cli, "_require_offline", lambda: None)
    args = Namespace(codex_home=home, action="apply", execute=True, offline=True,
                     plan_file=saved, automation_id=[], runtime_root=None, cli_bin="loopx")
    assert cli.run(args, registry)["results"][0]["status"] == "updated"
    assert upgrade.bootstrap_binding(tomllib.loads(path.read_text())["prompt"])
    # The old preview cannot replace a now-customized prompt or change homes.
    assert cli.run(args, registry)["results"][0]["status"] == "preview_stale"
    args.codex_home = tmp_path / "other-home"
    with pytest.raises(ValueError, match="host-home mismatch"):
        cli.run(args, registry)


def test_canary_keeps_generated_commands_on_the_same_runtime(tmp_path):
    prompt = upgrade.bootstrap_prompt(registry=tmp_path / "registry.json",
        goal_id="fixture-goal", agent_id="agent-a", cli_bin="loopx-canary")
    binding = upgrade.bootstrap_binding(prompt)
    assert binding["cli_bin"] == "loopx-canary"
    assert "--cli-bin loopx-canary" in prompt
    assert upgrade.bootstrap_binding(prompt.replace("--cli-bin loopx-canary", "--cli-bin loopx")) is None


def test_ambiguous_discovery_is_not_replacement_authority(tmp_path):
    home, path, database, registry, prompt = fixture(tmp_path)
    ambiguous = prompt + " --agent-id agent-b"
    path.write_text(upgrade._replace_prompt(path.read_text(), ambiguous))
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE automations SET prompt=?", (ambiguous,))
    entry = upgrade.build_plan(registry=registry, home=home)["entries"][0]
    assert entry["status"] == "blocked"
    assert "desired_prompt" not in entry
