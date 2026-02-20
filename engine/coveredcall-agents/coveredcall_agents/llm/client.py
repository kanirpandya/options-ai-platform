"""
coveredcall_agents.llm.client

Purpose:
    Compatibility-layer LLM client module for Covered Call Agents.

Design Goals:
    - Stable interface used by the rest of the codebase (LLMClient Protocol).
    - Extensible provider registry to avoid scattered provider conditionals.
    - Centralized, validated env configuration (fail-fast; no hidden defaults).
    - No hard-coded provider/model identifiers in code paths.

Providers:
    - Ollama (local)
    - Bedrock (AWS) via separate module that self-registers

Author:
    Kanir Pandya

Created:
    2026-02-17
"""

from __future__ import annotations

import importlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Protocol, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from coveredcall_agents.llm.providers import LLMProvider
from coveredcall_agents.utils.logging import get_logger

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)

_NON_ALNUM = re.compile(r"[^a-z0-9]+", re.IGNORECASE)

# ----------------------------
# Environment variable constants
# ----------------------------
ENV_LLM_PROVIDER = "LLM_PROVIDER"
ENV_LLM_MODEL_IDENTIFIER = "LLM_MODEL_IDENTIFIER"

ENV_LLM_TIMEOUT_SECONDS = "LLM_TIMEOUT_SECONDS"
ENV_LLM_TRACE_ENABLED = "LLM_TRACE_ENABLED"
ENV_LLM_TEMPERATURE = "LLM_TEMPERATURE"
ENV_LLM_TOP_P = "LLM_TOP_P"
ENV_LLM_MAX_TOKENS = "LLM_MAX_TOKENS"

ENV_OLLAMA_BASE_URL = "OLLAMA_BASE_URL"

ENV_AWS_REGION = "AWS_REGION"
ENV_AWS_DEFAULT_REGION = "AWS_DEFAULT_REGION"

# ----------------------------
# Non-secret defaults (centralized)
# ----------------------------
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TOP_P = 0.9
DEFAULT_MAX_TOKENS = 700

TRACE_ENABLED_VALUE = "1"

# ----------------------------
# Standardized debug marker (provider-agnostic)
# ----------------------------
LLM_DEBUG_MARKER = "[LLMClient]"


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


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """
    Runtime configuration for LLM selection and invocation.

    Notes:
        - provider must be explicitly configured via env.
        - model_identifier must be explicitly configured for non-stub providers.
    """

    provider: LLMProvider
    model_identifier: str | None

    timeout_seconds: float
    trace_enabled: bool

    temperature: float
    top_p: float
    max_tokens: int

    ollama_base_url: str | None = None
    aws_region: str | None = None

    @staticmethod
    def from_env() -> "LLMRuntimeConfig":
        provider_raw = (os.getenv(ENV_LLM_PROVIDER) or "").strip().lower()
        if not provider_raw:
            raise ValueError(f"{ENV_LLM_PROVIDER} must be set explicitly")

        try:
            provider = LLMProvider(provider_raw)
        except ValueError as e:
            raise ValueError(f"Unsupported {ENV_LLM_PROVIDER} value: {provider_raw}") from e

        model_identifier = (os.getenv(ENV_LLM_MODEL_IDENTIFIER) or "").strip() or None

        if provider not in (LLMProvider.STUB, LLMProvider.MOCK) and not model_identifier:
            raise ValueError(
                f"{ENV_LLM_MODEL_IDENTIFIER} must be set explicitly for provider={provider.value}"
            )

        timeout_seconds = float(os.getenv(ENV_LLM_TIMEOUT_SECONDS, str(DEFAULT_TIMEOUT_SECONDS)))
        trace_enabled = (os.getenv(ENV_LLM_TRACE_ENABLED) or "").strip() == TRACE_ENABLED_VALUE

        temperature = float(os.getenv(ENV_LLM_TEMPERATURE, str(DEFAULT_TEMPERATURE)))
        top_p = float(os.getenv(ENV_LLM_TOP_P, str(DEFAULT_TOP_P)))
        max_tokens = int(os.getenv(ENV_LLM_MAX_TOKENS, str(DEFAULT_MAX_TOKENS)))

        ollama_base_url = (os.getenv(ENV_OLLAMA_BASE_URL) or "").strip() or None
        aws_region = (
            (os.getenv(ENV_AWS_REGION) or "").strip()
            or (os.getenv(ENV_AWS_DEFAULT_REGION) or "").strip()
            or None
        )

        return LLMRuntimeConfig(
            provider=provider,
            model_identifier=model_identifier,
            timeout_seconds=timeout_seconds,
            trace_enabled=trace_enabled,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            ollama_base_url=ollama_base_url,
            aws_region=aws_region,
        )


