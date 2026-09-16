"""Credential-resolved default Turn host and managed executor readback.

The Turn host is **selected, never inferred from a launch-time surprise**. An
explicit ``--host`` or ``LOOPX_TURN_HOST`` is always honoured, and the shipped
default is resolved once from the operator's own credential facts.

- an operator credential (``DEEPSEEK_API_KEY``) selects the managed default
  ``dsh``: the managed execution unit the steward drives runs on the DeepSeek
  Harness host, billed to the operator's own endpoint;
- with no credential configured the individual default ``codex-cli`` applies
  instead, because the managed host cannot be authenticated without one -- and
  refusing to run is worse than running the individual CLI host this machine
  can already use;
- an explicit selection is never re-pointed by a credential: configuring or
  removing ``DEEPSEEK_API_KEY`` moves the shipped default only, never a host
  the operator already selected.

Both defaults are read back with their source, so an operator can always tell a
product default from an explicit selection instead of inferring it.

``managed_executor_binding`` turns the selection plus the operator environment
into the readback a caller can act on before a Turn runs: which executor the
plan would use, how that executor is billed and bounded, whether it can launch
here, which execution profile (provider, model, reasoning effort) runs on it,
and -- when it cannot launch -- one typed reason naming the missing fact. The
Turn executor fails closed on that verdict, so a bounded Turn never drifts onto
a host the operator did not select, nor onto a profile the endpoint is known to
reject.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from typing import Any, Callable

from ..operator_credential import (
    OPERATOR_CREDENTIAL_ENV_VARS,
    OPERATOR_ENDPOINT_ENV_VAR,
    configured_operator_credential,
    env_text,
)
from .execution_profile import (
    managed_execution_profile,
    managed_execution_profile_line,
    managed_profile_unavailable_reason,
)

# The shipped default is resolved from one fact: whether the operator configured
# a credential for the managed endpoint. An explicit selection always wins over
# this default, and nothing else in this module reads the environment to decide
# *which* host runs.
MANAGED_TURN_HOST = "dsh"
INDIVIDUAL_TURN_HOST = "codex-cli"
TURN_HOST_ENV_VAR = "LOOPX_TURN_HOST"
TURN_HOST_SOURCE_EXPLICIT_CONFIG = "explicit_config"
TURN_HOST_SOURCE_OPERATOR_CREDENTIAL = "operator_credential"
TURN_HOST_SOURCE_NO_OPERATOR_CREDENTIAL = "no_operator_credential"

MANAGED_EXECUTOR_BINDING_SCHEMA_VERSION = "managed_executor_binding_v0"
# Executor kinds name where a Turn's model work is billed and bounded rather
# than which adapter is launched: a managed executor runs on an
# operator-supplied credential, an individual executor on one person's own CLI
# login, and a generic executor on a caller-supplied adapter command.
EXECUTOR_KIND_MANAGED = "managed"
EXECUTOR_KIND_INDIVIDUAL = "individual"
EXECUTOR_KIND_GENERIC = "generic"
INDIVIDUAL_CLI_HOSTS = frozenset({INDIVIDUAL_TURN_HOST, "claude-code"})
MANAGED_HOST = MANAGED_TURN_HOST

# The built-in dsh host launches the DeepSeek Harness runtime unless the caller
# supplies the explicit runner hook, so that module being importable is the
# launchability fact this projection checks without side effects.
DSH_RUNTIME_MODULE = "deepseek_harness"
DSH_RUNTIME_UNAVAILABLE = "dsh_runtime_unavailable"
# A managed host is billed to the operator's own endpoint. Without the operator
# credential (or an explicit injected runner) LoopX cannot authenticate that
# endpoint, so it refuses instead of letting the managed default consume
# whatever personal login happens to exist on the machine.
OPERATOR_CREDENTIAL_UNCONFIGURED = "operator_credential_unconfigured"
# Operator-reachable exits from a fail-closed managed executor. A refusal that
# names only the missing fact leaves the operator to guess the way out, so the
# same typed readback names the exits as codes. These describe what the operator
# can change here; they never select a host, endpoint, or model themselves.
REMEDY_CONFIGURE_OPERATOR_CREDENTIAL = "configure_operator_credential"
REMEDY_CONFIGURE_DSH_RUNTIME = "configure_dsh_runtime"
REMEDY_CORRECT_EXECUTION_PROFILE = "correct_execution_profile"
REMEDY_SELECT_INDIVIDUAL_HOST = "select_individual_host"


def selected_turn_host(
    environ: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Return the selected default Turn host and the source that selected it.

    An explicit ``LOOPX_TURN_HOST`` wins. Otherwise the operator's own
    credential facts resolve the shipped default: a configured operator
    credential runs the managed host on that credential, and its absence runs
    the individual CLI host instead of a managed host nothing can authenticate.
    """

    explicit = env_text(TURN_HOST_ENV_VAR, environ)
    if explicit:
        return explicit, TURN_HOST_SOURCE_EXPLICIT_CONFIG
    if configured_operator_credential(environ):
        return MANAGED_TURN_HOST, TURN_HOST_SOURCE_OPERATOR_CREDENTIAL
    return (
        INDIVIDUAL_TURN_HOST,
        TURN_HOST_SOURCE_NO_OPERATOR_CREDENTIAL,
    )


