from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

EVENT_TYPE_MEMORY_QUERY = "memory.query"
EVENT_TYPE_MEMORY_RESULTS = "memory.results"
EVENT_TYPE_CHARACTER_GET = "character.get"
EVENT_TYPE_CHARACTER_RESULT = "character.result"
EVENT_TYPE_CHARACTER_CURRENT = "system.character.current"
EVENT_TYPE_CHARACTER_UPDATE = "character.update"
EVENT_TYPE_MEMORY_HEALTH = "system.health.memory"


class BaseMemoryMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)

    model_config = {"extra": "forbid"}


class MemoryQuery(BaseMemoryMessage):
    text: str
    top_k: int = Field(default=5, ge=1, le=50)


class MemoryResult(BaseModel):
    document: dict[str, Any] | str
    score: float | None = None

    model_config = {"extra": "forbid"}


class MemoryResults(BaseMemoryMessage):
    query: str
    k: int
    results: list[MemoryResult] = Field(default_factory=list)


class CharacterGetRequest(BaseMemoryMessage):
    section: str | None = None


class CharacterSnapshot(BaseMemoryMessage):
    name: str
    description: str | None = None
    systemprompt: str | None = None
    traits: dict[str, Any] = Field(default_factory=dict)
    voice: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    scenario: dict[str, Any] = Field(default_factory=dict)
    personality_notes: dict[str, Any] = Field(default_factory=dict)
    example_interactions: dict[str, Any] = Field(default_factory=dict)


class CharacterSection(BaseMemoryMessage):
    section: str
    value: dict[str, Any] | str | None = None


class CharacterTraitUpdate(BaseMemoryMessage):
    """Update a single character trait value."""
    section: str = Field(default="traits")
    trait: str
    value: int = Field(ge=0, le=100)


class CharacterResetTraits(BaseMemoryMessage):
    """Reset all traits to defaults from character.toml."""
    action: str = Field(default="reset_traits")