"""Negative or absent evidence cannot qualify a candidate test selection."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from impact_plan import VISION_SMOKES, VISION_TESTS
from impact_shadow import audit, cases, compare, digest, execute


class ShadowComparisonTests(unittest.TestCase):
    def test_same_cases_and_outcomes_match_without_claiming_full_coverage(self):
        chosen = {("tests.test_a", "test_ok[x]"): "passed"}
        report = compare(chosen, [chosen, {("tests.test_b", "test_other"): "passed"}], ("tests/test_a.py",))
        self.assertTrue(report["ok"])
        self.assertEqual(report["selected_test_count"], 1)
        self.assertEqual(report["full_test_count"], 2)
        self.assertIn("does not prove", report["limitation"])

    def test_omissions_different_outcomes_and_unselected_failures_are_not_passes(self):
        key, other = ("tests.test_a", "test_a"), ("tests.test_b", "test_b")
        for selected, full, metric in (
            ({key: "passed"}, {other: "passed"}, "missing_from_full_count"),
            ({key: "passed"}, {key: "failed"}, "outcome_difference_count"),
            ({key: "skipped"}, {key: "skipped"}, "selected_not_passed_count"),
            ({key: "failed"}, {key: "failed"}, "selected_not_passed_count"),
            ({key: "passed"}, {key: "passed", other: "failed"}, "unselected_failure_count"),
            ({key: "passed"}, {key: "passed", ("tests.test_a", "test_omitted"): "passed"}, "missing_from_selected_count"),
        ):
            with self.subTest(metric=metric):
                result = compare(selected, [full], ("tests/test_a.py",))
                self.assertFalse(result["ok"])
                self.assertEqual(result[metric], 1)

    def test_empty_collection_and_duplicate_full_shards_fail(self):
        with self.assertRaises(ValueError):
            compare({}, [{}], ("tests/test_a.py",))
        chosen = {("tests.test_a", "test_a"): "passed"}
        with self.assertRaises(ValueError):
            compare(chosen, [chosen, chosen], ("tests/test_a.py",))
        with self.assertRaises(ValueError):
            compare(chosen, [chosen], ("tests/test_a.py", "tests/test_b.py"))

    def test_junit_uses_identity_and_state_not_failure_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "junit.xml"
            path.write_text('<testsuites><testsuite><testcase classname="tests.test_a" name="ok"/>'
                            '<testcase classname="tests.test_a" name="bad"><failure>not exported</failure></testcase>'
                            '<testcase classname="tests.test_a" name="skip"><skipped/></testcase></testsuite></testsuites>')
            self.assertEqual(list(cases(path).values()), ["passed", "failed", "skipped"])
            for text in ('<testsuites/>', '<unknown/>', '<testsuite><testcase name="no-class"/></testsuite>',
                         '<testsuite><testcase classname="a" name="b"/><testcase classname="a" name="b"/></testsuite>'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    cases(path)

    def test_failed_command_keeps_negative_receipt_and_does_not_invent_success(self):
        with tempfile.TemporaryDirectory() as directory, patch("impact_shadow.validate_shadow_plan"), patch("impact_shadow.subprocess.run") as run:
            run.return_value.returncode = 1
            packet = {"checkout_sha": "a" * 40}
            self.assertEqual(execute(packet, Path(directory)), 1)
            receipt = json.loads((Path(directory) / "execution.json").read_text())
            self.assertEqual(receipt["coverage_scope"], "selected_only")
            self.assertEqual([item["check"] for item in receipt["checks"]], ["pytest", *VISION_SMOKES])
            self.assertTrue(all(item["exit_code"] == 1 for item in receipt["checks"]))

    def test_wrong_plan_and_missing_smokes_cannot_use_a_green_junit(self):
        with tempfile.TemporaryDirectory() as directory, patch("impact_shadow.validate_shadow_plan"):
            root = Path(directory)
            packet = {"checkout_sha": "a" * 40}
            receipt = {"schema_version": "loopx_ci_shadow_execution_v1", "checkout_sha": "a" * 40,
                       "plan_sha256": digest(packet), "coverage_scope": "selected_only", "checks": []}
            for change in ({}, {"plan_sha256": "wrong"}, {"coverage_scope": "full"}, {"checkout_sha": "b" * 40}):
                (root / "execution.json").write_text(json.dumps({**receipt, **change}))
                with self.assertRaises(ValueError):
                    audit(packet, root, root, root / "comparison.json")
                self.assertFalse((root / "comparison.json").exists())

    def test_real_report_audit_requires_both_shards_and_complete_inventory(self):
        with tempfile.TemporaryDirectory() as directory, patch("impact_shadow.validate_shadow_plan"):
            root = Path(directory)
            packet = {"checkout_sha": "a" * 40}
            receipt = {"schema_version": "loopx_ci_shadow_execution_v1", "checkout_sha": "a" * 40,
                       "plan_sha256": digest(packet), "coverage_scope": "selected_only",
                       "checks": [{"check": name, "exit_code": 0} for name in ("pytest", *VISION_SMOKES)]}
            (root / "execution.json").write_text(json.dumps(receipt))
            rows = [f'<testcase classname="{path.removesuffix(".py").replace("/", ".")}" name="test_case"/>' for path in VISION_TESTS]

            def report(path, cases):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("<testsuite>" + "".join(cases) + "</testsuite>")

            report(root / "selected.xml", rows)
            report(root / "python-junit-1/junit.xml", rows[:1])
            with self.assertRaises(FileNotFoundError):
                audit(packet, root, root, root / "result.json")
            report(root / "python-junit-2/junit.xml", rows[1:])
            self.assertEqual(audit(packet, root, root, root / "result.json"), 0)
            result = json.loads((root / "result.json").read_text())
            self.assertTrue(result["ok"])
            self.assertEqual(result["selected_test_count"], len(VISION_TESTS))
            self.assertEqual(result["coverage_scope"], "selected_only")


if __name__ == "__main__":
    unittest.main()
