"""Operator-supplied model credential facts shared by LoopX host surfaces.

This module reports credential *facts* and nothing else. It reads no credential
value, and it resolves nothing by itself.

Selection is a separate decision owned by the surface that runs the work: the
governed Turn host comes from ``turn_driver.host_binding.selected_turn_host``
and the steward channel endpoint comes from
``chat_manager.manager_channel_binding``. Both report the credential facts
quoted from here so their readback cannot drift apart, and both treat the
credential as authentication for the configuration that runs. A configured
credential is never a reason to re-point an explicitly selected surface: it
resolves only the shipped default of a surface that would otherwise have to run
on an individual CLI login.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

# Credential env vars the operator-supplied provider already reads. Only the
# variable name is ever reported back; values stay in the process environment.
OPERATOR_CREDENTIAL_ENV_VARS = ("DEEPSEEK_API_KEY",)
OPERATOR_ENDPOINT_ENV_VAR = "DEEPSEEK_BASE_URL"


def env_text(name: str, environ: Mapping[str, str] | None = None) -> str | None:
    """Return a stripped env value, or ``None`` when it is unset or blank."""

    source = os.environ if environ is None else environ
    value = str(source.get(name, "") or "").strip()
    return value or None


def configured_operator_credential(
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Return the configured operator credential env var name, else ``None``."""

    for name in OPERATOR_CREDENTIAL_ENV_VARS:
        if env_text(name, environ) is not None:
            return name
    return None


def operator_credential_configured(
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Whether any operator model credential is configured for this process."""

    return configured_operator_credential(environ) is not None