ProviderBuilder = Callable[[LLMRuntimeConfig], LLMClient]
_PROVIDER_REGISTRY: Dict[LLMProvider, ProviderBuilder] = {}

_PROVIDER_MODULES: Dict[LLMProvider, str] = {
    # Providers that self-register on import:
    LLMProvider.BEDROCK: "coveredcall_agents.llm.bedrock_client",
}


def register_llm_provider(provider: LLMProvider, builder: ProviderBuilder) -> None:
    """
    Register a provider builder. Providers should register themselves on import.
    """
    _PROVIDER_REGISTRY[provider] = builder


def _ensure_provider_registered(provider: LLMProvider) -> None:
    """
    Ensure provider module has been imported so it can register itself.
    """
    if provider in _PROVIDER_REGISTRY:
        return

    module_path = _PROVIDER_MODULES.get(provider)
    if not module_path:
        return

    importlib.import_module(module_path)


@dataclass
class OllamaClient:
    """
    Minimal Ollama client that asks for JSON output and validates with Pydantic.
    Requires local Ollama server running.
    """

    model_name: str
    base_url: str
    timeout_s: float
    trace: bool = False

    def _post_chat(self, payload_dict: dict) -> str:
        with httpx.Client(timeout=self.timeout_s) as http_client:
            response = http_client.post(f"{self.base_url}/api/chat", json=payload_dict)
            response.raise_for_status()
            payload = response.json()
        return ((payload.get("message") or {}).get("content") or "").strip()

    def _post_generate(self, payload_dict: dict) -> str:
        with httpx.Client(timeout=self.timeout_s) as http_client:
            response = http_client.post(f"{self.base_url}/api/generate", json=payload_dict)
            response.raise_for_status()
            payload = response.json()
        return (payload.get("response") or "").strip()

    def generate_json(self, *, system: str, user: str, schema: Dict[str, Any], model: Type[T]) -> T:
        system_instructions = (
            system
            + "\n\nIMPORTANT: Return ONLY a single valid JSON object. No markdown. No explanations."
        )
        user_instructions = user + "\n\nReturn ONLY JSON."

        payload = {
            "model": self.model_name,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_instructions},
            ],
            "options": {
                "temperature": 0.0,
                "num_predict": DEFAULT_MAX_TOKENS,
            },
        }

        if self.trace:
            logger.debug(
                "%s provider=%s mode=json model=%s base_url=%s timeout_s=%s",
                LLM_DEBUG_MARKER,
                LLMProvider.OLLAMA.value,
                self.model_name,
                self.base_url,
                self.timeout_s,
            )

        def _regenerate_from_scratch() -> dict:
            regeneration_payload = dict(payload)
            regeneration_payload["messages"] = [
                {"role": "system", "content": system_instructions},
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
                {"role": "user", "content": user_instructions},
            ]

            raw_regen = self._post_chat(regeneration_payload)
            if not raw_regen:
                raise RuntimeError("Ollama returned empty response on regenerate attempt")

            extracted, is_complete = _extract_first_json(raw_regen)
            if not is_complete:
                raise RuntimeError(f"LLM JSON truncated twice. Raw (truncated): {raw_regen[:800]}")

            parsed = json.loads(extracted)
            if isinstance(parsed, list) and parsed:
                parsed = parsed[0]
            if not isinstance(parsed, dict):
                raise RuntimeError(f"Regenerate returned non-object JSON: {type(parsed)}")

            return parsed

        raw = self._post_chat(payload)
        if not raw:
            raise RuntimeError("Ollama returned empty response")

        extracted, is_complete = _extract_first_json(raw)

        if not is_complete:
            parsed_obj: Any = _regenerate_from_scratch()
        else:
            try:
                parsed_obj = json.loads(extracted)
            except json.JSONDecodeError:
                parsed_obj = _regenerate_from_scratch()

        if isinstance(parsed_obj, list) and parsed_obj:
            parsed_obj = parsed_obj[0]

        try:
            return model.model_validate(parsed_obj)
        except ValidationError as validation_error:
            repair_payload = dict(payload)
            repair_payload["messages"] = [
                {"role": "system", "content": system_instructions},
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
                {"role": "user", "content": user_instructions},
            ]

            raw_repair = self._post_chat(repair_payload)
            if not raw_repair:
                raise RuntimeError("Ollama returned empty response on schema-repair attempt")

            extracted_repair, is_complete_repair = _extract_first_json(raw_repair)
            if not is_complete_repair:
                msg = f"LLM JSON truncated on schema-repair attempt. Raw (truncated): {raw_repair[:800]}"
                if self.trace:
                    logger.debug(msg)
                raise RuntimeError(msg)

            repaired_obj = json.loads(extracted_repair)
            if isinstance(repaired_obj, list) and repaired_obj:
                repaired_obj = repaired_obj[0]

            try:
                return model.model_validate(repaired_obj)
            except ValidationError as validation_error_retry:
                raise RuntimeError(
                    f"LLM JSON failed schema validation after retry: {validation_error_retry}. "
                    f"Raw (truncated): {json.dumps(repaired_obj)[:800]}"
                ) from validation_error

    def generate_text(self, *, system: str, user: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": user,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": DEFAULT_MAX_TOKENS,
            },
        }

        if self.trace:
            logger.debug(
                "%s provider=%s mode=text model=%s base_url=%s timeout_s=%s",
                LLM_DEBUG_MARKER,
                LLMProvider.OLLAMA.value,
                self.model_name,
                self.base_url,
                self.timeout_s,
            )

        return self._post_generate(payload)


