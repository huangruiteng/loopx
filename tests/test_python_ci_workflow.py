from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest


WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "python-tests.yml"
).read_text(encoding="utf-8")


@pytest.mark.parametrize("result", ["success", "failure", "cancelled", "skipped", ""])
def test_stage2c_gate_requires_all_lanes(result: str) -> None:
    gate = WORKFLOW.split("  stage2c-correctness-e2e:", 1)[1].split("  windows-powershell:", 1)[0]
    assert "if: always()" in gate
    assert "needs: [changes, stage2c-suite]" in gate
    assert "if: always() && needs.changes.outputs.core_tests == 'true'" in gate
    assert "STAGE2C_RESULT: ${{ needs.stage2c-suite.result }}" in gate
    script = gate.split("run: ", 1)[1].strip()
    actual = subprocess.run(
        ["bash", "-e", "-c", script],
        env={**os.environ, "STAGE2C_RESULT": result}, check=False,
    )
    assert (actual.returncode == 0) == (result == "success")
    suite = WORKFLOW.split("  stage2c-suite:", 1)[1].split("  stage2c-correctness-e2e:", 1)[0]
    assert "fail-fast: false" in suite
    assert "suite: [e2e, mutants, installed]" in suite
    assert "if: needs.changes.outputs.core_tests == 'true'" in suite.split("    steps:", 1)[0]
    steps = {step.splitlines()[0]: step for step in suite.split("      - name: ")[1:]}
    for name, lane in [
        ("Qualify real CLI, mixed writers, process death, and recovery", "e2e"),
        ("Reject deliberate correctness regressions", "mutants"),
        ("Build independently installed distributions", "installed"),
        ("Qualify wheel outside the repository", "installed"),
        ("Qualify sdist outside the repository", "installed"),
    ]:
        assert f"if: matrix.suite == '{lane}'" in steps[name]
    assert "--case" not in steps["Reject deliberate correctness regressions"]
    artifact = steps["Retain bounded acceptance evidence"]
    assert "if: always()" in artifact
    assert "name: stage2c-correctness-evidence-${{ matrix.suite }}" in artifact
    assert "if-no-files-found: error" in artifact


def test_stage2c_workers_preserve_module_state_and_execute_every_row(tmp_path: Path) -> None:
    step = WORKFLOW.split("name: Qualify real CLI, mixed writers, process death, and recovery", 1)[1]
    command = step.split("run: ", 1)[1].splitlines()[0]
    args = shlex.split(command)
    args[0] = sys.executable
    # Actual workflow command against two modules with order-sensitive shared state.
    # Per-test distribution would break the module fixture's accumulated state.
    for name in ("first", "second"):
        (tmp_path / f"test_{name}.py").write_text(
            "import os\nfrom pathlib import Path\nimport pytest\n"
            "pytestmark = pytest.mark.stage2c_e2e\n"
            "@pytest.fixture(scope='module')\ndef state():\n    return []\n"
            "@pytest.mark.parametrize('row', range(4))\n"
            "def test_order(state, row):\n"
            "    assert state == list(range(row))\n    state.append(row)\n"
            f"    with Path('{name}.visits').open('a') as stream:\n"
            "        stream.write(f'{os.getpid()}:{row}\\n')\n",
            encoding="utf-8",
        )
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers = stage2c_e2e\n")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYTEST", "COVERAGE", "COV_CORE"))}
    actual = subprocess.run(args, cwd=tmp_path, env=env, capture_output=True,
                            text=True, timeout=60, check=False)
    assert actual.returncode == 0, actual.stdout + actual.stderr
    cases = ET.parse(tmp_path / "stage2c-e2e.xml").findall(".//testcase")
    assert len(cases) == 8
    workers = set()
    for name in ("first", "second"):
        rows = [line.split(":") for line in (tmp_path / f"{name}.visits").read_text().splitlines()]
        assert [row for _, row in rows] == ["0", "1", "2", "3"]
        assert len({pid for pid, _ in rows}) == 1
        workers.add(rows[0][0])
    assert len(workers) == 2


@pytest.mark.parametrize("checks", ["success", "failure", "cancelled", "skipped"])
@pytest.mark.parametrize("shards", ["success", "failure", "cancelled", "skipped"])
def test_required_pytest_check_rejects_incomplete_upstream_jobs(
    checks: str, shards: str,
) -> None:
    # Execute the actual gate, including the runner's fail-fast shell behavior.
    gate = WORKFLOW.split("name: Require every upstream check", 1)[1]
    script = gate.split("run: |", 1)[1].split("      - uses:", 1)[0]
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        env={**os.environ, "CHECKS_RESULT": checks, "SHARDS_RESULT": shards},
        capture_output=True,
        check=False,
    )
    assert (result.returncode == 0) == (checks == shards == "success")
    assert "if: always() && needs.changes.outputs.core_tests == 'true'" in WORKFLOW
    assert "needs: [changes, checks, test-shard]" in WORKFLOW


