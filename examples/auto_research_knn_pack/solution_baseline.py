from __future__ import annotations

from typing import Iterable


STRATEGY = "full_sort"


Point = tuple[float, ...]


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def solve_knn(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    """Reference exact k-NN solver using a full distance sort per query."""

    results: list[list[int]] = []
    for query in queries:
        ranked = sorted((_squared_distance(query, point), index) for index, point in enumerate(train))
        results.append([index for _, index in ranked[:k]])
    return results