@dataclass
class LocalStubLLM:
    """
    A safe fallback that never calls a model.
    """

    def generate_json(self, *, system: str, user: str, schema: Dict[str, Any], model: Type[T]) -> T:
        raise RuntimeError("LocalStubLLM: no LLM configured")

    def generate_text(self, *, system: str, user: str) -> str:
        raise RuntimeError("LocalStubLLM: no LLM configured")


def _build_ollama_client(cfg: LLMRuntimeConfig) -> OllamaClient:
    if not cfg.ollama_base_url:
        raise ValueError(f"{ENV_OLLAMA_BASE_URL} must be set for provider={LLMProvider.OLLAMA.value}")

    if not cfg.model_identifier:
        raise ValueError(f"{ENV_LLM_MODEL_IDENTIFIER} must be set for provider={LLMProvider.OLLAMA.value}")

    return OllamaClient(
        model_name=cfg.model_identifier,
        base_url=cfg.ollama_base_url,
        timeout_s=cfg.timeout_seconds,
        trace=cfg.trace_enabled,
    )


register_llm_provider(LLMProvider.OLLAMA, _build_ollama_client)


def build_llm_client_from_config(runtime_config: LLMRuntimeConfig) -> LLMClient:
    """
    Construct an LLM client using a provided runtime config and provider registry.
    This is used by CLI flag-based config (dev flexibility) and tests.
    """
    if runtime_config.provider in (LLMProvider.STUB, LLMProvider.MOCK):
        return LocalStubLLM()

    _ensure_provider_registered(runtime_config.provider)

    builder = _PROVIDER_REGISTRY.get(runtime_config.provider)
    if not builder:
        raise ValueError(f"No provider registered for provider={runtime_config.provider.value}")

    return builder(runtime_config)


def build_llm_client_from_env() -> LLMClient:
    return build_llm_client_from_config(LLMRuntimeConfig.from_env())


# Backward-compatible alias
get_llm_client_from_env = build_llm_client_from_env
