#!/usr/bin/env python3
"""Smoke-check the generic multi-agent visible launcher protocol contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/reference/protocols/multi-agent-visible-launcher-v0.md"
LOCAL_PLAN = ROOT / "docs/reference/protocols/local-agent-launch-plan-v0.md"
AUTO_RESEARCH_PROFILE = ROOT / "docs/reference/protocols/auto-research-role-profile-v0.md"
AUTO_RESEARCH_GUIDE = ROOT / "docs/guides/auto-research-command-path.md"
PROTOCOL_INDEX = ROOT / "docs/reference/protocols/README.md"
DOCS_INDEX = ROOT / "docs/README.md"


PRIVATE_MARKERS = [
    "byte" + "dance",
    "lark" + "office",
    "fei" + "shu.cn",
    "/" + "Users" + "/",
    "/" + "private" + "/",
    "/" + "tmp" + "/",
    "api" + "_key",
    "pass" + "word",
    "sec" + "ret",
]


def read(path: Path) -> str:
    assert path.exists(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def require(text: str, snippets: list[str], *, source: Path) -> None:
    compact = " ".join(text.split())
    missing = [
        snippet for snippet in snippets if snippet not in text and " ".join(snippet.split()) not in compact
    ]
    assert not missing, f"{source}: missing {missing}"


def assert_public_safe(text: str, label: str) -> None:
    lower = text.lower()
    leaked = [marker for marker in PRIVATE_MARKERS if marker.lower() in lower]
    assert not leaked, f"{label} leaks private markers: {leaked}"


def main() -> int:
    protocol = read(PROTOCOL)
    local_plan = read(LOCAL_PLAN)
    auto_research_profile = read(AUTO_RESEARCH_PROFILE)
    auto_research_guide = read(AUTO_RESEARCH_GUIDE)
    protocol_index = read(PROTOCOL_INDEX)
    docs_index = read(DOCS_INDEX)
    changed_public_docs = "\n".join(
        [
            protocol,
            protocol_index,
            docs_index,
        ]
    )

    assert_public_safe(changed_public_docs, "multi-agent visible launcher docs")

    require(
        protocol,
        [
            "multi_agent_visible_launcher_v0",
            "local_agent_launch_plan_v0",
            "Domain capabilities",
            "not become a leader agent",
            "Ownership Split",
            "LoopX control plane",
            "Multi-agent visible launcher",
            "Host shell or app",
            "schema_version",
            "reasoning_contract",
            "default_reasoning_effort",
            "model_reasoning_effort",
            "shared_goal_surface",
            "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
            "agent-scoped `quota should-run`",
            "todo projection, frontier projection, and run history",
            "public-safe evidence",
            "all_lane_workspace_isolation=false",
            "only mutating attempts require a claimed worktree",
            "role_profile",
            "quota_guard",
            "frontier",
            "bootstrap_message",
            "visible_launch_command",
            "reasoning_effort",
            "lane_timeline",
            "The pane title is cosmetic",
            "Start Order",
            "Run `quota should-run --goal-id <goal-id> --agent-id <agent-id>`",
            "Print the domain frontier or a blocked reason",
            "Start the visible agent process only after the preceding packets are visible",
            "Host Controls",
            "attach",
            "stop",
            "retry",
            "visible acceptance markers",
            "Boundary",
            "hidden_prompt_injection",
            "public_safe_redaction",
            "Domain Adapter Responsibilities",
            "Acceptance Checks",
        ],
        source=PROTOCOL,
    )
    require(
        protocol,
        [
            "dry-run mode starts no process, runs no agent, writes no LoopX state, and\n   spends no quota",
            "execute mode still writes state and spends quota only through normal LoopX\n   writeback after validation",
            "workspace isolation scoped to mutating attempts rather than\n   splitting the shared goal surface",
        ],
        source=PROTOCOL,
    )
    forbidden = [
        "launcher owns promotion decisions",
        "all lanes must use separate goal state",
        "may hide guard output",
        "is a hidden scheduler",
    ]
    for phrase in forbidden:
        assert phrase not in protocol, f"forbidden phrase present: {phrase}"

    require(
        local_plan,
        [
            "local_agent_launch_plan_v0",
            "mode=dry_run",
            "It must not start a process",
        ],
        source=LOCAL_PLAN,
    )
    require(
        auto_research_profile,
        [
            "Host launcher",
            "Visible panes",
            "attach/stop controls",
            "The pane title is cosmetic",
        ],
        source=AUTO_RESEARCH_PROFILE,
    )
    require(
        auto_research_guide,
        [
            "The panes share the same LoopX\ngoal surface",
            "isolate only\nmutating evidence-runner attempts",
            "Each pane must route through its own quota/frontier/bootstrap path",
        ],
        source=AUTO_RESEARCH_GUIDE,
    )
    require(
        protocol_index,
        ["multi_agent_visible_launcher_v0", "multi-agent-visible-launcher-v0.md"],
        source=PROTOCOL_INDEX,
    )
    require(
        docs_index,
        ["Multi-agent visible launcher v0", "reference/protocols/multi-agent-visible-launcher-v0.md"],
        source=DOCS_INDEX,
    )

    print("multi-agent-visible-launcher-protocol-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
