from __future__ import annotations

from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sonarcloud.yml"


def test_missing_sonar_token_reaches_a_successful_skip_step() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "if: ${{ secrets.SONAR_TOKEN != '' }}" not in workflow
    assert "id: sonar-token" in workflow
    assert "available=false" in workflow
    assert "if: steps.sonar-token.outputs.available != 'true'" in workflow
    assert "non-blocking analysis skipped" in workflow


def _assert_token_guards(workflow: str) -> None:
    # Match the workflow's existing named-step convention, not its step count:
    # adding another coverage artifact must not weaken or break token isolation.
    steps = workflow.split("      - name: ")[1:]
    assert steps
    analysis_steps = []
    for step in steps:
        if "        id: sonar-token\n" in step:
            continue
        if step.startswith("Skip analysis when the token is unavailable\n"):
            assert "if: steps.sonar-token.outputs.available != 'true'" in step
            continue
        assert "if: steps.sonar-token.outputs.available == 'true'" in step, step.splitlines()[0]
        analysis_steps.append(step)
    assert any("uses: actions/checkout@" in step for step in analysis_steps)
    assert any("uses: SonarSource/sonarqube-scan-action@" in step for step in analysis_steps)
    for artifact in ("python-coverage-xml", "typescript-control-plane-coverage"):
        assert any(f"name: {artifact}\n" in step for step in analysis_steps)


def test_sonar_steps_remain_guarded_by_the_token() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    _assert_token_guards(workflow)
    assert workflow.count("SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}") == 2
    assert "\n    env:\n      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}" not in workflow


def test_each_missing_analysis_guard_is_rejected() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    guard = "        if: steps.sonar-token.outputs.available == 'true'\n"
    fragments = workflow.split(guard)
    assert len(fragments) > 1
    for index in range(len(fragments) - 1):
        mutant = guard.join(fragments[:index + 1]) + guard.join(fragments[index + 1:])
        with pytest.raises(AssertionError):
            _assert_token_guards(mutant)


def test_sonar_reuses_same_run_coverage_without_a_privileged_trigger() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    caller = WORKFLOW.with_name("python-tests.yml").read_text(encoding="utf-8")

    assert "workflow_call:" in workflow
    assert "workflow_run:" not in workflow
    assert "pull_request_target:" not in workflow + caller
    assert "python -m pytest" not in workflow
    assert "name: python-coverage-xml" in workflow
    assert "run-id:" not in workflow
    assert "github-token:" not in workflow
    assert "needs: pytest\n    uses: ./.github/workflows/sonarcloud.yml" in caller
    assert '"apps/**"' in caller
    assert '"sonar-project.properties"' in caller
