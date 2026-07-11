from __future__ import annotations

from loopx.capabilities.explore.episode_runtime import build_router_probes
from loopx.capabilities.explore.router_state import initial_router_state, observe_epoch


def _probe(**acceptance: object) -> dict[str, object]:
    return {
        "family": "episode-family",
        "duration_minutes": 1.0,
        "observation_keys": [],
        "weighted_flags": {},
        "retryable_infra_error": False,
        **acceptance,
    }


def _observe(*probes: dict[str, object]) -> dict[str, object]:
    state = initial_router_state({"accept_rate_alpha": 1.0})
    return observe_epoch(state, epoch=1, probes=list(probes))


def test_episode_acceptance_is_weighted_by_unequal_attempt_counts() -> None:
    observed = _observe(
        _probe(accepted_count=1, attempt_count=2),
        _probe(accepted_count=8, attempt_count=8),
    )

    family = observed["families"]["episode-family"]
    assert family["accept_rate_ema"] == 0.9
    assert family["runs"] == 2


def test_legacy_boolean_acceptance_keeps_equal_probe_weighting() -> None:
    observed = _observe(
        _probe(accepted=True),
        _probe(accepted=False),
        _probe(accepted=True),
    )

    family = observed["families"]["episode-family"]
    assert family["accept_rate_ema"] == 0.6667
    assert family["runs"] == 3


def test_invalid_counts_fall_back_to_legacy_boolean_behavior() -> None:
    observed = _observe(
        _probe(
            accepted=False,
            accepted_count=1,
            attempt_count=0,
        ),
        _probe(
            accepted=True,
            accepted_count=4,
            attempt_count=2,
        ),
    )

    family = observed["families"]["episode-family"]
    assert family["accept_rate_ema"] == 0.5
    assert family["runs"] == 2


def test_probe_builder_counts_suffixes_for_weighted_router_observation() -> None:
    records: list[dict[str, object]] = []
    for group_id, accepted_values in (
        ("small", [True, False]),
        ("large", [True] * 8),
    ):
        records.extend(
            {
                "execution_group_id": group_id,
                "record_kind": "episode_suffix",
                "family": "episode-family",
                "duration_minutes": 0.1,
                "observation_keys": [],
                "weighted_flags": {},
                "accepted": accepted,
            }
            for accepted in accepted_values
        )

    observed = _observe(*build_router_probes(records))

    family = observed["families"]["episode-family"]
    assert family["accept_rate_ema"] == 0.9
    assert family["runs"] == 2
