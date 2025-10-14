"""Message parsing and envelope handling."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import orjson as json
from pydantic import ValidationError

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1 import LLMRequest  # type: ignore[import]

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles message parsing and envelope extraction."""

    @staticmethod
    def decode_llm_request(payload: bytes) -> Tuple[Optional[LLMRequest], Optional[str]]:
        """Parse LLM request from payload, with or without envelope.

        Returns:
            (request, correlation_id) or (None, None) on error
        """
        envelope: Optional[Envelope] = None

        # Try parsing as envelope first
        try:
            envelope = Envelope.model_validate_json(payload)
            data = envelope.data
        except ValidationError:
            # Fallback to raw JSON
            try:
                data = json.loads(payload)
            except Exception:
                logger.warning("Invalid llm/request payload (unable to parse JSON)")
                return None, None

        # Validate as LLMRequest
        try:
            request = LLMRequest.model_validate(data)
            correlation_id = envelope.id if envelope else None
            return request, correlation_id
        except ValidationError as exc:
            logger.warning("Invalid llm/request payload: %s", exc)
            return None, None

    @staticmethod
    def decode_json_payload(payload: bytes) -> Optional[dict]:
        """Parse JSON payload with optional envelope."""
        try:
            envelope = Envelope.model_validate_json(payload)
            return envelope.data if isinstance(envelope.data, dict) else {}
        except ValidationError:
            try:
                return json.loads(payload)
            except Exception as e:
                logger.warning("Failed to parse JSON payload: %s", e)
                return None
