from __future__ import annotations

import json
import os
import socket
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..quota.turn_envelope import (
    quota_action_signature_document,
    turn_envelope_action_signature_document,
)
from .model_behavior_qualification import (
    MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
    ModelBehaviorActor,
    normalize_model_behavior_actor_request,
)
from .onboarding_model_behavior_qualification import (
    ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
    normalize_onboarding_model_behavior_actor_request,
)


DOUBAO_2_1_PRO_MODEL = "doubao-seed-2-1-pro-260628"
DOUBAO_2_1_TURBO_MODEL = "doubao-seed-2-1-turbo-260628"
DOUBAO_CHAT_COMPLETIONS_ENDPOINT = (
    "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
)
ARK_API_KEY_ENV = "ARK_API_KEY"
DOUBAO_MODEL_ENV = "LOOPX_MODEL_BEHAVIOR_MODEL"
MODEL_BEHAVIOR_PROVIDER_INPUT_SCHEMA_VERSION = "model_behavior_provider_input_v0"

_ALLOWED_MODELS = {DOUBAO_2_1_PRO_MODEL, DOUBAO_2_1_TURBO_MODEL}
_MAX_PROVIDER_RESPONSE_BYTES = 1_048_576
_MAX_DECISION_TOKENS = 4096


class DoubaoActorTransport(Protocol):
    def __call__(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


class DoubaoActorTransportError(RuntimeError):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _direct_ark_transport(
    *,
    endpoint: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout_seconds: float,
) -> Mapping[str, Any]:
    if endpoint != DOUBAO_CHAT_COMPLETIONS_ENDPOINT:
        raise DoubaoActorTransportError(
            "Doubao actor endpoint is not the canonical Ark endpoint",
            error_code="noncanonical_endpoint",
        )
    request = Request(endpoint, data=body, headers=dict(headers), method="POST")
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise DoubaoActorTransportError(
            f"Doubao actor request failed with HTTP status {exc.code}",
            error_code="provider_http_error",
        ) from None
    except TimeoutError:
        raise DoubaoActorTransportError(
            "Doubao actor provider timed out",
            error_code="provider_timeout",
        ) from None
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise DoubaoActorTransportError(
                "Doubao actor provider timed out",
                error_code="provider_timeout",
            ) from None
        raise DoubaoActorTransportError(
            "Doubao actor provider transport failed",
            error_code="provider_transport_failed",
        ) from None
    if len(payload) > _MAX_PROVIDER_RESPONSE_BYTES:
        raise DoubaoActorTransportError(
            "Doubao actor response exceeded the size limit",
            error_code="provider_response_too_large",
        )
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DoubaoActorTransportError(
            "Doubao actor returned invalid JSON",
            error_code="provider_invalid_json",
        ) from None
    if not isinstance(decoded, Mapping):
        raise DoubaoActorTransportError(
            "Doubao actor provider response must be an object",
            error_code="provider_invalid_shape",
        )
    return decoded


def _provider_input(request: Mapping[str, Any]) -> dict[str, Any]:
    """Keep qualification metadata out of the model-visible decision input."""

    arm = str(request["arm"])
    packet = request["packet"]
    signature = (
        quota_action_signature_document(packet)
        if arm == "full_packet"
        else turn_envelope_action_signature_document(packet)
    )
    selected_todo = dict(dict(signature.get("action") or {}).get("selected_todo") or {})
    return {
        "schema_version": MODEL_BEHAVIOR_PROVIDER_INPUT_SCHEMA_VERSION,
        "arm": arm,
        "canonical_selected_todo_id": selected_todo.get("todo_id"),
        "semantic_contract_required": request["semantic_contract_required"],
        "packet": packet,
    }


def _semantic_contract_instruction() -> str:
    return """
When semantic_contract_required=true, include all eight semantic_contract
fields and normalize them as follows. Never copy schema placeholders.
- concrete_user_question: first user.actions value, else null.
- required_reads: candidate packet.required_reads; for a full packet use
  interaction_contract.required_reads, falling back to packet.required_reads.
  Keep at most five object entries with a non-empty command and only command
  plus optional kind, reason, and source. Non-object entries are ignored.
- gate_or_stop: always include exactly decision, should_run, effective_action,
  state, interaction_mode, user_action_required, guards, and stop_condition.
  For a candidate use its top-level values, contract_capsule interaction mode,
  user.action_required, and boundary. For a full packet use its top-level
  values, interaction_contract, interaction_contract.user_channel, and
  goal_boundary. Use [] for absent guards and null for absent stop_condition.
- write_scope: candidate boundary.write_scope or full goal_boundary.write_scope;
  use [] when absent.
- spend_rule: candidate writeback. For a full packet construct exactly
  next_cli_actions, spend_allowed_now, spend_after_validation, and spend_policy
  from interaction_contract.cli_channel; use []/false/null when absent.
- scheduler_action: candidate scheduler. For a full packet project
  scheduler_hint using only non-null action, cadence_class, spend_policy, and a
  codex_app object containing only non-null apply, host_action,
  recommended_rrule, no_spend_for_cadence_change, stateful_backoff
  {state_key,current_rrule,apply_needed,state_status}, and ack_cli_args copied
  from ack_hint.cli_args. Use {} when absent.
- vision_continuation: candidate contract_capsule.vision_continuation_audit.
  For a full packet copy only non-null schema_version, required, decision,
  selected_todo_is_goal_completion, closeout_allowed_without_evidence,
  required_before_closeout, and recommended_action from
  vision_continuation_audit. Use {} when absent.
- actionable_warnings: candidate contract_capsule.actionable_warning_refs. For
  a full packet return, in packet order, only names of non-empty fields among
  state_projection_gap, boundary_projection_gap,
  state_action_projection_warning, next_action_projection_warning,
  stale_latest_run_warning, and decision_freshness_warning. Use [] when absent;
  guards are not warnings.
"""


def _decision_instruction(*, semantic_contract_required: bool) -> str:
    instruction = """You are a LoopX control-plane decision simulator.
Use only the qualification input supplied by the user. Do not call tools,
execute work, or request external writes. Return exactly one JSON object with
these fields and no others:
{
  "schema_version": "model_behavior_decision_v0",
  "decision": "execute|wait|ask_user|stop",
  "selected_todo_id": "todo_... or null",
  "user_action_required": true|false,
  "must_attempt_work": true|false,
  "delivery_allowed": true|false,
  "quiet_noop_allowed": true|false,
  "external_write_requested": false,
  "intended_action_kinds": ["read|inspect|edit|test|writeback|spend|notify|wait|stop"],
  "reason_codes": ["compact_public_safe_token"],
  "semantic_contract": {
    "concrete_user_question": null,
    "required_reads": [],
    "gate_or_stop": {},
    "write_scope": [],
    "spend_rule": {},
    "scheduler_action": {},
    "vision_continuation": {},
    "actionable_warnings": []
  }
}
Preserve user gates, selected work, execution obligations, write boundaries,
spend timing, scheduler duties, and stop conditions from the packet. Output
JSON only, without markdown or reasoning. Include semantic_contract whenever
the qualification input sets semantic_contract_required=true; derive it from
the packet and do not invent or summarize values. Copy
canonical_selected_todo_id exactly into selected_todo_id, including null; it
was derived locally from this arm's canonical action signature. Never infer a
todo id from summaries, diagnostics, handoffs, history, or other cold-path
references. Choose intended_action_kinds from the execution obligation, not
packet verbosity, and use the same ordered normalization for both arms.
Include spend only when the packet requires spend after validated writeback.
For intended actions, treat a full packet's interaction_contract.agent_channel
as equivalent to candidate action, and its interaction_contract.cli_channel as
equivalent to candidate writeback. When spend_after_validation=true, end both
arms with writeback then spend."""
    if semantic_contract_required:
        instruction += _semantic_contract_instruction()
    return instruction


def _provider_decision(response: Mapping[str, Any]) -> Mapping[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise RuntimeError("Doubao actor response must contain exactly one choice")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise RuntimeError("Doubao actor choice must be an object")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise RuntimeError("Doubao actor choice is missing its message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Doubao actor message content must be non-empty JSON")
    try:
        decision = json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError("Doubao actor message content is not valid JSON") from None
    if not isinstance(decision, Mapping):
        raise RuntimeError("Doubao actor decision must be an object")
    return decision


def _invoke_provider_decision(
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
    transport: DoubaoActorTransport,
    system_instruction: str,
    provider_input: Mapping[str, Any],
) -> Mapping[str, Any]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {
                "role": "user",
                "content": json.dumps(
                    dict(provider_input),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0,
        "max_tokens": _MAX_DECISION_TOKENS,
        "stream": False,
    }
    try:
        response = transport(
            endpoint=DOUBAO_CHAT_COMPLETIONS_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            body=json.dumps(
                body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            timeout_seconds=timeout_seconds,
        )
    except DoubaoActorTransportError:
        raise
    except Exception:
        raise DoubaoActorTransportError(
            "Doubao actor provider transport failed",
            error_code="provider_transport_failed",
        ) from None
    return _provider_decision(response)


def _onboarding_decision_instruction(phase: str) -> str:
    common = """You are a LoopX new-user onboarding decision simulator.
Use only the qualification packet supplied by the user. Do not call tools,
execute commands, or request external writes. Return exactly one JSON object
with these top-level fields and no others:
{
  "schema_version": "onboarding_model_behavior_decision_v0",
  "phase": "entry|postcondition",
  "next_action": "phase-specific route",
  "semantic_contract": {},
  "reason_codes": ["compact_public_safe_token"]
}
Copy the requested phase exactly. Output JSON only, without markdown or
reasoning. The semantic_contract must contain exactly the phase-specific fields
described below. Use null where instructed and never invent identifiers."""
    if phase == "entry":
        return common + """

For phase=entry, derive the contract from the start-goal packet:
- route: select_agent_identity when guided_transaction is blocked by an
  identity gate; select_goal when blocked by a goal-selection gate;
  connect_if_needed when ordered_steps contains that id; otherwise stop.
- goal_id: copy the top-level goal_id, including null.
- agent_id: copy top-level agent_id, falling back to
  host_loop_activation.agent_id or command_pack.host_loop_activation.agent_id;
  otherwise null.
- action_command_ids: in this exact order, include each key whose value is a
  non-empty string in top-level commands or command_pack.commands:
  goal_start_connect_if_needed, goal_start_refresh_state,
  goal_start_host_loop_activation, goal_start_quota_should_run.
- host_loop_activation_available: true when top-level host_loop_activation or
  command_pack.host_loop_activation is a non-empty object.
- host_loop_activation_after_todo_write: copy
  activation_required_after_todo_write from that activation object, else false.
- writes_now and spends_quota_now: copy the corresponding booleans from
  guided_transaction, defaulting to false.
Set next_action equal to route. The semantic_contract must contain exactly:
route, goal_id, agent_id, action_command_ids,
host_loop_activation_available, host_loop_activation_after_todo_write,
writes_now, spends_quota_now."""
    return common + """

For phase=postcondition, the packet is a locally derived observation:
- route: copy derived_route.
- state_projection_gap: copy the boolean field.
- executable_todo_present: true exactly when executable_todo_count is greater
  than zero.
- selected_action_kind: copy the field, including null.
- normal_delivery_allowed and user_action_required: copy both booleans.
Set next_action equal to route. The semantic_contract must contain exactly:
route, state_projection_gap, executable_todo_present, selected_action_kind,
normal_delivery_allowed, user_action_required."""


def _onboarding_provider_input(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "onboarding_model_behavior_provider_input_v0",
        "phase": request["phase"],
        "packet": request["packet"],
    }


class DoubaoModelBehaviorActor(ModelBehaviorActor):
    """Direct Ark actor for low-frequency, no-tool behavior qualification."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DOUBAO_2_1_PRO_MODEL,
        timeout_seconds: float = 90.0,
        transport: DoubaoActorTransport = _direct_ark_transport,
    ) -> None:
        if not api_key.strip():
            raise RuntimeError("Doubao actor requires a runtime-injected API key")
        if model not in _ALLOWED_MODELS:
            raise ValueError(
                "Doubao actor model must be an allowlisted Doubao 2.1 model"
            )
        if timeout_seconds <= 0 or timeout_seconds > 300:
            raise ValueError("Doubao actor timeout must be between 0 and 300 seconds")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_environment(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        transport: DoubaoActorTransport = _direct_ark_transport,
        timeout_seconds: float = 90.0,
    ) -> DoubaoModelBehaviorActor:
        values = os.environ if environ is None else environ
        api_key = values.get(ARK_API_KEY_ENV, "")
        if not api_key.strip():
            raise RuntimeError(
                "ARK_API_KEY is not injected; live Doubao qualification is unavailable"
            )
        model = values.get(DOUBAO_MODEL_ENV, DOUBAO_2_1_PRO_MODEL)
        return cls(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    def __call__(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        canonical_request = normalize_model_behavior_actor_request(request)
        decision = _invoke_provider_decision(
            api_key=self._api_key,
            model=self._model,
            timeout_seconds=self._timeout_seconds,
            transport=self._transport,
            system_instruction=_decision_instruction(
                semantic_contract_required=bool(
                    canonical_request["semantic_contract_required"]
                )
            ),
            provider_input=_provider_input(canonical_request),
        )
        return {
            "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
            "actor_ref": f"ark:{self._model}",
            "decision": dict(decision),
            "tool_calls": [],
        }


class DoubaoOnboardingModelBehaviorActor:
    """Direct Ark actor for low-frequency onboarding closed-loop qualification."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DOUBAO_2_1_PRO_MODEL,
        timeout_seconds: float = 90.0,
        transport: DoubaoActorTransport = _direct_ark_transport,
    ) -> None:
        if not api_key.strip():
            raise RuntimeError("Doubao actor requires a runtime-injected API key")
        if model not in _ALLOWED_MODELS:
            raise ValueError(
                "Doubao actor model must be an allowlisted Doubao 2.1 model"
            )
        if timeout_seconds <= 0 or timeout_seconds > 300:
            raise ValueError("Doubao actor timeout must be between 0 and 300 seconds")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_environment(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        transport: DoubaoActorTransport = _direct_ark_transport,
        timeout_seconds: float = 90.0,
    ) -> DoubaoOnboardingModelBehaviorActor:
        values = os.environ if environ is None else environ
        api_key = values.get(ARK_API_KEY_ENV, "")
        if not api_key.strip():
            raise RuntimeError(
                "ARK_API_KEY is not injected; live Doubao qualification is unavailable"
            )
        model = values.get(DOUBAO_MODEL_ENV, DOUBAO_2_1_PRO_MODEL)
        return cls(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    def __call__(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        canonical_request = normalize_onboarding_model_behavior_actor_request(request)
        phase = str(canonical_request["phase"])
        decision = _invoke_provider_decision(
            api_key=self._api_key,
            model=self._model,
            timeout_seconds=self._timeout_seconds,
            transport=self._transport,
            system_instruction=_onboarding_decision_instruction(phase),
            provider_input=_onboarding_provider_input(canonical_request),
        )
        return {
            "schema_version": ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
            "actor_ref": f"ark:{self._model}",
            "decision": dict(decision),
            "tool_calls": [],
        }
