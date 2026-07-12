from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .model_behavior_qualification import (
    MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
    ModelBehaviorActor,
    normalize_model_behavior_actor_request,
)


DOUBAO_2_1_PRO_MODEL = "doubao-seed-2-1-pro-260628"
DOUBAO_2_1_TURBO_MODEL = "doubao-seed-2-1-turbo-260628"
DOUBAO_CHAT_COMPLETIONS_ENDPOINT = (
    "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
)
ARK_API_KEY_ENV = "ARK_API_KEY"
DOUBAO_MODEL_ENV = "LOOPX_MODEL_BEHAVIOR_MODEL"

_ALLOWED_MODELS = {DOUBAO_2_1_PRO_MODEL, DOUBAO_2_1_TURBO_MODEL}
_MAX_PROVIDER_RESPONSE_BYTES = 1_048_576


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
    pass


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
            "Doubao actor endpoint is not the canonical Ark endpoint"
        )
    request = Request(endpoint, data=body, headers=dict(headers), method="POST")
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise DoubaoActorTransportError(
            f"Doubao actor request failed with HTTP status {exc.code}"
        ) from None
    except (URLError, TimeoutError):
        raise DoubaoActorTransportError(
            "Doubao actor provider transport failed"
        ) from None
    if len(payload) > _MAX_PROVIDER_RESPONSE_BYTES:
        raise DoubaoActorTransportError("Doubao actor response exceeded the size limit")
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DoubaoActorTransportError("Doubao actor returned invalid JSON") from None
    if not isinstance(decoded, Mapping):
        raise DoubaoActorTransportError(
            "Doubao actor provider response must be an object"
        )
    return decoded


def _decision_instruction() -> str:
    return """You are a LoopX control-plane decision simulator.
Use only the qualification request supplied by the user. Do not call tools,
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
    "concrete_user_question": "exact first user action or null",
    "required_reads": ["copy exact normalized objects from the packet"],
    "gate_or_stop": {"copy": "exact normalized object from the packet"},
    "write_scope": ["copy exact normalized values from the packet"],
    "spend_rule": {"copy": "exact normalized object from the packet"},
    "scheduler_action": {"copy": "exact normalized object from the packet"},
    "vision_continuation": {"copy": "exact normalized object from the packet"},
    "actionable_warnings": ["copy exact normalized values from the packet"]
  }
}
Preserve user gates, selected work, execution obligations, write boundaries,
spend timing, scheduler duties, and stop conditions from the packet. Output
JSON only, without markdown or reasoning. Include semantic_contract whenever
the qualification request sets semantic_contract_required=true; derive it from
the packet and do not invent or summarize values."""


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
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _decision_instruction()},
                {
                    "role": "user",
                    "content": json.dumps(
                        canonical_request,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 1200,
            "stream": False,
        }
        try:
            response = self._transport(
                endpoint=DOUBAO_CHAT_COMPLETIONS_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                body=json.dumps(
                    body,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
                timeout_seconds=self._timeout_seconds,
            )
        except DoubaoActorTransportError:
            raise
        except Exception:
            raise DoubaoActorTransportError(
                "Doubao actor provider transport failed"
            ) from None
        return {
            "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
            "actor_ref": f"ark:{self._model}",
            "decision": dict(_provider_decision(response)),
            "tool_calls": [],
        }
