from __future__ import annotations

import argparse

from ..codex_cli_probe import DEFAULT_CODEX_BIN, DEFAULT_TIMEOUT_SECONDS


def _add_project_arguments(
    parser: argparse.ArgumentParser,
    *,
    agent_help: str = "Registered LoopX agent id to include in quota/claim instructions.",
) -> None:
    parser.add_argument("--project", default=".", help="Project directory to start from.")
    parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    parser.add_argument("--agent-id", help=agent_help)
    parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )


def _add_codex_probe_arguments(
    parser: argparse.ArgumentParser,
    *,
    codex_help: str = "Codex CLI executable to probe and reference in fallback commands.",
) -> None:
    parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help=codex_help,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )


def _add_optional_proof_fixture(parser: argparse.ArgumentParser, *, help_text: str) -> None:
    parser.add_argument("--proof-fixture", help=help_text)


def _add_headless_fallback_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Deprecated and ignored; headless codex exec is disabled for this default /goal path.",
    )
