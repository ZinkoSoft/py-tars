"""Character/persona management."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CharacterManager:
    """Manages character/persona state and system prompt generation."""

    def __init__(self):
        self.character: Dict[str, Any] = {}

    def get_name(self) -> Optional[str]:
        """Get character name."""
        return self.character.get("name")

    def update_from_current(self, data: Dict[str, Any]) -> None:
        """Update character from full snapshot (character/current)."""
        self.character = data
        logger.info("Character updated: name=%s", self.character.get("name"))

    def update_section(self, section_key: str, value: Any) -> None:
        """Update a single section of character state."""
        self.character.setdefault(section_key, value)
        self.character[section_key] = value
        logger.info("Character section updated: %s", section_key)

    def merge_update(self, data: Dict[str, Any]) -> None:
        """Merge partial update into character state."""
        self.character.update(data)
        logger.info("Character partially updated")

    def update(self, data: Dict[str, Any]) -> None:
        """Update character state from MQTT message.

        Handles both full snapshots and section updates.
        DEPRECATED: Use update_from_current, update_section, or merge_update instead.

        Args:
            data: Character data from MQTT (full snapshot or section update)
        """
        if "name" in data:
            # Full character snapshot
            self.update_from_current(data)
        elif "section" in data and "value" in data:
            # Section update
            section_key = data.get("section")
            if isinstance(section_key, str):
                self.update_section(section_key, data.get("value"))
        else:
            # Partial update
            self.merge_update(data)

    def build_system_prompt(self, base_system: Optional[str] = None) -> Optional[str]:
        """Build comprehensive system prompt from all character data.

        Incorporates:
        - systemprompt (primary personality instructions)
        - description (character background)
        - scenario (world context)
        - personality_notes (behavioral guidelines)
        - example_interactions (communication style examples)
        - traits (quantified personality metrics)

        Priority:
        1. Use character.systemprompt as foundation
        2. Append scenario context if available
        3. Append personality notes if available
        4. Include example interactions for style guidance
        5. Append base_system if provided
        """
        if not self.character:
            return base_system

        name = self.character.get("name") or "Assistant"
        sys_prompt = (self.character.get("systemprompt") or "").strip()
        desc = self.character.get("description") or (self.character.get("meta") or {}).get(
            "description"
        )
        traits = self.character.get("traits") or {}
        scenario = self.character.get("scenario") or {}
        personality_notes = self.character.get("personality_notes") or {}
        example_interactions = self.character.get("example_interactions") or {}

        parts: list[str] = []

        # Primary system prompt
        if sys_prompt:
            parts.append(sys_prompt)
        elif desc:
            # Fallback to description if no system prompt
            parts.append(f"You are {name}. {desc}")
        else:
            # Minimal fallback
            parts.append(f"You are {name}.")

        # Scenario context (world/setting)
        if scenario:
            scenario_parts = []
            if "world" in scenario:
                scenario_parts.append(f"World Context: {scenario['world']}")
            if "context" in scenario:
                scenario_parts.append(f"Operational Context: {scenario['context']}")
            if scenario_parts:
                parts.append("\n".join(scenario_parts))

        # Personality notes (behavioral guidelines)
        if personality_notes:
            notes_parts = ["Behavioral Guidelines:"]
            for key, value in personality_notes.items():
                if isinstance(value, str):
                    notes_parts.append(f"- {key.replace('_', ' ').title()}: {value}")
            if len(notes_parts) > 1:  # Has content beyond header
                parts.append("\n".join(notes_parts))

        # Example interactions (communication style)
        if example_interactions:
            examples = []
            for key, value in example_interactions.items():
                if isinstance(value, str) and value.strip():
                    examples.append(value.strip())
            if examples:
                parts.append("Example Communication Style:\n" + "\n\n".join(examples))

        # Traits summary (quantified metrics)
        if traits:
            trait_pairs = [f"{k}: {v}" for k, v in traits.items()]
            parts.append("Personality Metrics: " + "; ".join(trait_pairs))

        persona = "\n\n".join(p for p in parts if p).strip() or None

        if base_system and persona:
            return persona + "\n\n" + base_system
        return base_system or persona
