"""Movement service models - now importing from tars-core contracts."""

from __future__ import annotations

# Import all contracts from tars-core
from tars.contracts.v1.movement import (
    MovementAction,
    MovementCommand,
    MovementFrame,
    MovementState,
    MovementStateEvent,
)

# Re-export for backward compatibility within movement-service
__all__ = [
    "MovementAction",
    "MovementCommand",
    "MovementFrame",
    "MovementState",
    "MovementStateEvent",
]
