#!/usr/bin/env python
"""Pier, with agent-image builds pointed at domestic mirrors.

Pier bakes the agent harness into every task image. Each of DeepSWE's 113 tasks
ships its own base image, so this layer is rebuilt 113 times and never reused
between tasks — whatever it costs, it costs 113 times, per harness. From here
the upstream install path is slow or fatal at three points:

  * ``apt-get update`` hits deb.debian.org, which does not answer at all from
    this host; a build sat there for 25 min before it was killed.
  * ``curl -LsSf https://astral.sh/uv/... | sh`` (mini-swe-agent) pulls a 17 MB
    binary from GitHub only to *downgrade* the uv 0.9.18 these images already
    carry in /root/.local/bin.
  * ``uv tool install`` resolves against pypi.org, unreachable here without the
    proxy and timing out even with it; ``npm install -g`` against
    registry.npmjs.org (claude-code, codex, opencode) works but at 0.8 MB/s.

So: keep the image's own uv when it has one, and resolve everything from
mirrors.aliyun.com / registry.npmmirror.com, which answer directly in ~0.2-0.5 s
at 2.8-5.6 MB/s and need no proxy. Measured end to end on one task image for
mini-swe-agent: 366 s and then a failure, against 8.8 s.

The proxy still applies to the build (run.sh points DOCKER_CONFIG at
mr_common/docker-config); this only removes the steps that depend on it being
both up and fast. The mirror hosts are in that file's ``noProxy`` on purpose —
routed through the proxy they come back 502, and they need no proxy anyway.

run.sh calls this instead of .venv/bin/pier. A plain `pier` is untouched and
still behaves exactly as upstream ships it.
"""

from __future__ import annotations

import importlib
import os
import re
import sys

PYPI_INDEX = "https://mirrors.aliyun.com/pypi/simple/"
NPM_REGISTRY = "https://registry.npmmirror.com"
APT_MIRROR_HOST = "mirrors.aliyun.com"

# UV_DEFAULT_INDEX is what uv >= 0.6 reads; UV_INDEX_URL keeps older uv (and
# pier's pinned 0.7.13, should an image ever need it fetched) on the mirror too.
PYPI_ENV = {
    "UV_DEFAULT_INDEX": PYPI_INDEX,
    "UV_INDEX_URL": PYPI_INDEX,
    "PIP_INDEX_URL": PYPI_INDEX,
    "UV_HTTP_TIMEOUT": "120",
}

# npm reads either spelling depending on version; setting both is free.
NPM_ENV = {
    "NPM_CONFIG_REGISTRY": NPM_REGISTRY,
    "npm_config_registry": NPM_REGISTRY,
}

# Matched verbatim against pier's install script, so an upstream change to the
# pinned uv version makes the patch fall through loudly rather than silently
# stop applying.
UV_INSTALL_LINE = "curl -LsSf https://astral.sh/uv/0.7.13/install.sh | sh"

UV_REUSE_BLOCK = f"""if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  {UV_INSTALL_LINE}
fi
mkdir -p "$HOME/.local/bin"
[ -f "$HOME/.local/bin/env" ] || : > "$HOME/.local/bin/env" """

# Runs before the package manager. Images that are not Debian match no files.
APT_MIRROR_PREFIX = (
    "for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources"
    " /etc/apt/sources.list.d/*.list; do"
    ' [ -f "$f" ] || continue;'
    f' sed -i "s|deb.debian.org|{APT_MIRROR_HOST}|g;'
    f' s|security.debian.org|{APT_MIRROR_HOST}|g" "$f";'
    " done 2>/dev/null; true; "
)

# Every harness Pier can install that we might sweep with. Listed explicitly
# rather than walked from __subclasses__: the subclasses only exist once their
# module is imported, and an agent that quietly missed the patch would show up
# as a 25-minute hang rather than an error.
HARNESSES = (
    ("pier.agents.installed.mini_swe_agent", "MiniSweAgent"),
    ("pier.agents.installed.claude_code", "ClaudeCode"),
    ("pier.agents.installed.codex", "Codex"),
    ("pier.agents.installed.opencode", "OpenCode"),
    ("pier.agents.installed.cursor_cli", "CursorCli"),
    ("pier.agents.installed.gemini_cli", "GeminiCli"),
)


