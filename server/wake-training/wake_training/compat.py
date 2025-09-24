"""Compatibility helpers for environments running older Python versions."""

from enum import Enum

try:  # pragma: no cover - simple import guard
    from enum import StrEnum  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    class StrEnum(str, Enum):  # type: ignore[misc]
        """Minimal backport of Python 3.11's StrEnum."""

        pass

__all__ = ["StrEnum"]
