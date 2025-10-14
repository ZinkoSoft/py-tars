"""TARS MCP Server - Character and Personality Management.

This MCP server provides tools for TARS to manage its own personality traits
and character settings through MQTT messages to the memory-worker.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import asyncio_mqtt as mqtt
from mcp.server.fastmcp import FastMCP
from tars.contracts.envelope import Envelope
from tars.contracts.v1.memory import (
    EVENT_TYPE_CHARACTER_UPDATE,
    CharacterGetRequest,
    CharacterResetTraits,
    CharacterTraitUpdate,
)

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("tars-mcp-server")

# Create FastMCP app
app = FastMCP("TARS Character Manager")

# MQTT configuration
MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@mqtt:1883")
TOPIC_CHARACTER_UPDATE = os.getenv("TOPIC_CHARACTER_UPDATE", "character/update")


@app.tool()
async def adjust_personality_trait(trait_name: str, new_value: int) -> dict[str, Any]:
    """Adjust a TARS personality trait value.

    TARS can use this to dynamically modify its own personality traits based on
    user requests or context. Changes are published to the memory-worker which
    updates the character state.

    Args:
        trait_name: Name of the trait to adjust (e.g., "humor", "honesty", "sarcasm")
        new_value: New value for the trait (0-100 scale)

    Returns:
        dict with status and updated trait information

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
        "honesty",
        "humor",
        "empathy",
        "curiosity",
        "confidence",
        "formality",
        "sarcasm",
        "adaptability",
        "discipline",
        "imagination",
        "emotional_stability",
        "pragmatism",
        "optimism",
        "resourcefulness",
        "cheerfulness",
        "engagement",
        "respectfulness",
        "verbosity",
    }

    if trait_name.lower() not in valid_traits:
        return {
            "success": False,
            "error": f"Unknown trait '{trait_name}'. Valid traits: {', '.join(sorted(valid_traits))}",
        }

    try:
        # Create typed payload
        trait_update = CharacterTraitUpdate(
            trait=trait_name.lower(),
            value=new_value,
        )

        # Wrap in envelope and publish to memory-worker via MQTT
        envelope = Envelope(
            type=EVENT_TYPE_CHARACTER_UPDATE,
            data=trait_update.model_dump(),
        )

        async with mqtt.Client(MQTT_URL) as client:
            await client.publish(
                TOPIC_CHARACTER_UPDATE,
                envelope.model_dump_json(),
                qos=1,
            )

            logger.info(f"Published trait update: {trait_name}={new_value}")

            return {
                "success": True,
                "trait": trait_name.lower(),
                "old_value": "unknown",  # Memory-worker tracks old value
                "new_value": new_value,
                "message": f"Trait '{trait_name}' adjusted to {new_value}%",
            }

    except Exception as e:
        logger.error(f"Failed to adjust trait: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to communicate trait change: {str(e)}",
        }


@app.tool()
async def get_current_traits() -> dict[str, Any]:
    """Get TARS's current personality trait values.

    Returns all current trait settings so TARS can reference them in conversation.

    Returns:
        dict with current trait values
    """
    try:
        # Create typed query request
        char_request = CharacterGetRequest(section="traits")

        # Wrap in envelope
        envelope = Envelope(
            type="character.get",
            data=char_request.model_dump(),
        )

        # Query current character state from memory-worker
        async with mqtt.Client(MQTT_URL) as client:
            await client.publish(
                "character/get",
                envelope.model_dump_json(),
                qos=1,
            )

            # Wait for response (with timeout)
            # Note: This is a simplified implementation
            # In production, you'd use a proper request-response pattern
            await asyncio.sleep(0.5)

            return {
                "success": True,
                "message": "Trait query sent. Check character/current topic for latest values.",
                "note": "Actual values are maintained by memory-worker",
            }

    except Exception as e:
        logger.error(f"Failed to get traits: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to query traits: {str(e)}",
        }


@app.tool()
async def reset_all_traits() -> dict[str, Any]:
    """Reset all personality traits to default values from character.toml.

    Returns:
        dict with status of reset operation
    """
    try:
        # Create typed reset request
        reset_request = CharacterResetTraits()

        # Wrap in envelope
        envelope = Envelope(
            type=EVENT_TYPE_CHARACTER_UPDATE,
            data=reset_request.model_dump(),
        )

        async with mqtt.Client(MQTT_URL) as client:
            await client.publish(
                TOPIC_CHARACTER_UPDATE,
                envelope.model_dump_json(),
                qos=1,
            )

            logger.info("Published trait reset request")

            return {
                "success": True,
                "message": "All traits reset to default values from character.toml",
            }

    except Exception as e:
        logger.error(f"Failed to reset traits: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to reset traits: {str(e)}",
        }
