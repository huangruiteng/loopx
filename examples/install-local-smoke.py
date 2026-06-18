#!/usr/bin/env python3
"""Smoke-test local installer wrapper and skill installation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-local.sh"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.doctor import add_promotion_readiness_freshness  # noqa: E402


def run_install(env: dict[str, str], release_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALL_SCRIPT)],
        cwd=REPO_ROOT,
        env={**env, "GOAL_HARNESS_RELEASE_ID": release_id},
        check=True,
        capture_output=True,
        text=True,
    )


def write_promotion_readiness(
    runtime_run_dir: Path,
    *,
    generated_at: str,
    label: str,
) -> dict[str, str]:
    runtime_run_dir.mkdir(parents=True, exist_ok=True)
    readiness_json = runtime_run_dir / f"2026-01-01T00-00-00-{label}-canary-promotion-readiness.json"
    readiness_markdown = runtime_run_dir / f"2026-01-01T00-00-00-{label}-canary-promotion-readiness.md"
    readiness_record = {
        "generated_at": generated_at,
        "goal_id": "goal-harness-meta",
        "classification": "canary_promotion_readiness_smoke_group",
        "delivery_batch_scale": "multi_surface",
        "delivery_outcome": "primary_goal_outcome",
        "recommended_action": f"fixture {label} promotion readiness evidence",
        "json_path": str(readiness_json),
        "markdown_path": str(readiness_markdown),
    }
    readiness_json.write_text(json.dumps(readiness_record, indent=2, sort_keys=True), encoding="utf-8")
    readiness_markdown.write_text("# Canary promotion readiness\n", encoding="utf-8")
    (runtime_run_dir / "index.jsonl").write_text(json.dumps(readiness_record, sort_keys=True) + "\n", encoding="utf-8")
    return readiness_record


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-install-smoke-") as tmp:
        root = Path(tmp)
        home = root / "home"
        home.mkdir()
        bin_dir = home / ".local" / "bin"
        codex_home = home / ".codex"
        profile = home / ".zshrc"
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "GOAL_HARNESS_BIN_DIR": str(bin_dir),
            "GOAL_HARNESS_SHELL_PROFILE": str(profile),
            "GOAL_HARNESS_INSTALL_SKILL": "1",
            "PATH": os.environ.get("PATH", ""),
            "SHELL": "/bin/zsh",
        }

        install = run_install(env, "install-smoke-initial")
        assert "goal-harness installed locally" in install.stdout, install.stdout
        assert "promotion-readiness evidence is missing" in install.stderr, install.stderr
        assert "non-blocking" in install.stderr, install.stderr
        assert "examples/canary-promotion-readiness-smoke.py" in install.stderr, install.stderr
        assert f"- executable: {bin_dir / 'goal-harness'}" in install.stdout, install.stdout
        assert "- release: " in install.stdout, install.stdout
        assert f"- canary executable: {bin_dir / 'goal-harness-canary'}" in install.stdout, install.stdout
        assert f"- skill: {codex_home / 'skills' / 'goal-harness-doc-registry'}" in install.stdout, install.stdout
        assert f"- skill: {codex_home / 'skills' / 'goal-harness-project'}" in install.stdout, install.stdout
        assert f"- skill: {codex_home / 'skills' / 'goal-harness-self-repair'}" in install.stdout, install.stdout

        wrapper = bin_dir / "goal-harness"
        assert wrapper.is_symlink(), wrapper
        assert wrapper.resolve() != REPO_ROOT / "scripts" / "goal-harness", wrapper.resolve()
        assert wrapper.resolve().name == "goal-harness", wrapper.resolve()
        release_root = wrapper.resolve().parents[1]
        assert (release_root / "goal_harness" / "cli.py").is_file(), release_root
        canary_wrapper = bin_dir / "goal-harness-canary"
        assert canary_wrapper.is_symlink(), canary_wrapper
        assert canary_wrapper.resolve() == REPO_ROOT / "scripts" / "goal-harness", canary_wrapper.resolve()
        assert profile.read_text(encoding="utf-8").count("Goal Harness local CLI") == 1, profile.read_text()

        skill = codex_home / "skills" / "goal-harness-project" / "SKILL.md"
        assert not skill.parent.is_symlink(), skill.parent
        skill_text = skill.read_text(encoding="utf-8")
        compact_skill_text = " ".join(skill_text.split())
        for phrase in (
            "Set Up Recurring Heartbeats",
            "goal-harness heartbeat-prompt",
            "run a short steering audit before choosing work",
            "at least three plausible next-action candidates",
            "continuation check",
            "compute quota separate from focus quota",
            "Register Project Authority And Material Sources",
            "doc-registry skill trigger",
            "Diagnose For The User",
            "goal-harness diagnose",
            "Use those signals as evidence",
            "Identify the target project and goal first",
            "goal-harness register-authority-source",
            "goal-harness import-doc-registry-authority",
            "--source heartbeat --execute",
            "Generate A Review Packet",
            "goal-harness review-packet --goal-id",
            "goal-harness review-packet --goal-id <STABLE_GOAL_ID> --handoff-only",
            "goal-harness --format json review-packet --goal-id",
            "target project agent must not run this draft",
            "This command is read-only",
            "JSON output returns a minimized handoff payload with `handoff_text` instead of the full operator packet",
            "--classification <PUBLIC_SAFE_PROGRESS_CLASSIFICATION>",
            "--delivery-batch-scale multi_surface",
            "--delivery-outcome outcome_progress",
            "do not infer scale/outcome from the classification name",
        ):
            assert phrase in compact_skill_text, phrase
        assert "JSON output still keeps the full payload" not in compact_skill_text, compact_skill_text
        doc_registry_skill = codex_home / "skills" / "goal-harness-doc-registry" / "SKILL.md"
        doc_registry_text = " ".join(doc_registry_skill.read_text(encoding="utf-8").split())
        for phrase in (
            "Use even when the user does not mention Goal Harness or doc registry",
            "use `.goal-harness/registry.json` as the project-local doc registry",
            "not a substitute for project-local authority registration",
            "goal-harness --registry .goal-harness/registry.json register-authority-source",
        ):
            assert phrase in doc_registry_text, phrase
        self_repair_skill = codex_home / "skills" / "goal-harness-self-repair" / "SKILL.md"
        self_repair_text = " ".join(self_repair_skill.read_text(encoding="utf-8").split())
        for phrase in (
            "Build a compact evidence packet",
            "references/repair-patterns.md",
            "Repair at the lowest durable layer",
            "Do not solve contradictory payloads by guessing",
        ):
            assert phrase in self_repair_text, phrase
        self_repair_patterns = (
            codex_home
            / "skills"
            / "goal-harness-self-repair"
            / "references"
            / "repair-patterns.md"
        )
        self_repair_patterns_text = self_repair_patterns.read_text(encoding="utf-8")
        assert "`boundary_projection_gap`" in self_repair_patterns_text, self_repair_patterns_text
        assert "`tiny_turn_under_delivery`" in self_repair_patterns_text, self_repair_patterns_text
        assert (
            codex_home / "skills" / "goal-harness-self-repair" / "agents" / "openai.yaml"
        ).is_file()

        cli_env = {**env, "PATH": f"{bin_dir}:{env['PATH']}"}
        runtime_run_dir = home / ".codex" / "goal-harness" / "goals" / "goal-harness-meta" / "runs"
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        write_promotion_readiness(runtime_run_dir, generated_at=generated_at, label="fresh")

        doctor = subprocess.run(
            ["goal-harness", "--format", "json", "doctor"],
            cwd=root,
            env=cli_env,
            check=True,
            capture_output=True,
            text=True,
        )
        doctor_payload = json.loads(doctor.stdout)
        assert doctor_payload["ok"] is True, doctor_payload
        assert doctor_payload["path"]["goal_harness"] == str(wrapper), doctor_payload
        assert doctor_payload["path"]["goal_harness_realpath"] == str(wrapper.resolve()), doctor_payload
        assert doctor_payload["path"]["goal_harness_canary"] == str(canary_wrapper), doctor_payload
        assert doctor_payload["path"]["goal_harness_canary_realpath"] == str(canary_wrapper.resolve()), doctor_payload
        assert doctor_payload["package"]["release_root"] == str(release_root), doctor_payload
        assert doctor_payload["skill"]["path"] == str(skill), doctor_payload
        assert doctor_payload["skill"]["exists"] is True, doctor_payload
        assert doctor_payload["skill"]["delivery_hints"] is True, doctor_payload
        assert doctor_payload["skills"]["goal-harness-project"]["exists"] is True, doctor_payload
        assert doctor_payload["skills"]["goal-harness-project"]["required_phrases"] is True, doctor_payload
        assert doctor_payload["skills"]["goal-harness-doc-registry"]["exists"] is True, doctor_payload
        assert doctor_payload["skills"]["goal-harness-doc-registry"]["required_phrases"] is True, doctor_payload
        assert doctor_payload["skills"]["goal-harness-self-repair"]["exists"] is True, doctor_payload
        assert doctor_payload["skills"]["goal-harness-self-repair"]["required_phrases"] is True, doctor_payload
        provenance = doctor_payload["release_provenance"]
        assert provenance["default_release"]["root"] == str(release_root), provenance
        assert provenance["default_release"]["release_id"] == release_root.name, provenance
        assert provenance["default_release"]["is_release_snapshot"] is True, provenance
        assert provenance["live_canary"]["root"] == str(REPO_ROOT), provenance
        assert provenance["live_canary"]["separate_from_default"] is True, provenance
        assert provenance["current_invocation"]["source"] == "release_snapshot", provenance
        assert provenance["promotion_readiness"]["available"] is True, provenance
        assert provenance["promotion_readiness"]["goal_id"] == "goal-harness-meta", provenance
        assert provenance["promotion_readiness"]["classification"] == "canary_promotion_readiness_smoke_group", provenance
        assert provenance["promotion_readiness"]["delivery_outcome"] == "primary_goal_outcome", provenance
        assert provenance["promotion_readiness"]["freshness_status"] == "fresh", provenance
        assert provenance["promotion_readiness"]["is_fresh"] is True, provenance
        assert provenance["promotion_readiness"]["requires_readiness_run"] is False, provenance
        assert provenance["promotion_readiness"]["freshness_window_hours"] == 24, provenance
        assert provenance["promotion_readiness"]["json_exists"] is True, provenance
        assert provenance["promotion_readiness"]["markdown_exists"] is True, provenance
        doctor_checks = {check["id"]: check for check in doctor_payload["checks"]}
        for check_id in (
            "default_command_is_release_snapshot",
            "canary_command_on_path",
            "canary_separate_from_default",
            "installed_skill_exists",
            "installed_skill_delivery_hints",
            "installed_required_skills",
            "installed_required_skill_routes",
        ):
            assert doctor_checks[check_id]["ok"] is True, doctor_payload

        doctor_markdown = subprocess.run(
            ["goal-harness", "doctor"],
            cwd=root,
            env=cli_env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "installed_skill_delivery_hints: `True`" in doctor_markdown, doctor_markdown
        assert (
            "installed_required_skills: "
            "`goal-harness-doc-registry,goal-harness-project,goal-harness-self-repair`"
            in doctor_markdown
        ), doctor_markdown
        assert "canary_realpath:" in doctor_markdown, doctor_markdown
        assert "release_root:" in doctor_markdown, doctor_markdown
        assert "## Release Provenance" in doctor_markdown, doctor_markdown
        assert "latest_promotion_readiness: available=`True`" in doctor_markdown, doctor_markdown
        assert "freshness=`fresh`" in doctor_markdown, doctor_markdown
        assert "requires_readiness_run=`False`" in doctor_markdown, doctor_markdown

        stale = add_promotion_readiness_freshness(
            {
                "available": True,
                "generated_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
            }
        )
        assert stale["freshness_status"] == "stale", stale
        assert stale["is_fresh"] is False, stale
        assert stale["requires_readiness_run"] is True, stale
        missing = add_promotion_readiness_freshness({"available": False})
        assert missing["freshness_status"] == "missing", missing
        assert missing["requires_readiness_run"] is True, missing

        cli = subprocess.run(
            [
                "goal-harness",
                "--format",
                "json",
                "heartbeat-prompt",
                "--goal-id",
                "installer-smoke-goal",
                "--active-state",
                "/tmp/public-installer-smoke/ACTIVE_GOAL_STATE.md",
            ],
            cwd=REPO_ROOT,
            env=cli_env,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(cli.stdout)
        assert payload["ok"] is True, payload
        assert payload["quota_guard_command"] == (
            'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" '
            "quota should-run --goal-id installer-smoke-goal"
        ), payload
        assert payload["quota_spend_command"] == (
            'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" '
            "quota spend-slot --goal-id installer-smoke-goal --slots 1 --source heartbeat --execute"
        ), payload
        assert "--delivery-batch-scale multi_surface" in payload["task_body"], payload
        assert "--delivery-outcome outcome_progress" in payload["task_body"], payload
        assert "<PUBLIC_SAFE_PROGRESS_CLASSIFICATION>" in payload["task_body"], payload
        assert "DONT_NOTIFY" in payload["task_body"], payload
        assert payload["cli_bin"] == "goal-harness", payload

        canary_cli = subprocess.run(
            [
                "goal-harness-canary",
                "--format",
                "json",
                "heartbeat-prompt",
                "--goal-id",
                "installer-canary-smoke-goal",
                "--active-state",
                "/tmp/public-installer-canary-smoke/ACTIVE_GOAL_STATE.md",
                "--brief",
                "--cli-bin",
                "goal-harness-canary",
            ],
            cwd=REPO_ROOT,
            env=cli_env,
            check=True,
            capture_output=True,
            text=True,
        )
        canary_payload = json.loads(canary_cli.stdout)
        assert canary_payload["cli_bin"] == "goal-harness-canary", canary_payload
        assert "goal-harness-canary doctor" in canary_payload["cli_preflight"], canary_payload
        assert "goal-harness-canary --format json" in canary_payload["quota_guard_command"], canary_payload
        assert "goal-harness-canary heartbeat-prompt --compact" in canary_payload["task_body"], canary_payload
        assert "refresh with explicit delivery" in canary_payload["task_body"], canary_payload
        assert "scale/outcome for progress artifacts" in canary_payload["task_body"], canary_payload

        fresh_install = run_install(env, "install-smoke-fresh")
        assert "goal-harness installed locally" in fresh_install.stdout, fresh_install.stdout
        assert "goal-harness install warning" not in fresh_install.stderr, fresh_install.stderr

        stale_generated_at = (datetime.now(timezone.utc) - timedelta(hours=25)).replace(microsecond=0).isoformat()
        write_promotion_readiness(runtime_run_dir, generated_at=stale_generated_at, label="stale")
        stale_install = run_install(env, "install-smoke-stale")
        assert "goal-harness installed locally" in stale_install.stdout, stale_install.stdout
        assert "promotion-readiness evidence is stale" in stale_install.stderr, stale_install.stderr
        assert "age_hours=" in stale_install.stderr, stale_install.stderr
        assert "non-blocking" in stale_install.stderr, stale_install.stderr

    print("install-local-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
