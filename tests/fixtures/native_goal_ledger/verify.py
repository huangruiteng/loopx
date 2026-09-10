"""Independent release oracle; the model's own tests are not acceptance authority."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def verify(project: Path) -> None:
    spec = importlib.util.spec_from_file_location("candidate_ledger", project / "ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reduce_events = module.reduce_events
    credit = {"id": "c", "account": "雪", "type": "credit", "amount": 100}
    debit = {"id": "d", "account": "雪", "type": "debit", "amount": 35}
    reverse = {"id": "r", "account": "雪", "type": "reverse", "target": "d"}
    events = [credit, debit, credit.copy(), reverse, reverse.copy()]
    before = copy.deepcopy(events)
    assert reduce_events(events) == {"雪": 100}
    assert events == before
    assert reduce_events([credit, {**reverse, "target": "c"}]) == {"雪": 0}
    assert reduce_events([]) == {}
    for invalid in (
        [{**credit, "amount": True}], [{**credit, "amount": 1.0}],
        [{**credit, "amount": 0}], [{**credit, "extra": 1}],
        [{"id": "missing"}], [debit], [reverse, credit],
        [credit, {**credit, "amount": 2}],
        [credit, debit, {**reverse, "target": "c"}],
        [credit, debit, {**reverse, "account": "other"}],
        [credit, debit, reverse, {**reverse, "id": "r2"}],
        [credit, debit, reverse, {**reverse, "id": "r2", "target": "r"}],
    ):
        untouched = copy.deepcopy(invalid)
        try:
            reduce_events(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid_event_accepted")
        assert invalid == untouched
    long = [{**credit, "id": str(i), "account": "A" if i % 2 else "a"}
            for i in range(12000)]
    assert reduce_events(long + long) == {"A": 600000, "a": 600000}
    with tempfile.TemporaryDirectory(prefix="ledger-oracle-") as raw:
        source = Path(raw) / "input.jsonl"
        for content, expected in (
            ("\n" + "\n".join(json.dumps(e) for e in events), {"雪": 100}),
            ("\n".join(json.dumps(e) for e in [credit, {**credit, "id": "a", "account": "A"}]),
             {"A": 100, "雪": 100}),
            ("\n", {}),
            (json.dumps(credit) + "\nnot-json", None),
            (json.dumps(debit), None),
        ):
            source.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(project / "ledger.py"), str(source)],
                capture_output=True, text=True, timeout=30,
            )
            if expected is None:
                assert result.returncode != 0 and result.stdout == "" and result.stderr
            else:
                assert result.returncode == 0 and result.stderr == ""
                assert result.stdout.endswith("\n") and len(result.stdout.splitlines()) == 1
                assert json.loads(result.stdout) == expected
                assert list(json.loads(result.stdout)) == sorted(expected)
    assert (project / "README.md").is_file()


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve())
    print("ledger acceptance passed")
