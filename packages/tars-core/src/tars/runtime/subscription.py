from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Type


@dataclass(frozen=True, slots=True)
class Sub:
    """Describe a subscription binding topic -> handler."""

    topic: str
    model: Type[Any]
    handler: Callable[[Any, "Ctx"], Awaitable[None]]
    qos: int = 1


# NOTE: We import Ctx lazily to avoid circular import at module load time.
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .ctx import Ctx
