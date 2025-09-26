from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Optional


@dataclass(slots=True)
class TTSControlMessage:
    """Validated representation of a `tts/control` payload."""

    VALID_ACTIONS: ClassVar[set[str]] = {"pause", "resume", "stop"}

    action: str
    reason: str
    request_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Any) -> "TTSControlMessage":
        if not isinstance(data, dict):
            raise ValueError("control payload must be a JSON object")
        action = data.get("action")
        if not isinstance(action, str) or action.lower() not in cls.VALID_ACTIONS:
            raise ValueError(f"unsupported control action: {action!r}")
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("control reason is required")
        ctrl_id = data.get("id")
        if ctrl_id is not None and not isinstance(ctrl_id, str):
            raise ValueError("control id must be a string when provided")
        return cls(action=action.lower(), reason=reason.strip(), request_id=ctrl_id)
