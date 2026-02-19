"""
backend.shared.models.enums

Purpose:
    Enumerations shared across backend components for the Options AI Platform.
    These enums are part of the stable contract used by:
      - Submitter Lambda (API -> SQS)
      - Fargate worker (SQS -> engine run -> persistence)
      - DynamoDB job records (status + metadata)
      - Future frontend (job polling + history views)

Used By:
    - backend.shared.models.job_payload
    - backend.shared.models.job_record
    - backend.shared.models.result_summary
    - backend submitter/worker components

Design Notes:
    - Keep enum string values stable to preserve backward compatibility.
    - Do not embed infrastructure concerns (names/ARNs/URLs) in enums.
    - FundamentalsMode values should align with engine config/CLI expectations.

Author:
    Kanir Pandya

Created:
    2026-02-13
"""

from __future__ import annotations

from enum import Enum


class FundamentalsMode(str, Enum):
    """
    Supported fundamentals execution modes.

    IMPORTANT:
        String values must align with engine config usage so the worker can pass
        mode cleanly via config overrides without translation layers.
    """

    DET = "det"
    LLM = "llm"
    AGENTIC = "agentic"
    LLM_AGENTIC = "llm_agentic"

    # Backward-compatible alias (optional):
    DETERMINISTIC = "det"


class JobStatus(str, Enum):
    """
    Backend job lifecycle states.

    Notes:
        - QUEUED: Accepted and enqueued; worker has not started.
        - RUNNING: Worker has started processing the job.
        - DONE: Completed successfully; result artifacts available in S3.
        - FAILED: Terminal failure; error details available in DynamoDB/S3.
    """

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
