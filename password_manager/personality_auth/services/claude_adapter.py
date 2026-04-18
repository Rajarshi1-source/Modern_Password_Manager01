"""Thin Claude adapter enforcing a Pydantic-style output contract.

The real ``ai_assistant.ClaudeService`` speaks free-form natural language — fine
for a chat UI, but risky for an authentication flow that must reason
over structured output. This adapter:

1. Asks Claude for a JSON response that matches a caller-supplied schema.
2. Extracts the JSON payload defensively (Claude sometimes wraps it in
   markdown fences).
3. Validates against a lightweight schema validator — uses ``pydantic`` if
   available, otherwise a minimal in-process validator on a dict shape.
4. Retries once on parse failure with a stricter reminder prompt.
5. Raises :class:`LLMSchemaError` if the output cannot be forced into the
   expected shape after retries.

The adapter is intentionally decoupled from the rest of the app so tests
can swap the underlying ``ClaudeService`` with a stub that returns fixed
JSON strings.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency.
    from pydantic import BaseModel, ValidationError
    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover
    BaseModel = object  # type: ignore
    ValidationError = Exception  # type: ignore
    _HAS_PYDANTIC = False


class LLMSchemaError(Exception):
    """Raised when the LLM response cannot be coerced into the expected schema."""


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)
_FIRST_JSON_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


@dataclass
class AdapterCall:
    prompt: str
    schema: Any
    system: Optional[str] = None
    max_attempts: int = 2


class ClaudeJSONAdapter:
    """Wraps a ClaudeService-like object and returns structured JSON.

    The wrapped service must expose a ``send_message(user, history, message,
    vault_context=None)`` method returning a dict with a ``content`` key
    (same contract as :class:`ai_assistant.services.claude_service.ClaudeService`).
    A ``system`` parameter is optional; when provided, the adapter folds it
    into the prompt as a leading ``SYSTEM:`` block so existing service code
    doesn't need new plumbing.
    """

    SYSTEM_HINT = (
        "You MUST respond with a single JSON object matching the schema "
        "provided. Do not wrap the JSON in prose or markdown. If you are "
        "unsure of any field, still return valid JSON with null or empty "
        "values."
    )

    def __init__(self, inner_service: Any, *, user=None) -> None:
        self._svc = inner_service
        self._user = user

    # ------------------------------------------------------------------
    def call(self, call: AdapterCall) -> Any:
        """Execute the LLM call and return a parsed, validated payload."""
        system_block = (call.system or '') + '\n' + self.SYSTEM_HINT
        schema_repr = self._render_schema(call.schema)
        attempt = 0
        last_error: Optional[str] = None
        while attempt < call.max_attempts:
            prompt = self._build_prompt(
                call.prompt, system_block, schema_repr, previous_error=last_error
            )
            raw = self._send(prompt)
            try:
                data = self._extract_json(raw)
            except LLMSchemaError as exc:
                last_error = str(exc)
                attempt += 1
                continue

            try:
                return self._validate(data, call.schema)
            except LLMSchemaError as exc:
                last_error = str(exc)
                attempt += 1

        raise LLMSchemaError(
            f"LLM output failed schema validation after {call.max_attempts} attempts: {last_error}"
        )

    # ------------------------------------------------------------------
    def _send(self, prompt: str) -> str:
        try:
            response = self._svc.send_message(
                self._user,
                conversation_history=[],
                user_message=prompt,
                vault_context=None,
            )
        except TypeError:
            # Allow simple callables in tests.
            response = self._svc(prompt)  # type: ignore

        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            return str(response.get('content', ''))
        return str(response)

    @staticmethod
    def _build_prompt(
        user_prompt: str,
        system_block: str,
        schema_repr: str,
        *,
        previous_error: Optional[str],
    ) -> str:
        parts = [
            f"SYSTEM:\n{system_block.strip()}\n",
            f"REQUIRED_SCHEMA:\n{schema_repr}\n",
        ]
        if previous_error:
            parts.append(
                f"Your previous response was invalid: {previous_error}. "
                "Respond with only valid JSON this time."
            )
        parts.append(f"TASK:\n{user_prompt}\n")
        return "\n".join(parts)

    @staticmethod
    def _render_schema(schema: Any) -> str:
        if _HAS_PYDANTIC and isinstance(schema, type) and issubclass(schema, BaseModel):  # type: ignore[arg-type]
            try:
                return json.dumps(schema.model_json_schema())  # type: ignore[attr-defined]
            except Exception:
                try:
                    return json.dumps(schema.schema())  # type: ignore[attr-defined]
                except Exception:
                    return schema.__name__
        if callable(schema) and not isinstance(schema, type):
            return "<custom validator>"
        if isinstance(schema, dict):
            return json.dumps(schema, default=str)
        return str(schema)

    @staticmethod
    def _extract_json(raw: str) -> Any:
        if not raw:
            raise LLMSchemaError("empty response")
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        m = _JSON_BLOCK_RE.search(raw)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = _FIRST_JSON_RE.search(raw)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError as exc:
                raise LLMSchemaError(f"malformed JSON in fallback extractor: {exc}")
        raise LLMSchemaError("no JSON object detected in response")

    def _validate(self, data: Any, schema: Any) -> Any:
        # 1. Pydantic model ------------------------------------------------
        if _HAS_PYDANTIC and isinstance(schema, type) and issubclass(schema, BaseModel):  # type: ignore[arg-type]
            try:
                return schema.model_validate(data)  # type: ignore[attr-defined]
            except AttributeError:
                try:
                    return schema.parse_obj(data)  # type: ignore[attr-defined]
                except ValidationError as exc:  # type: ignore
                    raise LLMSchemaError(str(exc))
            except ValidationError as exc:  # type: ignore
                raise LLMSchemaError(str(exc))

        # 2. Callable validator -------------------------------------------
        if callable(schema) and not isinstance(schema, type):
            try:
                result = schema(data)
            except Exception as exc:
                raise LLMSchemaError(str(exc))
            return result if result is not None else data

        # 3. Dict schema with "required" keys -----------------------------
        if isinstance(schema, dict) and 'required' in schema:
            missing = [k for k in schema['required'] if k not in data]
            if missing:
                raise LLMSchemaError(f"missing required keys: {missing}")
            return data

        return data
