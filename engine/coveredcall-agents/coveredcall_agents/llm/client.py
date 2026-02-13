from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, Protocol, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from coveredcall_agents.utils.logging import get_logger

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)

_NON_ALNUM = re.compile(r"[^a-z0-9]+", re.IGNORECASE)


def _extract_first_json(text: str) -> tuple[str, bool]:
    """
    Extract the first balanced JSON object OR array from text.
    Returns (json_str, complete).
    """
    s = (text or "").strip()
    if not s:
        return "", False

    obj_i = s.find("{")
    arr_i = s.find("[")
    if obj_i == -1 and arr_i == -1:
        return s, False

    start = min(i for i in (obj_i, arr_i) if i != -1)
    opener = s[start]
    closer = "}" if opener == "{" else "]"

    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return s[start : i + 1].strip(), True

    return s[start:].strip(), False


class LLMClient(Protocol):
    def generate_json(
        self, *, system: str, user: str, schema: Dict[str, Any], model: Type[T]
    ) -> T: ...

    def generate_text(self, *, system: str, user: str) -> str: ...


@dataclass
class OllamaClient:
    """
    Minimal Ollama client that asks for JSON output and validates with Pydantic.
    Requires local Ollama server running (default: http://localhost:11434).
    """

    model_name: str
    base_url: str = "http://localhost:11434"
    timeout_s: float = 30.0
    trace: bool = False

    def _post_chat(self, payload_dict: dict) -> str:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(f"{self.base_url}/api/chat", json=payload_dict)
            r.raise_for_status()
            data = r.json()
        return ((data.get("message") or {}).get("content") or "").strip()

    def _post_generate(self, payload_dict: dict) -> str:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(f"{self.base_url}/api/generate", json=payload_dict)
            r.raise_for_status()
            data = r.json()
        return (data.get("response") or "").strip()

    def generate_json(self, *, system: str, user: str, schema: Dict[str, Any], model: Type[T]) -> T:
        system2 = (
            system
            + "\n\nIMPORTANT: Return ONLY a single valid JSON object. No markdown. No explanations."
        )
        user2 = user + "\n\nReturn ONLY JSON."

        payload = {
            "model": self.model_name,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system2},
                {"role": "user", "content": user2},
            ],
            "options": {
                "temperature": 0.0,
                "num_predict": 700,
            },
        }

        if self.trace:
            logger.debug(
                "OllamaClient(json) model=%s base_url=%s timeout_s=%s",
                self.model_name,
                self.base_url,
                self.timeout_s,
            )

        def _regen_from_scratch_short() -> dict:
            regen_payload = dict(payload)
            regen_payload["messages"] = [
                {"role": "system", "content": system2},
                {
                    "role": "user",
                    "content": (
                        "Your previous response was invalid or truncated.\n"
                        "Regenerate from scratch.\n"
                        "Return ONLY valid JSON.\n"
                        "Rules:\n"
                        "- Use ONLY the allowed keys\n"
                        "- bullets must be 0-4 short strings (<= 80 chars each)\n"
                        "- risks must be 0-4 short strings (<= 80 chars each)\n"
                        "- Finish every string; no trailing clauses\n"
                    ),
                },
                {"role": "user", "content": user2},
            ]

            raw2 = self._post_chat(regen_payload)
            if not raw2:
                raise RuntimeError("Ollama returned empty response on regenerate attempt")

            text2, complete2 = _extract_first_json(raw2)
            if not complete2:
                raise RuntimeError(f"LLM JSON truncated twice. Raw (truncated): {raw2[:800]}")

            obj2 = json.loads(text2)
            if isinstance(obj2, list) and obj2:
                obj2 = obj2[0]
            if not isinstance(obj2, dict):
                raise RuntimeError(f"Regenerate returned non-object JSON: {type(obj2)}")

            return obj2

        raw = self._post_chat(payload)
        if not raw:
            raise RuntimeError("Ollama returned empty response")

        text, complete = _extract_first_json(raw)

        if not complete:
            obj = _regen_from_scratch_short()
        else:
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                obj = _regen_from_scratch_short()

        if isinstance(obj, list) and obj:
            obj = obj[0]

        try:
            return model.model_validate(obj)
        except ValidationError as e:
            repair_payload = dict(payload)
            repair_payload["messages"] = [
                {"role": "system", "content": system2},
                {
                    "role": "user",
                    "content": (
                        "Your previous JSON did NOT match the required schema.\n"
                        "Regenerate from scratch.\n"
                        "Return ONLY valid JSON.\n"
                        "Hard rules:\n"
                        "- Use ONLY the keys required by the schema.\n"
                        "- Include ALL required keys.\n"
                        "- Enums must match exactly.\n"
                        "- Respect list limits exactly.\n"
                    ),
                },
                {"role": "user", "content": user2},
            ]

            raw3 = self._post_chat(repair_payload)
            if not raw3:
                raise RuntimeError("Ollama returned empty response on schema-repair attempt")

            text3, complete3 = _extract_first_json(raw3)
            if not complete3:
                msg = f"LLM JSON truncated on schema-repair attempt. Raw (truncated): {raw3[:800]}"
                if self.trace:
                    logger.debug(msg)
                raise RuntimeError(msg)

            obj3 = json.loads(text3)
            if isinstance(obj3, list) and obj3:
                obj3 = obj3[0]

            try:
                return model.model_validate(obj3)
            except ValidationError as e2:
                raise RuntimeError(
                    f"LLM JSON failed schema validation after retry: {e2}. "
                    f"Raw (truncated): {json.dumps(obj3)[:800]}"
                ) from e

    def generate_text(self, *, system: str, user: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": user,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 700,
            },
        }

        if self.trace:
            logger.debug(
                "OllamaClient(text) model=%s base_url=%s timeout_s=%s",
                self.model_name,
                self.base_url,
                self.timeout_s,
            )

        return self._post_generate(payload)


@dataclass
class LocalStubLLM:
    """
    A safe fallback that never calls a model.
    Useful if you want to flip 'mode=llm' before setting up Ollama.
    """

    def generate_json(self, *, system: str, user: str, schema: Dict[str, Any], model: Type[T]) -> T:
        raise RuntimeError("LocalStubLLM: no LLM configured")

    def generate_text(self, *, system: str, user: str) -> str:
        raise RuntimeError("LocalStubLLM: no LLM configured")
