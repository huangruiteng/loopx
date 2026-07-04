from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ...visible_multi_agent_launcher import wake_visible_multi_agent_panes


@dataclass(frozen=True)
class VisibleLaunchPolicy:
    """Generic visible-launch decisions shared by product presets."""

    launch_visible: bool
    wake_visible_after_launch: bool
    attach: bool


VisibleLauncherCallback = Callable[[dict[str, object], Path, Optional[str], Path], dict[str, object]]
VisibleLaunchExecutor = Callable[..., dict[str, object]]
VisibleWorkspacePolicy = Callable[[Path], Tuple[Optional[str], bool, bool]]


def resolve_visible_launch_policy(
    args: argparse.Namespace,
    *,
    launch_visible: bool,
    default_wake_allowed: bool,
    default_attach_allowed: bool,
    attach_wake_conflict_message: str | None = None,
) -> VisibleLaunchPolicy:
    """Resolve attach/wake policy without product-specific runner logic."""

    no_attach = bool(getattr(args, "no_attach", False))
    attach_requested = bool(getattr(args, "attach", False))
    if no_attach and attach_requested:
        raise ValueError("--attach cannot be combined with --no-attach")

    wake_setting = getattr(args, "wake_visible_after_launch", None)
    if wake_setting is True and attach_requested:
        raise ValueError(
            attach_wake_conflict_message
            or "--attach cannot be combined with --wake-visible-after-launch"
        )

    wake = False
    if launch_visible and default_wake_allowed:
        if wake_setting is None and attach_requested:
            wake = False
        else:
            wake = bool(wake_setting is not False)

    attach = bool(
        attach_requested
        or (
            launch_visible
            and default_attach_allowed
            and not no_attach
            and not wake
        )
    )
    return VisibleLaunchPolicy(
        launch_visible=bool(launch_visible),
        wake_visible_after_launch=wake,
        attach=attach,
    )


def resolve_codex_trust_workspace(
    args: argparse.Namespace,
    *,
    launch_visible: bool,
    default: bool,
) -> bool:
    """Resolve the optional Codex workspace trust default for visible launches."""

    if not launch_visible:
        return False
    trust_setting = getattr(args, "codex_trust_workspace", None)
    if trust_setting is None:
        return bool(default)
    return bool(trust_setting)


def make_visible_launcher_callback(
    *,
    launch_visible: bool,
    launch_executor: VisibleLaunchExecutor,
    launcher: str,
    tmux_bin: str,
    cli_bin: str,
    codex_bin: str,
    attach: bool,
    replace_existing: bool,
    workspace_policy: VisibleWorkspacePolicy,
) -> VisibleLauncherCallback | None:
    """Create the generic callback shape expected by visible demo runners."""

    if not launch_visible:
        return None

    def visible_launcher(
        payload: dict[str, object],
        registry_path: Path,
        runtime_root_arg: str | None,
        default_workspace: Path,
    ) -> dict[str, object]:
        workspace, create_workspace, codex_trust_workspace = workspace_policy(
            default_workspace
        )
        return launch_executor(
            payload,
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            launcher=launcher,
            tmux_bin=tmux_bin,
            cli_bin=cli_bin,
            codex_bin=codex_bin,
            attach=attach,
            replace_existing=replace_existing,
            workspace=workspace,
            create_workspace=create_workspace,
            codex_trust_workspace=codex_trust_workspace,
        )

    return visible_launcher


def make_visible_wake_callback(
    *,
    tmux_bin: str,
) -> Callable[[str, list[str]], dict[str, object]]:
    """Return a pane-local A2A wake callback for visible launcher integrations."""

    def visible_wake(session: str, lanes: Iterable[str]) -> dict[str, object]:
        return wake_visible_multi_agent_panes(
            session_name=session,
            tmux_bin=tmux_bin,
            lanes=lanes,
            execute=True,
        )

    return visible_wake