def rewrite_step(step) -> list[str]:
    """Point one install step at the mirrors. Returns what it changed."""
    changed = []
    run = step.run

    if ("apt-get" in run or "apk add" in run) and APT_MIRROR_PREFIX not in run:
        run = APT_MIRROR_PREFIX + run
        changed.append("apt")

    if UV_INSTALL_LINE in run:
        run = run.replace(UV_INSTALL_LINE, UV_REUSE_BLOCK)
        changed.append("uv-reuse")
    if "uv tool install" in run or "uv pip install" in run or "pip install" in run:
        step.env = {**(step.env or {}), **PYPI_ENV}
        changed.append("pypi")

    if "npm install" in run or "npm i " in run:
        step.env = {**(step.env or {}), **NPM_ENV}
        # Registry downloads occasionally reset the TLS connection on this host;
        # make image builds retry instead of turning a transient reset into an
        # invalid benchmark trial.
        run = run.replace(
            "npm install -g @openai/codex@latest",
            "npm install --fetch-retries=5 --fetch-retry-mintimeout=5000 "
            "--fetch-retry-maxtimeout=60000 -g @openai/codex@latest",
        )
        # Debian task images already ship node/npm. Avoid the upstream nvm
        # bootstrap from GitHub, which is unreachable when the host proxy is
        # down; install the harness directly from the configured npm mirror.
        if "nvm-sh/nvm" in run:
            run = re.sub(
                r"else\s+curl -o- https://raw\.githubusercontent\.com/nvm-sh/nvm/.*?; fi && codex --version",
                "else npm install --fetch-retries=5 --fetch-retry-mintimeout=5000 "
                "--fetch-retry-maxtimeout=60000 -g @openai/codex@latest; "
                "fi && codex --version",
                run,
                flags=re.DOTALL,
            )
            changed.append("nvm-bypass")
        changed.append("npm")

    step.run = run
    return changed


def patch_harnesses() -> None:
    """Wrap install_spec on every known harness class."""
    patched_any = False
    for module_path, class_name in HARNESSES:
        try:
            cls = getattr(importlib.import_module(module_path), class_name)
        except (ImportError, AttributeError) as exc:
            print(f"pier_cn: skipping {class_name} ({exc})", file=sys.stderr)
            continue

        original = cls.install_spec

        def install_spec(self, _original=original, _name=class_name):
            spec = _original(self)
            changed = []
            for step in spec.steps:
                changed += rewrite_step(step)
            if not changed:
                # Pier changed its install script out from under the patch: say
                # so rather than let a sweep crawl or die one task at a time.
                print(
                    f"pier_cn: WARNING — no install step of {_name} matched; its "
                    "build will use upstream's GitHub/PyPI/npm path and may hang.",
                    file=sys.stderr,
                )
            return spec

        cls.install_spec = install_spec
        patched_any = True

    if not patched_any:
        raise SystemExit("pier_cn: could not patch any harness — refusing to run")


