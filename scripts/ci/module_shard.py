"""Shard complete pytest modules; preserve ordered shared-fixture tests."""
from collections import defaultdict

import pytest


def assign_modules(counts: dict[str, int], shards: int) -> dict[str, int]:
    """Deterministic largest-module-first balancing, without timing-cache authority."""
    if shards < 1:
        raise ValueError("shards must be positive")
    loads = [0] * shards
    result = {}
    for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        slot = min(range(shards), key=lambda index: (loads[index], index))
        result[name] = slot + 1
        loads[slot] += count
    return result


def pytest_addoption(parser):
    parser.addoption("--ci-module-shards", type=int, default=1)
    parser.addoption("--ci-module-shard", type=int, default=1)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    shards = config.getoption("--ci-module-shards")
    shard = config.getoption("--ci-module-shard")
    if shards < 1 or not 1 <= shard <= shards:
        raise pytest.UsageError("invalid module shard coordinates")
    counts = defaultdict(int)
    for item in items:
        counts[item.nodeid.split("::", 1)[0]] += 1
    assigned = assign_modules(counts, shards)
    selected, deselected = [], []
    for item in items:
        target = selected if assigned[item.nodeid.split("::", 1)[0]] == shard else deselected
        target.append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