def resolve_default_turn_host(environ: Mapping[str, str] | None = None) -> str:
    """Return the selected default Turn host."""

    return selected_turn_host(environ)[0]


def _configured_env_name(name: str, environ: Mapping[str, str] | None) -> str | None:
    return env_text(name, environ) and name


def dsh_runtime_importable(
    module_probe: Callable[[str], bool] | None = None,
) -> bool:
    """Whether the DeepSeek Harness runtime the built-in dsh host launches exists."""

    if module_probe is not None:
        return bool(module_probe(DSH_RUNTIME_MODULE))
    try:
        return importlib.util.find_spec(DSH_RUNTIME_MODULE) is not None
    except (ImportError, ValueError):
        return False


def _managed_unavailable_remediation(reason: str | None) -> list[str]:
    """Name the operator-reachable exits from one managed refusal.

    The list is empty whenever the managed executor can launch, so a caller
    reads the same field in both states instead of branching on its presence.
    Selecting an individual host is always one exit, because it is the
    documented alternative to a managed host nothing here can authenticate.
    """

    if reason is None:
        return []
    remedy_by_reason = {
        DSH_RUNTIME_UNAVAILABLE: REMEDY_CONFIGURE_DSH_RUNTIME,
        OPERATOR_CREDENTIAL_UNCONFIGURED: REMEDY_CONFIGURE_OPERATOR_CREDENTIAL,
    }
    return [
        remedy_by_reason.get(reason, REMEDY_CORRECT_EXECUTION_PROFILE),
        REMEDY_SELECT_INDIVIDUAL_HOST,
    ]