def patch_goal_mode() -> None:
    """Point the ``codex`` agent name at one of the experiment's two arms.

    Pier's CLI validates ``--agent`` against the ``AgentName`` enum, so the
    factory's import-path loader ('module:Class') cannot be reached from the
    command line and a new name cannot simply be added. Rebinding the existing
    name suits the experiment better anyway: both arms then run byte-for-byte
    identical commands and differ only in this one environment variable, which
    is what makes the comparison controlled.

        MR_CODEX_ARM=goal    Goal attached over the app-server (treatment)
        MR_CODEX_ARM=plain   same objective text and web_search setting, but
                             app-server transport with no Goal (control)
        MR_CODEX_ARM=loopx   Codex driven by LoopX's governed Turn loop
        MR_CODEX_ARM=loopx-native
                             LoopX through its own product path: formal release
                             install, LoopX-rendered Goal body, and continuation
                             owned by app-server.  `loopx` predates it and drove
                             `turn run-once` from an outer loop with a
                             hand-written goal document, which LoopX's own
                             benchmark method rules out; its results describe
                             that wrapper rather than this product.
        MR_CODEX_ARM=loopx-native-deepseek
                             Byte-identical to loopx-native; only the arm name
                             differs, so it lands in its own
                             deepswe-<stratum>-loopx-native-deepseek job
                             directory instead of overwriting the gpt-5.5
                             native run already recorded there. Combine with
                             MR_MODEL to actually route to a different model.
        MR_CODEX_ARM=loopx-native-deepseek-flash
                             Same as loopx-native-deepseek; a separate alias so
                             a deepseek-v4-flash sweep lands in its own job
                             directory instead of mixing into
                             deepswe-<stratum>-loopx-native-deepseek, which
                             already holds the deepseek-v4-pro results.
        MR_CODEX_ARM=loopx-native-codex-cli
                             Official `codex_cli` profile through LoopX
                             `turn run-once`, launching real `codex exec` turns.
        MR_CODEX_ARM=loopx-native-heartbeat
                             Official `generic_cli` heartbeat profile; recurring
                             wakes are owned by the benchmark supervisor.

    MR_GOAL_MODE=1 is still honoured as a synonym for the goal arm. Unset, an
    ordinary sweep is untouched.
    """
    arm = os.environ.get("MR_CODEX_ARM", "").strip().lower()
    if not arm and os.environ.get("MR_GOAL_MODE", "") not in ("", "0"):
        arm = "goal"
    if not arm:
        return
    if arm not in ("goal", "plain", "loopx", "loopx-native", "loopx-native-deepseek",
                  "loopx-native-deepseek-flash", "loopx-native-codex-cli",
                  "loopx-native-heartbeat"):
        raise SystemExit(
            "pier_cn: MR_CODEX_ARM must be 'goal', 'plain', 'loopx', 'loopx-native', "
            "'loopx-native-deepseek', 'loopx-native-deepseek-flash', "
            "'loopx-native-codex-cli' or 'loopx-native-heartbeat', "
            f"got {arm!r}"
        )

    from pier.agents.factory import AgentFactory
    from pier.models.agent.name import AgentName

    import goal_codex

    if arm in ("loopx-native", "loopx-native-deepseek", "loopx-native-deepseek-flash",
               "loopx-native-codex-cli", "loopx-native-heartbeat"):
        os.environ["MR_LOOPX_MODE"] = {
            "loopx-native": "ssh-goal",
            "loopx-native-deepseek": "ssh-goal",
            "loopx-native-deepseek-flash": "ssh-goal",
            "loopx-native-codex-cli": "codex-cli",
            "loopx-native-heartbeat": "heartbeat",
        }[arm]
        import loopx_native_codex

        agent = {
            "loopx-native": loopx_native_codex.LoopxNativeCodex,
            "loopx-native-deepseek": loopx_native_codex.LoopxNativeCodex,
            "loopx-native-deepseek-flash": loopx_native_codex.LoopxNativeCodex,
            "loopx-native-codex-cli": loopx_native_codex.LoopxCodexCliCodex,
            "loopx-native-heartbeat": loopx_native_codex.LoopxHeartbeatCodex,
        }[arm]
    else:
        agent = {
            "goal": goal_codex.GoalCodex,
            "plain": goal_codex.PlainAppServerCodex,
            "loopx": goal_codex.LoopxCodex,
        }[arm]
    AgentFactory._AGENT_MAP[AgentName.CODEX] = agent
    print(
        f"pier_cn: MR_CODEX_ARM={arm} — 'codex' now runs as {agent.__qualname__}",
        file=sys.stderr,
    )


