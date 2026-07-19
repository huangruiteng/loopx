#!/usr/bin/env python3
"""Smoke-check the generic multi-agent visible launcher protocol contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/reference/protocols/multi-agent-visible-launcher-v0.md"
THREE_LAYER = ROOT / "docs/reference/protocols/multi-agent-three-layer-minimality-v0.md"
LOCAL_PLAN = ROOT / "docs/reference/protocols/local-agent-launch-plan-v1.md"
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
    three_layer = read(THREE_LAYER)
    local_plan = read(LOCAL_PLAN)
    auto_research_profile = read(AUTO_RESEARCH_PROFILE)
    auto_research_guide = read(AUTO_RESEARCH_GUIDE)
    protocol_index = read(PROTOCOL_INDEX)
    docs_index = read(DOCS_INDEX)
    changed_public_docs = "\n".join(
        [
            protocol,
            three_layer,
            protocol_index,
        ]
    )

    assert_public_safe(changed_public_docs, "multi-agent visible launcher docs")

    require(
        protocol,
        [
            "multi_agent_visible_launcher_v0",
            "local_agent_launch_plan_v1",
            "Domain capabilities",
            "not become a leader agent",
            "multi_agent_three_layer_minimality_contract_v0",
            "both the user-facing recipe and the domain preset stay thin",
            "Kernel Module",
            "loopx/control_plane/agents/multi_agent/",
            "generic_multi_agent_role_profile_v0",
            "multi_agent_three_layer_minimality_contract_v0",
            "compact human status",
            "runtime scripts for scoped LoopX wrappers",
            "pane-local tick scripts",
            "machine JSON wrapper policy",
            "visible_multi_agent_launcher.py",
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
            "Prepare the role profile, scoped LoopX wrappers, and bootstrap prompt as\n   local artifacts",
            "Start one fresh interactive Codex CLI TUI per role window",
            "Let the Codex role read quota/frontier/todo state through the pane-local\n   LoopX wrapper inside the TUI",
            "Host Controls",
            "attach",
            "stop",
            "retry",
            "visible acceptance proof",
            "Interactive TUI Contract",
            "no extra frontier/status JSON window by default",
            "not `codex exec`",
            "no pre-Codex character stream",
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
            "Visible Codex TUI panes must not default into a generated demo-local git\nworktree or control-plane repository",
            "generated workspace trust prompt",
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
        three_layer,
        [
            "multi_agent_three_layer_minimality_contract_v0",
            "User layer",
            "Preset layer",
            "Kernel layer",
            "user_and_preset_stay_thin_kernel_owns_reusable_mechanics",
            "The goal is not only to minimize the user's snippet",
            "Auto-research is one preset on top of the generic kernel",
            "another multi-agent product can reuse the same kernel",
        ],
        source=THREE_LAYER,
    )
    require(
        local_plan,
        [
            "local_agent_launch_plan_v1",
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
            "start one fresh interactive Codex CLI TUI per role",
        ],
        source=AUTO_RESEARCH_PROFILE,
    )
    require(
        auto_research_guide,
        [
            "The panes share the same LoopX\ngoal surface",
            "isolate only mutating research-executor attempts",
            "Each Codex TUI role must route through its own quota/frontier/worker-turn path",
            "first show the Codex CLI TUI",
            "should not default into the demo-local\ncontrol-plane repository or generated lane worktrees",
        ],
        source=AUTO_RESEARCH_GUIDE,
    )
    require(
        protocol_index,
        [
            "multi_agent_three_layer_minimality_contract_v0",
            "multi-agent-three-layer-minimality-v0.md",
            "multi_agent_visible_launcher_v0",
            "multi-agent-visible-launcher-v0.md",
        ],
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