def test_merge_gate_runs_on_all_prs_and_checks_every_core_aggregate() -> None:
    trigger = WORKFLOW.split("  pull_request:", 1)[1].split("  push:", 1)[0]
    assert "paths:" not in trigger and "paths-ignore:" not in trigger
    gate = WORKFLOW.split("  merge-gate:", 1)[1]
    assert "if: always()" in gate
    assert (
        "needs: [changes, pytest, node-minimum-compatibility, "
        "stage2c-correctness-e2e, windows-powershell]"
    ) in gate
    assert "NEEDS_JSON: ${{ toJSON(needs) }}" in gate
    assert "run: python scripts/ci/review_gate.py verify" in gate
    assert "continue-on-error" not in gate
    for name in ("checks", "test-shard", "stage2c-suite", "windows-powershell"):
        job = WORKFLOW.split(f"  {name}:\n", 1)[1].split("    steps:", 1)[0]
        assert "needs: changes" in job
        assert "if: needs.changes.outputs.core_tests == 'true'" in job


def test_two_shards_execute_each_test_once_and_merge_portable_coverage(
    tmp_path: Path,
) -> None:
    # Real pytest-split + xdist + coverage, in two distinct checkout roots.
    # Each shard alone misses a function; their union must cover the whole file.
    shard_step = WORKFLOW.split("name: Run test shard", 1)[1]
    template = shard_step.split("run: >-", 1)[1].split("      - name:", 1)[0]
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("COVERAGE", "COV_CORE", "PYTEST"))
    }
    seen: list[set[str]] = []
    for shard in (1, 2):
        root = tmp_path / f"checkout-{shard}"
        root.mkdir()
        (root / "ci_subject.py").write_text(
            "def first():\n    return 1\n\ndef second():\n    return 2\n",
            encoding="utf-8",
        )
        (root / "test_subject.py").write_text(
            "from ci_subject import first, second\n"
            "def test_first():\n    assert first() == 1\n"
            "def test_second():\n    assert second() == 2\n",
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text(
            '[tool.coverage.run]\nsource = ["ci_subject"]\nrelative_files = true\n',
            encoding="utf-8",
        )
        args = shlex.split(template.replace("${{ matrix.shard }}", str(shard)))
        args[0] = sys.executable
        args[args.index("--cov=loopx")] = "--cov=ci_subject"
        result = subprocess.run(
            [*args, "--junitxml=results.xml"], cwd=root, env=env,
            capture_output=True, text=True, timeout=60, check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        cases = ET.parse(root / "results.xml").findall(".//testcase")
        seen.append({case.attrib["name"] for case in cases})
        partial = subprocess.run(
            [sys.executable, "-m", "coverage", "report", "--fail-under=100"],
            cwd=root, env=env, capture_output=True, check=False,
        )
        assert partial.returncode == 2
        destination = tmp_path / "coverage-shards" / f"python-coverage-{shard}"
        destination.mkdir(parents=True)
        (root / ".coverage").rename(destination / ".coverage")

    assert seen[0] and seen[1] and seen[0].isdisjoint(seen[1])
    assert seen[0] | seen[1] == {"test_first", "test_second"}
    # Reuse the real aggregate shell commands, with a 100% synthetic oracle.
    step = WORKFLOW.split("name: Combine complete coverage", 1)[1]
    script = step.split("run: |", 1)[1].split("      - uses:", 1)[0]
    script = script.replace("python -m", f"{shlex.quote(sys.executable)} -m")
    script = script.replace("--fail-under=19.6", "--fail-under=100")
    root = tmp_path / "checkout-1"
    (tmp_path / "coverage-shards").rename(root / "coverage-shards")
    for shard in (1, 2):
        data = root / "coverage-shards" / f"python-coverage-{shard}" / ".coverage"
        held = data.with_name("held")
        data.rename(held)
        missing = subprocess.run(
            ["bash", "-e", "-c", script], cwd=root, env=env,
            capture_output=True, check=False,
        )
        assert missing.returncode != 0
        assert not (root / "coverage.xml").exists()
        held.rename(data)
    result = subprocess.run(
        ["bash", "-e", "-c", script], cwd=root, env=env,
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert ET.parse(root / "coverage.xml").getroot().attrib["line-rate"] == "1"
    # The combine consumed the inputs: replay with absent artifacts must fail.
    missing = subprocess.run(
        ["bash", "-e", "-c", script], cwd=root, env=env,
        capture_output=True, check=False,
    )
    assert missing.returncode != 0
    assert re.search(r"shard: \[1, 2\]", WORKFLOW)
    assert "include-hidden-files: true" in WORKFLOW
    assert "--cov-fail-under" not in template
