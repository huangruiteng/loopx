"""An intentionally exempt job must be skipped; all required jobs must pass."""
from __future__ import annotations
import copy
import unittest
from impact_plan import job_flags
from review_gate import CORE_JOBS, JOB_OUTPUT, requires_core_tests, verify


def needs(kind="full", *, presentation=False):
    flags = job_flags(kind, presentation=presentation)
    return {"changes": {"result": "success", "outputs": {"change_kind": kind,
        **{key: str(value).lower() for key, value in flags.items()}}},
        **{job: {"result": "success" if flags[output] else "skipped"} for job, output in JOB_OUTPUT.items()}}


class GateTests(unittest.TestCase):
    def test_legal_profiles_and_policy_rehearsal(self):
        for kind in ("docs", "presentation", "full"):
            verify(needs(kind))
        verify(needs("full", presentation=True))
        self.assertFalse(requires_core_tests(["README.md", "docs/guide.md"]))
        self.assertTrue(requires_core_tests(["loopx/prompt.md"]))
        self.assertTrue(requires_core_tests([]))

    def test_every_missing_failure_cancel_or_unexpected_skip_is_rejected(self):
        for kind in ("docs", "presentation", "full"):
            good = needs(kind)
            for job in CORE_JOBS:
                for state in ("success", "skipped", "failure", "cancelled", "neutral", None):
                    if state == good[job]["result"]:
                        continue
                    value = copy.deepcopy(good)
                    value[job]["result"] = state
                    with self.subTest(kind=kind, job=job, state=state), self.assertRaises(ValueError):
                        verify(value)
            for job in ("changes", *CORE_JOBS):
                value = copy.deepcopy(good)
                del value[job]
                with self.assertRaises(ValueError):
                    verify(value)

    def test_bad_and_contradictory_classification_cannot_skip_work(self):
        for kind in ("docs", "presentation", "full"):
            for field in ("change_kind", "core_tests", "python_tests", "stage2c_tests", "presentation_tests"):
                for replacement in (None, "", True, "unknown"):
                    value = needs(kind)
                    value["changes"]["outputs"][field] = replacement
                    with self.assertRaises((ValueError, TypeError)):
                        verify(value)
        value = needs("full")
        value["changes"]["outputs"]["stage2c_tests"] = "false"
        with self.assertRaises(ValueError):
            verify(value)
        for state in ("failure", "skipped", "cancelled"):
            value = needs()
            value["changes"]["result"] = state
            with self.assertRaises(ValueError):
                verify(value)
        with self.assertRaises(ValueError):
            verify({**needs(), "extra": {"result": "success"}})


if __name__ == "__main__":
    unittest.main()
