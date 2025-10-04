"""TARS MCP Server - Character and Personality Management.

This is a pure MCP server that provides tools for TARS personality management.
It returns structured data that the llm-worker will use to publish MQTT messages.

NO MQTT code should be in this server - it's a pure tool provider.
"""
from __future__ import annotations

import os
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("tars-mcp-server")

# Create FastMCP app
app = FastMCP("TARS Character Manager")

# MQTT configuration (for return values only, not for publishing)
TOPIC_CHARACTER_UPDATE = os.getenv("TOPIC_CHARACTER_UPDATE", "character/update")


@app.tool()
def adjust_personality_trait(trait_name: str, new_value: int) -> dict[str, Any]:
    """Adjust a TARS personality trait value.
    
    TARS can use this to dynamically modify its own personality traits based on
    user requests or context. Changes are published to the memory-worker which
    updates the character state.
    
    Args:
        trait_name: Name of the trait to adjust (e.g., "humor", "honesty", "sarcasm")
        new_value: New value for the trait (0-100 scale)
    
    Returns:
        dict with status and mqtt_publish directive for llm-worker
    
    Example:
        User: "Set your humor to 50%"
        TARS calls: adjust_personality_trait(trait_name="humor", new_value=50)
    """
    # Validate trait value
    if not 0 <= new_value <= 100:
        return {
            "success": False,
            "error": f"Trait value must be between 0-100, got {new_value}",
        }
    
    # Valid trait names
    valid_traits = {
        "honesty", "humor", "empathy", "curiosity", "confidence", "formality",
        "sarcasm", "adaptability", "discipline", "imagination", "emotional_stability",
        "pragmatism", "optimism", "resourcefulness", "cheerfulness", "engagement",
        "respectfulness", "verbosity"
    }
    
    if trait_name.lower() not in valid_traits:
        return {
            "success": False,
            "error": f"Unknown trait '{trait_name}'. Valid traits: {', '.join(sorted(valid_traits))}",
        }
    
    try:
        # Return the update data - the LLM worker will publish it to MQTT
        # Pure MCP server - no MQTT dependencies here
        return {
            "success": True,
            "trait": trait_name.lower(),
            "new_value": new_value,
            "message": f"Trait '{trait_name}' will be adjusted to {new_value}%",
            "mqtt_publish": {
                "topic": TOPIC_CHARACTER_UPDATE,
                "event_type": "character.trait.update",
                "data": {
                    "trait": trait_name.lower(),
                    "value": new_value,
                },
                "source": "mcp-character",
            },
        }
    
    except Exception as e:
        logger.error(f"Failed to prepare trait update: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to prepare trait change: {str(e)}",
        }


@app.tool()
def get_current_traits() -> dict[str, Any]:
    """Get TARS's current personality trait values.
    
    Returns all current trait settings so TARS can reference them in conversation.
    
    Returns:
        dict with mqtt_publish directive to query traits
    """
    try:
        # Pure MCP server - return directive for llm-worker to publish MQTT query
        return {
            "success": True,
            "message": "Trait query will be sent to memory-worker",
            "mqtt_publish": {
                "topic": "character/get",
                "event_type": "character.get",
                "data": {
                    "section": "traits",
                },
                "source": "mcp-character",
            },
        }
    
    except Exception as e:
        logger.error(f"Failed to prepare trait query: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to prepare trait query: {str(e)}",
        }


@app.tool()
def reset_all_traits() -> dict[str, Any]:
    """Reset all personality traits to default values from character.toml.
    
    Returns:
        dict with mqtt_publish directive to reset traits
    """
    try:
        # Pure MCP server - return directive for llm-worker to publish MQTT command
        return {
            "success": True,
            "message": "All traits will be reset to default values",
            "mqtt_publish": {
                "topic": TOPIC_CHARACTER_UPDATE,
                "event_type": "character.trait.reset",
                "data": {
                    "reset_all": True,
                },
                "source": "mcp-character",
            },
        }
    
    except Exception as e:
        logger.error(f"Failed to prepare trait reset: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to prepare trait reset: {str(e)}",
        }
