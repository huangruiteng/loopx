from __future__ import annotations

from typing import Any


DEEP_RESEARCH_CATALOG_ENTRY: dict[str, Any] = {
    "id": "deep-research",
    "origin": "builtin",
    "visibility": "public",
    "provider_id": "loopx-core",
    "documentation": {
        "source_root": "loopx/capabilities/deep_research",
        "site_root": "capabilities/deep-research",
        "canonical": "README.md",
    },
    "title": "Evidence-ledger deep research loop",
    "status": "experimental",
    "real_world_anchor": (
        "one user question driven by packet-cut expeditions over question, source, "
        "claim, and contradiction ledgers, ending in a citation-auditable report"
    ),
    "user_value": (
        "Run a bounded, auditable research session per project: claims must come from "
        "recorded sources, answers must cite recorded claims, and closeout is blocked "
        "while any contradiction stays unresolved."
    ),
    "entry_command": "loopx deepresearch start --question <text>",
    "commands": [
        {
            "command": "loopx deepresearch start --question <text> [--max-sources N] [--new-run]",
            "purpose": "Open a research run; archives the previous closed/stopped run instead of editing state files by hand.",
            "write_boundary": ".loopx/deepresearch/ state and report files only",
        },
        {
            "command": "loopx deepresearch status",
            "purpose": "Emit the expedition packet: contract, ledgers, next expedition, stop conditions, evidence commands.",
            "write_boundary": "read-only projection over the research ledger",
        },
        {
            "command": "loopx deepresearch add-source --url-or-path <ref> --tool <tool> --claims-json <json>",
            "purpose": "Record one consulted source and the claims extracted from it.",
            "write_boundary": "one ledger transaction under the project research lock",
        },
        {
            "command": "loopx deepresearch add-subquestion --text <text> --from-claim <claim-id>",
            "purpose": "Open a subquestion that derives from a recorded claim.",
            "write_boundary": "one ledger transaction under the project research lock",
        },
        {
            "command": "loopx deepresearch resolve-question --question-id <id> --answer <text> --evidence-claims <ids>",
            "purpose": "Answer a recorded question citing recorded evidence claims; contradictions touching the evidence must be resolved in the same transition.",
            "write_boundary": "one ledger transaction under the project research lock",
        },
        {
            "command": "loopx deepresearch resolve-contradiction --contradiction-id <id> --sides-with <claim-id> --rationale <text>",
            "purpose": "Close one open contradiction standalone with an explicit sides-with rationale.",
            "write_boundary": "one ledger transaction under the project research lock",
        },
        {
            "command": "loopx deepresearch close [--note <text>]",
            "purpose": "Terminal transition marking this run closed and its ledger immutable; the next start archives it.",
            "write_boundary": "marks the run closed; the next start performs the archive rotation",
        },
        {
            "command": "loopx deepresearch report",
            "purpose": "Render the citation-auditable markdown report from the ledgers.",
            "write_boundary": "writes .loopx/deepresearch/report.md only",
        },
    ],
    "implemented_protocols": [
        {
            "schema_version": "loopx_deepresearch_state_v0",
            "module": "loopx.deepresearch",
            "doc": "loopx/capabilities/deep_research/README.md",
        },
        {
            "schema_version": "loopx_deepresearch_packet_v0",
            "module": "loopx.deepresearch",
            "doc": "loopx/capabilities/deep_research/README.md",
        },
    ],
    "smokes": [
        "python3 -m pytest tests/test_deepresearch_command.py -q",
    ],
    "docs": [
        "loopx/capabilities/deep_research/README.md",
    ],
    "boundaries": [
        (
            "Distinct from the auto-research capability: auto-research launches "
            "role-scoped workers inside a LoopX goal for open exploration; "
            "deep-research is a single-session, user-facing evidence ledger whose "
            "truth is the .loopx/deepresearch state, not goal todos."
        ),
        (
            "The packet owns research progression and stop decisions; the model "
            "executes bounded expeditions and records typed ledger transitions only."
        ),
        (
            "Claims exist only when a tool the agent actually ran produced them; "
            "reports must keep every citation resolvable to a recorded source."
        ),
        (
            "One active run per project; finished or closed runs are archived under "
            ".loopx/deepresearch/archive/ by typed transitions, never by hand edits."
        ),
    ],
    "next_real_step": (
        "Keep the deep-research entrypoint as the single evidence-ledger authority and "
        "reuse LoopX goal/todo/quota projections rather than adding a second scheduler."
    ),
}