def patch_claude_arm() -> None:
    """Point the ``claude-code`` agent name at one of its two arms.

    The same rebinding trick as ``patch_goal_mode``, on a separate environment
    variable so the two agent families stay independent: a sweep can run the
    Codex arms and the Claude Code arms without either one's setting leaking
    into the other.

        MR_CLAUDE_ARM=plain   stock `claude --print`, plus the objective text
                              that the LoopX arm necessarily carries (control)
        MR_CLAUDE_ARM=loopx   Claude Code driven by LoopX's governed Turn loop

    There is no ``goal`` arm here: Claude Code's native `/loop` is interactive
    and has no `--print` entry point, so it cannot be exercised inside Pier's
    one-shot container invocation. Unset, an ordinary sweep is untouched.
    """
    arm = os.environ.get("MR_CLAUDE_ARM", "").strip().lower()
    if not arm:
        return
    if arm not in ("plain", "loopx"):
        raise SystemExit(
            f"pier_cn: MR_CLAUDE_ARM must be 'plain' or 'loopx', got {arm!r}"
        )

    from pier.agents.factory import AgentFactory
    from pier.models.agent.name import AgentName

    import goal_claude

    agent = {
        "plain": goal_claude.PlainClaudeCode,
        "loopx": goal_claude.LoopxClaudeCode,
    }[arm]
    AgentFactory._AGENT_MAP[AgentName.CLAUDE_CODE] = agent
    print(
        f"pier_cn: MR_CLAUDE_ARM={arm} — 'claude-code' now runs as {agent.__qualname__}",
        file=sys.stderr,
    )


def patch_modelonly_network() -> None:
    """Attach Pier's task container to the internal model-only network.

    The compose overlay is appended after Pier's generated files, so the task
    can reach the host gateway at 127.0.0.1 without relying on the egress
    proxy or the container's loopback address.
    """
    if os.environ.get("MR_MODELONLY_NET", "0") not in ("1", "true", "yes"):
        return
    from pathlib import Path
    from pier.environments.docker.docker import DockerEnvironment

    local_agent_base = os.environ.get("MR_LOCAL_AGENT_BASE_IMAGE", "").strip()
    if local_agent_base and not getattr(
        DockerEnvironment._prepare_agent_build_context, "_deepswe_local_base", False
    ):
        original_prepare = DockerEnvironment._prepare_agent_build_context

        def prepare_agent_build_context(self):
            # BuildKit performs a registry metadata HEAD even when the remote
            # base image was already loaded. Use the explicit local alias only
            # while Pier writes the generated agent Dockerfile; the task config
            # is restored before Compose starts, so scoring metadata remains
            # unchanged.
            original_image = self.task_env_config.docker_image
            self.task_env_config.docker_image = local_agent_base
            try:
                return original_prepare(self)
            finally:
                self.task_env_config.docker_image = original_image

        prepare_agent_build_context._deepswe_local_base = True
        DockerEnvironment._prepare_agent_build_context = prepare_agent_build_context
        print(
            f"pier_cn: local agent base override={local_agent_base}",
            file=sys.stderr,
        )

    overlay = Path(__file__).resolve().with_name("docker-compose-modelonly.yaml")
    if not overlay.exists():
        raise SystemExit(f"pier_cn: missing model-only compose overlay: {overlay}")
    original = DockerEnvironment._docker_compose_paths
    if getattr(original, "_deepswe_modelonly", False):
        return

    def paths(self):
        # Verifier environments are deliberately no-network. Adding a
        # `networks` key there conflicts with Compose's `network_mode: none`.
        # Pier uses `no-network` for both agent and verifier task declarations;
        # the verifier's environment directory is the reliable distinction.
        if Path(self.environment_dir).name == "tests":
            return list(original.fget(self))
        result = list(original.fget(self))
        result.append(overlay)
        return result

    paths._deepswe_modelonly = True
    DockerEnvironment._docker_compose_paths = property(paths)
    original_agent_env = DockerEnvironment.agent_process_env

    def agent_process_env(self, env):
        result = dict(original_agent_env(self, env) or {})
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            result[key] = ""
        no_proxy = result.get("NO_PROXY", "")
        result["NO_PROXY"] = ",".join(
            item for item in (no_proxy, "localhost", "127.0.0.1", "127.0.0.1") if item
        )
        result["no_proxy"] = result["NO_PROXY"]
        return result

    agent_process_env._deepswe_modelonly = True
    DockerEnvironment.agent_process_env = agent_process_env
    print(f"pier_cn: model-only network overlay={overlay}", file=sys.stderr)


def main() -> int:
    patch_harnesses()
    patch_goal_mode()
    patch_claude_arm()
    patch_modelonly_network()
    from pier.cli.main import app

    return app()


if __name__ == "__main__":
    sys.exit(main())
