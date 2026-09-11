"""Selection rules are conservative; exact Git changes are the input oracle."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from impact_plan import Change, VISION_SOURCES, VISION_TESTS, candidate, validate_shadow_plan
from review_gate import CORE_JOBS, verify


def gate(profile="vision", shadow="vision"):
    core = profile != "docs"
    return {
        "changes": {"result": "success", "outputs": {"core_tests": str(core).lower(),
                    "impact_profile": profile, "shadow_profile": shadow}},
        **{name: {"result": "success" if core else "skipped"} for name in CORE_JOBS},
        "impact-shadow": {"result": "success" if shadow == "vision" else "skipped"},
    }


class ImpactRuleTests(unittest.TestCase):
    def test_sources_select_cross_domain_consumers(self):
        for source in VISION_SOURCES:
            self.assertEqual(candidate([Change("M", source)])[0], "vision")
        for required in (
            "tests/control_plane/test_refresh_state_replan_gate.py",
            "tests/control_plane/test_goal_terminal_no_followup.py",
            "tests/control_plane/test_quota_settlement_cli.py",
            "tests/control_plane/test_vision_budget_cli.py",
        ):
            self.assertIn(required, VISION_TESTS)
        self.assertEqual(len(VISION_TESTS), len(set(VISION_TESTS)))

    def test_additional_test_is_selected_but_new_runtime_is_full(self):
        self.assertEqual(candidate([Change("A", VISION_TESTS[0])])[0], "vision")
        self.assertEqual(candidate([Change("A", VISION_SOURCES[0])])[0], "full")

    def test_unknown_shared_and_ci_paths_cannot_hide_in_a_known_change(self):
        for path in (
            "loopx/control_plane/runtime_decode.ts", "loopx/control_plane/effect_runtime_handlers.ts",
            "loopx/control_plane/coordination/todo_update.ts", "loopx/cli.py", "tests/conftest.py",
            "scripts/ci/impact_plan.py", ".github/workflows/python-tests.yml", "pyproject.toml",
            "package-lock.json", "new-vision-checkpoint.ts", "docs/executable.py", "loopx/prompt.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(candidate([Change("M", VISION_SOURCES[0]), Change("M", path)])[0], "full")

    def test_deletion_type_change_rename_and_bad_status_are_full(self):
        for status in ("D", "T", "R100", "U", ""):
            self.assertEqual(candidate([Change(status, VISION_SOURCES[0])])[0], "full")
        self.assertEqual(candidate([Change("D", VISION_SOURCES[0]), Change("A", "docs/copied.md")])[0], "full")

    def test_docs_maintain_the_existing_exemption_not_a_keyword_heuristic(self):
        self.assertEqual(candidate([Change("M", "docs/vision.md"), Change("D", "README.md")])[0], "docs")
        for path in ("docs/not-a-doc.ts", "docs/../loopx/code.md", "/docs/readme.md", "docs//readme.md"):
            self.assertEqual(candidate([Change("M", path)])[0], "full")
        self.assertEqual(candidate([])[0], "full")

    def test_main_and_scheduled_contexts_never_select_less(self):
        for changes in ([], [Change("M", "docs/a.md")], [Change("M", VISION_SOURCES[0])]):
            self.assertEqual(candidate(changes, pull_request=False)[0], "full")

    def test_full_gate_is_retained_for_every_candidate(self):
        self.assertEqual(set(CORE_JOBS), {"pytest", "node-minimum-compatibility", "stage2c-correctness-e2e", "windows-powershell"})
        for profile, shadow in (("vision", "vision"), ("full", "vision"), ("full", "none"), ("docs", "none")):
            verify(gate(profile, shadow), shadow=True)
        for name in (*CORE_JOBS, "impact-shadow"):
            for state in ("failure", "cancelled", "skipped", "neutral", None):
                value = gate()
                value[name]["result"] = state
                with self.subTest(name=name, state=state), self.assertRaises(ValueError):
                    verify(value, shadow=True)

    def test_missing_and_contradictory_profiles_fail_closed(self):
        for value in (gate("docs", "vision"), gate("vision", "none"), gate("invented", "none")):
            with self.assertRaises(ValueError):
                verify(value, shadow=True)
        value = gate("docs", "none")
        value["impact-shadow"]["result"] = "success"
        with self.assertRaises(ValueError):
            verify(value, shadow=True)
        for field in ("core_tests", "impact_profile", "shadow_profile"):
            value = gate()
            del value["changes"]["outputs"][field]
            with self.assertRaises(ValueError):
                verify(value, shadow=True)
        for name in ("impact-shadow", "changes", *CORE_JOBS):
            value = gate()
            del value[name]
            with self.assertRaises(ValueError):
                verify(value, shadow=True)


class RealGitImpactTests(unittest.TestCase):
    def test_real_diff_and_cli_bind_revisions_and_preserve_all_paths(self):
        script = str(Path(__file__).with_name("review_gate.py"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PYTEST", "COVERAGE", "COV_CORE"))}

            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, env=env, text=True).strip()

            def write(path, content):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)

            def classify(base, head="HEAD", *extra):
                result = subprocess.run([sys.executable, script, "classify", "--base", base, "--head", head,
                    "--plan", str(root / "result.json"), *extra], cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout, json.loads((root / "result.json").read_text())

            git("init", "-q")
            git("config", "user.name", "CI Fixture")
            git("config", "user.email", "ci@example.invalid")
            git("config", "core.hooksPath", str(root / "no-hooks"))
            write(VISION_SOURCES[0], "// baseline\n")
            git("add", VISION_SOURCES[0])
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            write(VISION_SOURCES[0], "// changed\n")
            git("commit", "-qam", "vision change")
            output, packet = classify(base)
            self.assertIn("core_tests=true", output)
            self.assertIn("impact_profile=vision", output)
            self.assertEqual(packet["head_sha"], git("rev-parse", "HEAD"))
            self.assertEqual(packet["merge_base_sha"], base)
            self.assertEqual(packet["execution_mode"], "full_with_shadow")
            self.assertFalse(packet["selection_is_merge_authority"])
            self.assertEqual(classify(base, "HEAD", "--non-pr")[1]["shadow_profile"], "none")
            # A newline-bearing filename is one path, never a GITHUB_OUTPUT line.
            strange = "unknown\ncore_tests=false"
            write(strange, "fixture\n")
            git("add", strange)
            git("commit", "-qm", "unknown path")
            output, packet = classify(base)
            self.assertNotIn("core_tests=false", output)
            self.assertIn(strange, [item["path"] for item in packet["changes"]])
            self.assertEqual(packet["candidate_profile"], "full")
            write("scripts/ci/impact_plan.py", "# policy changed\n")
            git("add", "scripts/ci/impact_plan.py")
            git("commit", "-qm", "policy qualification")
            packet = classify(base)[1]
            self.assertEqual((packet["candidate_profile"], packet["shadow_profile"]), ("full", "vision"))
            before_rename = git("rev-parse", "HEAD")
            (root / "docs").mkdir()
            git("mv", VISION_SOURCES[0], "docs/moved.md")
            git("commit", "-qm", "rename")
            packet = classify(before_rename)[1]
            self.assertEqual(packet["candidate_profile"], "full")
            self.assertEqual({item["status"] for item in packet["changes"]}, {"A", "D"})
            failed = subprocess.run([sys.executable, script, "classify", "--base", "missing-base", "--head", "HEAD",
                "--plan", str(root / "invalid.json")], cwd=root, env=env, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse((root / "invalid.json").exists())

    def test_plan_validation_rejects_wrong_revision_inventory_and_authority(self):
        from impact_plan import SCHEMA, VISION_SMOKES
        packet = {"schema_version": SCHEMA, "candidate_profile": "vision", "shadow_profile": "vision",
                  "execution_mode": "full_with_shadow", "selection_is_merge_authority": False,
                  "checkout_sha": "a" * 40, "base_sha": "b" * 40, "head_sha": "a" * 40,
                  "merge_base_sha": "b" * 40, "pytest_files": list(VISION_TESTS), "smoke_files": list(VISION_SMOKES)}
        with patch("impact_plan.revision", return_value="a" * 40), patch("impact_plan.plan", return_value=packet), patch("impact_plan.Path.is_file", return_value=True), patch("impact_plan.Path.is_symlink", return_value=False):
            validate_shadow_plan(packet)
            for field, value in (("checkout_sha", "c" * 40), ("pytest_files", []), ("smoke_files", []),
                                 ("selection_is_merge_authority", True), ("execution_mode", "targeted"),
                                 ("head_sha", "HEAD"), ("base_sha", "c" * 40)):
                changed = copy.deepcopy(packet)
                changed[field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    validate_shadow_plan(changed)


if __name__ == "__main__":
    unittest.main()
