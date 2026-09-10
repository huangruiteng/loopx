"""Public exports must not republish withdrawn experiment arms."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest


STUDY = Path(__file__).resolve().parents[1] / "swe-marathon"


@pytest.fixture
def exporters(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY / "scoring"))
    modules = []
    for name in ("_aggregate", "case_insights"):
        spec = importlib.util.spec_from_file_location(
            f"publication_test_{name}", STUDY / "scoring" / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def test_aggregate_filters_before_denominator_and_count(exporters, monkeypatch, tmp_path):
    aggregate, _ = exporters
    data = json.loads((STUDY / "data.json").read_text())
    rows = {(task, arm): cell for task, cols in data["cells"].items()
            for arm, cell in cols.items()}
    for task in data["tasks_all"]:
        for arm in ("ssh-goal", "codex-cli"):
            rows[task, arm] = {**rows[task, "heartbeat"], "arm": arm}
    rows["withdrawn-only", "ssh-goal"] = {"arm": "ssh-goal"}
    monkeypatch.setattr(aggregate, "collect", lambda _: rows)
    output = tmp_path / "data.json"
    monkeypatch.setattr(sys, "argv", ["aggregate", str(tmp_path), str(output)])
    assert aggregate.main() == 0
    result = json.loads(output.read_text())
    assert result["arms"] == list(aggregate.ARMS)
    assert result["n_trials"] == sum(len(cols) for cols in data["cells"].values())
    assert result["tasks_full"] == data["tasks_full"]
    assert result["cells"] == data["cells"]
    for arm, expected in data["arm_summary"].items():
        for field, value in expected.items():
            actual = result["arm_summary"][arm][field]
            if isinstance(value, float):
                # Aggregation order can change the final floating-point bit.
                assert actual == pytest.approx(value, rel=0, abs=1e-12)
            else:
                assert actual == value
    assert result["publication_note"]


def test_insights_filter_old_input_and_keep_negative_evidence(exporters):
    _, insights = exporters
    data = json.loads((STUDY / "data.json").read_text())
    for task, cols in data["cells"].items():
        for arm in ("ssh-goal", "codex-cli"):
            cols[arm] = {**cols["heartbeat"], "arm": arm, "build_failed": True}
    records = insights.build(data)
    assert all("__heartbeat__" in row["run_id"] for row in records)
    assert any(row["outcome_status"] == "incomplete" for row in records)
    assert any(row["outcome_status"] == "completed" for row in records)
    published = json.loads((STUDY / "case_insights.json").read_text())
    assert published == insights._payload(records)
    assert published["study_observations"] == []


def test_published_data_and_bilingual_tables_share_scope(exporters):
    aggregate, _ = exporters
    data = json.loads((STUDY / "data.json").read_text())
    allowed = set(aggregate.ARMS)
    assert set(data["arms"]) == set(data["arm_role"]) == set(data["arm_summary"]) == allowed
    assert all(set(cols) == allowed for cols in data["cells"].values())
    site = STUDY.parents[1] / "apps/presentation/site/src"
    copy = json.loads((site / "swe-marathon-copy.json").read_text())
    for localized in copy.values():
        assert {row[0] for row in localized["armRows"]} == allowed
        assert set(localized["executiveReads"]) == allowed
