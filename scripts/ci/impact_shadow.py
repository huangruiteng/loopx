"""Execute and audit selected CI tests without weakening full-suite gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from impact_plan import VISION_SMOKES, VISION_TESTS, validate_shadow_plan


def digest(packet: dict) -> str:
    return hashlib.sha256(json.dumps(packet, sort_keys=True).encode()).hexdigest()


def execute(packet: dict, output: Path) -> int:
    validate_shadow_plan(packet)
    output.mkdir(parents=True, exist_ok=True)
    commands = [
        ("pytest", [sys.executable, "-m", "pytest", "-q", "-n", "2", "--dist", "loadfile",
                    *VISION_TESTS, f"--junitxml={output / 'selected.xml'}"], 900),
        *((path, [sys.executable, path], 240) for path in VISION_SMOKES),
    ]
    results = []
    for name, argv, timeout in commands:
        started = time.monotonic()
        try:
            code = subprocess.run(argv, timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            code = 124
        results.append({"check": name, "exit_code": code, "seconds": round(time.monotonic() - started, 3)})
    receipt = {
        "schema_version": "loopx_ci_shadow_execution_v1",
        "plan_sha256": digest(packet),
        "checkout_sha": packet["checkout_sha"],
        "coverage_scope": "selected_only",
        "checks": results,
    }
    (output / "execution.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return int(any(item["exit_code"] for item in results))


def cases(path: Path) -> dict[tuple[str, str], str]:
    """JUnit outcomes, never failure text, stdout or machine-local paths."""
    result = {}
    root = ET.parse(path).getroot()
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("not a JUnit report")
    for item in root.iter("testcase"):
        key = (item.get("classname", ""), item.get("name", ""))
        if not all(key) or key in result:
            raise ValueError("missing or duplicate JUnit test identity")
        state = "failed" if item.find("failure") is not None or item.find("error") is not None else (
            "skipped" if item.find("skipped") is not None else "passed")
        result[key] = state
    if not result:
        raise ValueError("empty JUnit report is not qualification")
    return result


def compare(selected: dict, full_reports: list[dict], files: tuple[str, ...]) -> dict:
    full = {}
    for report in full_reports:
        if set(full) & set(report):
            raise ValueError("full shards contain duplicate test identities")
        full.update(report)
    prefixes = tuple(path.removesuffix(".py").replace("/", ".") for path in files)
    for path, prefix in zip(files, prefixes):
        if not any(key[0] == prefix or key[0].startswith(prefix + ".") for key in selected):
            raise ValueError(f"selected file collected no tests: {path}")
    missing = set(selected) - set(full)
    omitted = {key for key in full if any(key[0] == prefix or key[0].startswith(prefix + ".") for prefix in prefixes)} - set(selected)
    differences = {key for key in selected.keys() & full.keys() if selected[key] != full[key]}
    selected_not_passed = {key for key, state in selected.items() if state != "passed"}
    unselected_failures = {key for key, state in full.items() if state == "failed" and key not in selected}
    report = {
        "selected_test_count": len(selected),
        "full_test_count": len(full),
        "missing_from_full_count": len(missing),
        "missing_from_selected_count": len(omitted),
        "outcome_difference_count": len(differences),
        "selected_not_passed_count": len(selected_not_passed),
        "unselected_failure_count": len(unselected_failures),
        "ok": not (missing or omitted or differences or selected_not_passed or unselected_failures),
        "limitation": "Agreement on this revision does not prove the absence of future selection gaps.",
    }
    return report


def audit(packet: dict, selected_dir: Path, full_dir: Path, output: Path) -> int:
    validate_shadow_plan(packet)
    receipt = json.loads((selected_dir / "execution.json").read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "loopx_ci_shadow_execution_v1" or receipt.get("plan_sha256") != digest(packet):
        raise ValueError("execution receipt belongs to a different plan")
    if receipt.get("checkout_sha") != packet["checkout_sha"] or receipt.get("coverage_scope") != "selected_only":
        raise ValueError("execution receipt has invalid revision or coverage provenance")
    checks = receipt.get("checks", [])
    if [item.get("check") for item in checks] != ["pytest", *VISION_SMOKES] or any(item.get("exit_code") != 0 for item in checks):
        raise ValueError("selected tests or required real-entrypoint smokes did not succeed")
    result = compare(cases(selected_dir / "selected.xml"), [
        cases(full_dir / f"python-junit-{shard}" / "junit.xml") for shard in (1, 2)
    ], VISION_TESTS)
    result.update({"schema_version": "loopx_ci_shadow_comparison_v1", "plan_sha256": digest(packet),
                   "checkout_sha": packet["checkout_sha"], "coverage_scope": "selected_only"})
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return int(not result["ok"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("run", "audit"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--selected-dir", default="impact-results")
    parser.add_argument("--full-dir", default="full-reports")
    parser.add_argument("--output", default="impact-comparison.json")
    args = parser.parse_args()
    packet = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if args.operation == "run":
        return execute(packet, Path(args.selected_dir))
    return audit(packet, Path(args.selected_dir), Path(args.full_dir), Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
