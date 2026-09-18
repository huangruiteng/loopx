"""Independent exhaustive oracle; never import the generated solver."""

import copy
import itertools
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def optimal(spec):
    rows = sorted(spec["orders"], key=lambda r: r["id"])
    best = None
    for xs in itertools.product(*(range(r["demand"] + 1) for r in rows)):
        cost = sum(n * r["cost"] for n, r in zip(xs, rows))
        value = sum(n * r["value"] for n, r in zip(xs, rows))
        if cost > spec["budget"]:
            continue
        if any(
            sum(n for n, r in zip(xs, rows) if r["stock_group"] == g)
            > max(0, v - spec.get("reserve_per_group", 0))
            for g, v in spec["stock"].items()
        ):
            continue
        if any(
            sum(n for n, r in zip(xs, rows) if r["region"] == g) > v
            for g, v in spec["region_cap"].items()
        ):
            continue
        if sum(n for n, r in zip(xs, rows) if r["region"] == "east") < spec.get(
            "minimum_east", 0
        ):
            continue
        if best is None or value > best[0] or (value == best[0] and xs < best[1]):
            best = (value, xs, cost)
    if best is None:
        return None
    return {
        "allocation": dict(zip([r["id"] for r in rows], best[1])),
        "total_value": best[0],
        "total_cost": best[2],
    }


def verify(workspace):
    spec = json.loads((workspace / "inputs/scenario.json").read_text())
    cases = [spec]
    for budget in [0, 90, 400, 1000]:
        cases.append(dict(spec, budget=budget, minimum_east=0))
    cases.append(dict(spec, reserve_per_group=1, minimum_east=4))
    cases.append(dict(spec, orders=list(reversed(spec["orders"]))))
    tie = {
        "orders": [
            {
                "id": "b",
                "region": "east",
                "demand": 2,
                "stock_group": "g",
                "cost": 1,
                "value": 1,
            },
            {
                "id": "a",
                "region": "east",
                "demand": 2,
                "stock_group": "g",
                "cost": 1,
                "value": 1,
            },
        ],
        "stock": {"g": 2},
        "region_cap": {"east": 2},
        "budget": 2,
    }
    cases.append(tie)
    cases.append(dict(spec, minimum_east=99))
    invalid = []
    for field, value in [("budget", True), ("budget", -1), ("budget", 2.5)]:
        invalid.append(dict(spec, **{field: value}))
    dup = copy.deepcopy(spec)
    dup["orders"].append(dup["orders"][0])
    invalid.append(dup)
    missing = copy.deepcopy(spec)
    del missing["stock"]["x"]
    invalid.append(missing)
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "input.json"
        out = Path(tmp) / "plan.json"
        for case in cases:
            source.write_text(json.dumps(case))
            out.unlink(missing_ok=True)
            p = subprocess.run(
                [sys.executable, str(workspace / "solver.py"), str(source), str(out)],
                capture_output=True,
                text=True,
                timeout=20,
            )
            expected = optimal(case)
            if expected is None:
                assert p.returncode != 0 and not out.exists(), (
                    case,
                    p.stdout,
                    p.stderr,
                )
            else:
                assert p.returncode == 0, (p.stdout, p.stderr)
                actual = json.loads(out.read_text())
                assert {k: actual[k] for k in expected} == expected, (expected, actual)
        for case in invalid:
            source.write_text(json.dumps(case))
            out.unlink(missing_ok=True)
            p = subprocess.run(
                [sys.executable, str(workspace / "solver.py"), str(source), str(out)],
                capture_output=True,
                text=True,
                timeout=20,
            )
            assert p.returncode != 0 and not out.exists(), ("invalid accepted", case)
    return {
        "positive_cases": len(cases),
        "negative_cases": len(invalid),
        "expected": optimal(spec),
    }


if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1])), indent=2))
