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
        """Build system prompt from character traits and optional base prompt.
        
        Priority:
        1. Use character.systemprompt if provided, append traits
        2. Otherwise build from traits and description
        3. Append base_system if provided
        """
        if not self.character:
            return base_system
        
        name = self.character.get("name") or "Assistant"
        sys_prompt = (self.character.get("systemprompt") or "").strip()
        traits = self.character.get("traits") or {}
        desc = self.character.get("description") or (self.character.get("meta") or {}).get("description")
        
        parts: list[str] = []
        
        if sys_prompt:
            parts.append(sys_prompt)
        
        # Append traits if present
        if traits:
            trait_pairs = [f"{k}: {v}" for k, v in traits.items()]
            trait_line = f"You are {name}. Traits: " + "; ".join(trait_pairs) + "."
            if desc:
                trait_line = (trait_line + " " + str(desc)).strip()
            parts.append(trait_line)
        elif not sys_prompt:
            # Fallback minimal persona
            fallback = f"You are {name}."
            if desc:
                fallback = (fallback + " " + str(desc)).strip()
            parts.append(fallback)
        
        persona = "\n".join(p for p in parts if p).strip() or None
        
        if base_system and persona:
            return persona + "\n\n" + base_system
        return base_system or persona
