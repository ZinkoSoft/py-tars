from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tars.domain.ports import Publisher

from .logging import Logger
from .publisher import publish_event


@dataclass(slots=True)
class Ctx:
    """Execution context passed into handlers."""

    pub: Publisher
    policy: Any
    logger: Logger
    metrics: Any | None = None

    async def publish(
        self,
        event_type: str,
        data: Any,
        *,
        correlate: str | None = None,
        qos: int = 1,
        retain: bool = False,
    ) -> str:
        """Publish an event via the shared helper.

        Returns the message id assigned to the envelope for downstream correlation.
        """

        return await publish_event(
            self.pub,
            self.logger,
            event_type,
            data,
            correlate=correlate,
            qos=qos,
            retain=retain,
        )

    @staticmethod
    def id_from(evt: Any) -> str:
        for attr in ("message_id", "id", "utt_id"):
            value = getattr(evt, attr, None)
            if isinstance(value, str) and value:
                return value
        return ""
