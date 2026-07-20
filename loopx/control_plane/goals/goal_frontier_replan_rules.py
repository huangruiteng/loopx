from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


GOAL_FRONTIER_REPLAN_RULE_DECISION_SCHEMA_VERSION = (
    "goal_frontier_replan_rule_decision_v0"
)


class GoalFrontierReplanRule(str, Enum):
    EXISTING_OBLIGATION = "existing_obligation"
    BLOCKING_HANDOFF_GATE = "blocking_handoff_gate"
    READY_DEFERRED_SUCCESSOR = "ready_deferred_successor"
    OPEN_USER_TODO = "open_user_todo"
    TODO_SUCCESSION_GAP = "todo_succession_gap"
    VISION_ACCEPTANCE_GAP = "vision_acceptance_gap"
    LONG_TODO_CHAIN = "long_todo_chain"
    LONG_TODO_CHAIN_ACKNOWLEDGED = "long_todo_chain_acknowledged"
    WATCH_LANE_CONTINUATION_ACKNOWLEDGED = "watch_lane_continuation_acknowledged"
    MONITOR_NO_CHANGE_STREAK = "monitor_no_change_streak"
    NOT_MONITOR_ONLY = "not_monitor_only"
    NO_OPEN_MONITOR = "no_open_monitor"
    ADVANCEMENT_REMAINS = "advancement_remains"
    MONITOR_FRONTIER_EXHAUSTED = "monitor_frontier_exhausted"


GOAL_FRONTIER_REPLAN_RULE_ORDER = tuple(GoalFrontierReplanRule)


@dataclass(frozen=True)
class GoalFrontierReplanFacts:
    existing_replan_required: bool = False
    blocking_handoff_gate_count: int = 0
    ready_deferred_successor_count: int = 0
    successor_vision_required: bool = False
    blocking_user_open_count: int = 0
    succession_gap_count: int = 0
    agent_advancement_count: int = 0
    total_frontier_advancement: int = 0
    acceptance_gap_count: int = 0
    selectable_frontier_advancement: int = 0
    acceptance_allows_watch_lane_continuation: bool = False
    long_todo_chain_triggered: bool = False
    long_todo_chain_acknowledged: bool = False
    watch_lane_continuation_acknowledged: bool = False
    monitor_no_change_streak_triggered: bool = False
    monitor_only_lane: bool = False
    monitor_count: int = 0


@dataclass(frozen=True)
class GoalFrontierReplanRuleDecision:
    rule: GoalFrontierReplanRule
    derives_obligation: bool
    reason: str

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": GOAL_FRONTIER_REPLAN_RULE_DECISION_SCHEMA_VERSION,
            "rule": self.rule.value,
            "rule_index": GOAL_FRONTIER_REPLAN_RULE_ORDER.index(self.rule),
            "derives_obligation": self.derives_obligation,
            "reason": self.reason,
        }


def select_goal_frontier_replan_rule(
    facts: GoalFrontierReplanFacts,
) -> GoalFrontierReplanRuleDecision:
    """Select the first matching goal-frontier rule in policy order."""

    ordered_rules = (
        (
            GoalFrontierReplanRule.EXISTING_OBLIGATION,
            facts.existing_replan_required,
            False,
            "an existing scoped obligation remains authoritative",
        ),
        (
            GoalFrontierReplanRule.BLOCKING_HANDOFF_GATE,
            facts.blocking_handoff_gate_count > 0,
            False,
            "a blocking handoff gate owns the next transition",
        ),
        (
            GoalFrontierReplanRule.READY_DEFERRED_SUCCESSOR,
            facts.ready_deferred_successor_count > 0
            and not facts.successor_vision_required,
            False,
            "a deferred successor is already runnable",
        ),
        (
            GoalFrontierReplanRule.OPEN_USER_TODO,
            facts.blocking_user_open_count > 0,
            False,
            "open blocking user work owns the frontier",
        ),
        (
            GoalFrontierReplanRule.TODO_SUCCESSION_GAP,
            facts.succession_gap_count > 0
            and facts.agent_advancement_count == 0
            and facts.total_frontier_advancement == 0,
            True,
            "completed advancement work lacks a successor or no-followup rationale",
        ),
        (
            GoalFrontierReplanRule.VISION_ACCEPTANCE_GAP,
            facts.acceptance_gap_count > 0
            and (
                facts.successor_vision_required
                or facts.selectable_frontier_advancement == 0
            )
            and not facts.acceptance_allows_watch_lane_continuation,
            True,
            "the scoped vision gap has no satisfying runnable frontier",
        ),
        (
            GoalFrontierReplanRule.LONG_TODO_CHAIN,
            facts.long_todo_chain_triggered
            and not facts.long_todo_chain_acknowledged,
            True,
            "the selectable todo chain crossed the bounded replan threshold",
        ),
        (
            GoalFrontierReplanRule.LONG_TODO_CHAIN_ACKNOWLEDGED,
            facts.long_todo_chain_triggered and facts.long_todo_chain_acknowledged,
            False,
            "a frontier-delta acknowledgement covers the long todo chain",
        ),
        (
            GoalFrontierReplanRule.WATCH_LANE_CONTINUATION_ACKNOWLEDGED,
            facts.watch_lane_continuation_acknowledged,
            False,
            "an explicit watch-lane continuation covers the empty frontier",
        ),
        (
            GoalFrontierReplanRule.MONITOR_NO_CHANGE_STREAK,
            facts.monitor_only_lane
            and facts.monitor_count > 0
            and facts.monitor_no_change_streak_triggered,
            True,
            "the current agent monitor crossed the no-change replan threshold",
        ),
        (
            GoalFrontierReplanRule.NOT_MONITOR_ONLY,
            not facts.monitor_only_lane,
            False,
            "the selected lane is not monitor-only",
        ),
        (
            GoalFrontierReplanRule.NO_OPEN_MONITOR,
            facts.monitor_count <= 0,
            False,
            "no open monitor remains",
        ),
        (
            GoalFrontierReplanRule.ADVANCEMENT_REMAINS,
            facts.agent_advancement_count > 0
            or facts.total_frontier_advancement > 0,
            False,
            "advancement work remains on the frontier",
        ),
        (
            GoalFrontierReplanRule.MONITOR_FRONTIER_EXHAUSTED,
            True,
            True,
            "only monitor work remains on an empty advancement frontier",
        ),
    )
    for rule, matches, derives_obligation, reason in ordered_rules:
        if matches:
            return GoalFrontierReplanRuleDecision(
                rule=rule,
                derives_obligation=derives_obligation,
                reason=reason,
            )
    raise AssertionError("goal-frontier replan rules must have a terminal rule")
