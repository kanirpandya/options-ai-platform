"""
coveredcall_agents.llm.bedrock_client

Purpose:
    Amazon Bedrock LLM provider implementation for Covered Call Agents.

Design Notes:
    - Provider registers itself into coveredcall_agents.llm.client registry on import.
    - Uses boto3 bedrock-runtime InvokeModel.
    - No hard-coded model IDs; model id comes from env via LLMRuntimeConfig.model_identifier.

Author:
    Kanir Pandya

Created:
    2026-02-17
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Type, TypeVar

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ValidationError

from coveredcall_agents.utils.logging import get_logger
from coveredcall_agents.llm.client import (
    ENV_AWS_DEFAULT_REGION,
    ENV_AWS_REGION,
    LLMProvider,
    LLMRuntimeConfig,
    register_llm_provider,
    _extract_first_json,
)

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)


def _format_llama_instruct_prompt(*, system: str, user: str) -> str:
    """
    Meta Llama 3.x instruct prompt format suitable for Bedrock Meta Llama models.
    """
    system_text = (system or "").strip()
    user_text = (user or "").strip()

    begin = "<|begin_of_text|>"
    system_header = "<|start_header_id|>system<|end_header_id|>\n"
    user_header = "<|start_header_id|>user<|end_header_id|>\n"
    assistant_header = "<|start_header_id|>assistant<|end_header_id|>\n"
    eot = "<|eot_id|>"

    if system_text:
        return (
            f"{begin}"
            f"{system_header}{system_text}{eot}"
            f"{user_header}{user_text}{eot}"
            f"{assistant_header}"
        )

    return f"{begin}{user_header}{user_text}{eot}{assistant_header}"


@dataclass
class BedrockClient:
    """
    Bedrock LLM client (Meta Llama family via InvokeModel).

    Requirements:
      - IAM permission on task role: bedrock:InvokeModel
      - Bedrock model access enabled in the AWS account/region for model_id
    """

    model_id: str
    region_name: str
    timeout_s: float
    trace: bool

    temperature: float
    top_p: float
    max_gen_len: int

    def __post_init__(self) -> None:
        self._runtime = boto3.client("bedrock-runtime", region_name=self.region_name)

    def generate_text(self, *, system: str, user: str) -> str:
        prompt = _format_llama_instruct_prompt(system=system, user=user)

        request_body = {
            "prompt": prompt,
            "temperature": float(self.temperature),
            "top_p": float(self.top_p),
            "max_gen_len": int(self.max_gen_len),
        }

        if self.trace:
            logger.debug(
                "[LLMClient] provider=%s model_id=%s region=%s timeout_s=%s",
                LLMProvider.BEDROCK.value,
                self.model_id,
                self.region_name,
                self.timeout_s,
            )

        try:
            response = self._runtime.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body),
            )
            raw_payload = response["body"].read().decode("utf-8")
            parsed = json.loads(raw_payload)
            return (parsed.get("generation") or "").strip()
        except (ClientError, BotoCoreError, json.JSONDecodeError) as e:
            logger.exception("Bedrock invoke_model failed: %s", e)
            raise

    def generate_json(self, *, system: str, user: str, schema: Dict[str, Any], model: Type[T]) -> T:
        system_instructions = (
            system + "\n\nIMPORTANT: Return ONLY a single valid JSON object. No markdown. No explanations."
        )
        user_instructions = user + "\n\nReturn ONLY JSON."

        raw = self.generate_text(system=system_instructions, user=user_instructions)
        if not raw:
            raise RuntimeError("Bedrock returned empty response")

        extracted, is_complete = _extract_first_json(raw)
        if not is_complete:
            raise RuntimeError(f"Bedrock JSON truncated. Raw (truncated): {raw[:800]}")

        try:
            parsed_obj: Any = json.loads(extracted)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Bedrock returned invalid JSON. Raw (truncated): {raw[:800]}") from e

        if isinstance(parsed_obj, list) and parsed_obj:
            parsed_obj = parsed_obj[0]

        try:
            return model.model_validate(parsed_obj)
        except ValidationError as validation_error:
            repair_user = (
                "Your previous JSON did NOT match the required schema.\n"
                "Regenerate from scratch.\n"
                "Return ONLY valid JSON.\n"
                "Hard rules:\n"
                "- Use ONLY the keys required by the schema.\n"
                "- Include ALL required keys.\n"
                "- Enums must match exactly.\n"
                "- Respect list limits exactly.\n\n"
                f"{user_instructions}"
            )

            raw_retry = self.generate_text(system=system_instructions, user=repair_user)
            if not raw_retry:
                raise RuntimeError("Bedrock returned empty response on schema-repair attempt")

            extracted_retry, is_complete_retry = _extract_first_json(raw_retry)
            if not is_complete_retry:
                raise RuntimeError(
                    f"Bedrock JSON truncated on schema-repair attempt. Raw (truncated): {raw_retry[:800]}"
                )

            parsed_retry: Any = json.loads(extracted_retry)
            if isinstance(parsed_retry, list) and parsed_retry:
                parsed_retry = parsed_retry[0]

            try:
                return model.model_validate(parsed_retry)
            except ValidationError as validation_error_retry:
                raise RuntimeError(
                    f"Bedrock JSON failed schema validation after retry: {validation_error_retry}. "
                    f"Raw (truncated): {json.dumps(parsed_retry)[:800]}"
                ) from validation_error


def _build_bedrock_client(runtime_config: LLMRuntimeConfig) -> BedrockClient:
    if not runtime_config.aws_region:
        raise ValueError(
            f"AWS region must be set via {ENV_AWS_REGION} or {ENV_AWS_DEFAULT_REGION} "
            f"for provider={LLMProvider.BEDROCK.value}"
        )

    return BedrockClient(
        model_id=runtime_config.model_identifier,
        region_name=runtime_config.aws_region,
        timeout_s=runtime_config.timeout_seconds,
        trace=runtime_config.trace_enabled,
        temperature=runtime_config.temperature,
        top_p=runtime_config.top_p,
        max_gen_len=runtime_config.max_tokens,
    )


register_llm_provider(LLMProvider.BEDROCK, _build_bedrock_client)