def managed_executor_binding(
    host: str,
    *,
    environ: Mapping[str, str] | None = None,
    dsh_runner_configured: bool = False,
    module_probe: Callable[[str], bool] | None = None,
    provider: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Project the executor one planned Turn would run on.

    ``available`` is ``False`` only when LoopX can prove the planned executor
    cannot launch here, which is what a caller has to fail closed on. ``None``
    records that this projection does not probe that executor kind, so it makes
    no claim rather than an unproven ``True``.

    ``execution_profile`` is the managed profile this executor would run -- and,
    with it, the provider claims to authenticate. It is ``None`` for every
    non-managed executor because neither the profile nor the credential belongs
    to an individual or generic host.
    """

    if host == MANAGED_HOST:
        credential_env = configured_operator_credential(environ)
        runtime_available = bool(
            dsh_runner_configured or dsh_runtime_importable(module_probe)
        )
        operator_credential_bound = bool(credential_env or dsh_runner_configured)
        profile = managed_execution_profile(
            environ,
            provider=provider,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        profile_reason = managed_profile_unavailable_reason(profile)
        if not runtime_available:
            unavailable_reason: str | None = DSH_RUNTIME_UNAVAILABLE
        elif not operator_credential_bound:
            unavailable_reason = OPERATOR_CREDENTIAL_UNCONFIGURED
        else:
            unavailable_reason = profile_reason
        return {
            "schema_version": MANAGED_EXECUTOR_BINDING_SCHEMA_VERSION,
            "executor": host,
            "executor_kind": EXECUTOR_KIND_MANAGED,
            "credential_env": credential_env,
            "endpoint_env": _configured_env_name(OPERATOR_ENDPOINT_ENV_VAR, environ),
            "execution_profile": managed_execution_profile_line(profile),
            # Billing boundary, stated instead of assumed: a managed executor is
            # operator-credential-bound only when the credential or an explicit
            # runner hook is configured here.
            "operator_credential_bound": operator_credential_bound,
            "available": unavailable_reason is None,
            "unavailable_reason": unavailable_reason,
            "unavailable_remediation": _managed_unavailable_remediation(
                unavailable_reason
            ),
        }
    return {
        "schema_version": MANAGED_EXECUTOR_BINDING_SCHEMA_VERSION,
        "executor": host,
        "executor_kind": (
            EXECUTOR_KIND_INDIVIDUAL
            if host in INDIVIDUAL_CLI_HOSTS
            else EXECUTOR_KIND_GENERIC
        ),
        "credential_env": None,
        "endpoint_env": None,
        "execution_profile": None,
        "operator_credential_bound": False,
        "available": None,
        "unavailable_reason": None,
        "unavailable_remediation": [],
    }


def managed_executor_payload_entry(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return the execution payload's ``managed_executor`` entry, when planned.

    Reading the entry from the plan keeps one authority for the executor
    identity: the payload quotes the binding the plan resolved instead of
    re-deriving an executor from the launched host.
    """

    binding = plan.get("managed_executor")
    return {"managed_executor": dict(binding)} if isinstance(binding, Mapping) else {}


def managed_executor_unavailable_payload(
    plan: Mapping[str, Any],
    *,
    execute: bool,
    host_projection: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return the fail-closed execution payload for an unlaunchable executor.

    ``None`` means the plan makes no claim that its executor cannot launch, so
    the Turn continues normally. A returned payload stops the Turn before the
    journal, the host, and quota with no effect recorded, so a bounded Turn
    cannot quietly move onto a different executor than the plan read back.
    """

    if not execute:
        return None
    binding = plan.get("managed_executor")
    if not isinstance(binding, Mapping) or binding.get("available") is not False:
        return None
    remediation = binding.get("unavailable_remediation")
    return {
        "status": "unavailable",
        "host": dict(host_projection),
        "reason": str(binding.get("unavailable_reason") or ""),
        # The operator-facing refusal carries the exits as data, so a caller
        # does not have to re-derive them from the reason string.
        "remediation": [
            str(code)
            for code in (remediation if isinstance(remediation, list) else [])
            if str(code)
        ],
        "remediation_host": INDIVIDUAL_TURN_HOST,
        "remediation_env_vars": list(OPERATOR_CREDENTIAL_ENV_VARS),
    }


def managed_executor_remediation_projection(
    journal: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the refusal's remediation entry for a public payload, else ``{}``.

    Only a refusal that named at least one exit projects anything, so a payload
    that can launch stays byte-identical to the one before this field existed.
    """

    remediation = journal.get("remediation")
    if not isinstance(remediation, list) or not remediation:
        return {}
    projection: dict[str, Any] = {
        "remediation": [str(code) for code in remediation if str(code)]
    }
    host = journal.get("remediation_host")
    if isinstance(host, str) and host:
        projection["remediation_host"] = host
    env_vars = journal.get("remediation_env_vars")
    if isinstance(env_vars, list):
        projection["remediation_env_vars"] = [
            str(name) for name in env_vars if str(name)
        ]
    return projection
