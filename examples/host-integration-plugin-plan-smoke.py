#!/usr/bin/env python3
"""Smoke-test the host integration plugin plan contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN = REPO_ROOT / "docs" / "reference" / "protocols" / "host-integration-plugin-plan-v0.md"
PROTOCOL_INDEX = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
DOCS_INDEX = REPO_ROOT / "docs" / "README.md"


def require(text: str, snippets: list[str], *, source: Path) -> None:
    compact = " ".join(text.split())
    missing = [
        snippet
        for snippet in snippets
        if snippet not in text and " ".join(snippet.split()) not in compact
    ]
    assert not missing, f"{source}: missing {missing}"


def main() -> int:
    plan = PLAN.read_text(encoding="utf-8")
    protocol_index = PROTOCOL_INDEX.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")

    require(
        plan,
        [
            "host_integration_plugin_plan_v0",
            "skill-level LoopX slash-command fallback",
            "host-owned command registry",
            "not a shipped plugin manifest",
            "LoopX CLI as the source of truth",
            "codex_app_host_command_registry_v0",
            "host_integration_surface_v0",
            "session_runtime_loopx_projection_v0",
            "## Plugin Capability Set",
            "## Phased Path",
            "### Phase 0: Skill Fallback",
            "### Phase 1: Host Command Alias",
            "### Phase 2: Heartbeat Installer",
            "### Phase 3: Scheduler Hint Adapter",
            "### Phase 4: Controlled Write Tools",
            "## Acceptance Matrix",
            "loopx heartbeat-prompt --thin --goal-id <goal-id>",
            "stateful_backoff.apply_needed",
            "quota scheduler-ack-current",
            "last applied RRULE",
            "does not spend quota",
            "Raw transcript offered to plugin",
            "Plugin rejects or redacts the payload",
            "CLI unavailable",
            "install/doctor blocker",
            "raw_transcripts_accepted",
            "credentials_accepted",
            "public_local_paths_allowed",
        ],
        source=PLAN,
    )
    require(
        plan,
        [
            "Do not replace the CLI",
            "Do not store raw transcripts",
            "Do not treat a chat slash command as approval",
            "Do not make hidden headless execution the default",
            "Unknown `/loopx-debug-me`",
            "fails closed with `loopx slash-commands` help",
        ],
        source=PLAN,
    )
    assert plan.index("### Phase 0: Skill Fallback") < plan.index("### Phase 1: Host Command Alias")
    assert plan.index("### Phase 1: Host Command Alias") < plan.index("### Phase 2: Heartbeat Installer")
    assert plan.index("### Phase 2: Heartbeat Installer") < plan.index("### Phase 3: Scheduler Hint Adapter")
    assert plan.index("### Phase 3: Scheduler Hint Adapter") < plan.index("### Phase 4: Controlled Write Tools")
    assert "raw transcript material" not in plan.lower()

    require(
        protocol_index,
        ["host_integration_plugin_plan_v0", "host-integration-plugin-plan-v0.md"],
        source=PROTOCOL_INDEX,
    )
    require(
        docs_index,
        ["Host integration plugin plan v0", "reference/protocols/host-integration-plugin-plan-v0.md"],
        source=DOCS_INDEX,
    )
    print("host-integration-plugin-plan-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
