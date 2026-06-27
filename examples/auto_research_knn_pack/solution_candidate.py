from __future__ import annotations

import heapq


STRATEGY = "partial_selection"


Point = tuple[float, ...]


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def solve_knn(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    """Exact k-NN using partial selection instead of sorting every distance."""

    results: list[list[int]] = []
    for query in queries:
        nearest = heapq.nsmallest(
            k,
            ((_squared_distance(query, point), index) for index, point in enumerate(train)),
        )
        results.append([index for _, index in nearest])
    return results
