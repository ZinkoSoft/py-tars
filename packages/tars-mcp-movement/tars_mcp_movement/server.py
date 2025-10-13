"""TARS MCP Server - Movement and Action Control.

This is a pure MCP server that provides tools for TARS robot movement control.
It returns structured data that the llm-worker will use to publish MQTT messages.

NO MQTT code should be in this server - it's a pure tool provider.

Based on firmware/esp32/movements/sequences.py movement library.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("tars-mcp-movement")

# Create FastMCP app
app = FastMCP("TARS Movement Controller")

# MQTT configuration (for return values only, not for publishing)
TOPIC_MOVEMENT_TEST = os.getenv("TOPIC_MOVEMENT_TEST", "movement/test")
TOPIC_MOVEMENT_STOP = os.getenv("TOPIC_MOVEMENT_STOP", "movement/stop")


# ============================================================================
# MOVEMENT TOOLS (Direct Robot Control)
# ============================================================================


@app.tool()
def move_forward(speed: float = 0.8) -> dict[str, Any]:
    """Move the robot forward one step.
    
    Use this when the user asks to move forward, advance, or go ahead.
    
    Args:
        speed: Movement speed (0.1-1.0). Higher is faster. Default 0.8.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Move forward"
        TARS calls: move_forward(speed=0.8)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Moving forward at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "step_forward",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def move_backward(speed: float = 0.8) -> dict[str, Any]:
    """Move the robot backward one step.
    
    Use this when the user asks to move back, reverse, or retreat.
    
    Args:
        speed: Movement speed (0.1-1.0). Default 0.8.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Back up a bit"
        TARS calls: move_backward(speed=0.7)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Moving backward at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "step_backward",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def turn_left(speed: float = 0.8) -> dict[str, Any]:
    """Rotate the robot to the left.
    
    Use this when the user asks to turn left, rotate left, or face left.
    
    Args:
        speed: Rotation speed (0.1-1.0). Default 0.8.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Turn left"
        TARS calls: turn_left(speed=0.8)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Turning left at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "turn_left",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def turn_right(speed: float = 0.8) -> dict[str, Any]:
    """Rotate the robot to the right.
    
    Use this when the user asks to turn right, rotate right, or face right.
    
    Args:
        speed: Rotation speed (0.1-1.0). Default 0.8.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Turn around to the right"
        TARS calls: turn_right(speed=0.8)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Turning right at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "turn_right",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def stop_movement() -> dict[str, Any]:
    """Emergency stop - immediately halt all movement and clear queue.
    
    Use this when the user asks to stop, halt, or cancel movement.
    This clears the movement queue and stops any in-progress actions.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Stop moving!"
        TARS calls: stop_movement()
    """
    return {
        "success": True,
        "message": "Emergency stop triggered - all movements halted",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_STOP,
            "event_type": "movement.stop",
            "data": {},
            "source": "mcp-movement",
        },
    }


# ============================================================================
# ACTION TOOLS (Expressive/Non-Movement)
# ============================================================================


@app.tool()
def wave(speed: float = 0.7) -> dict[str, Any]:
    """Wave gesture - wave with right arm.
    
    Use this when greeting users, saying goodbye, or being friendly.
    TARS can decide to use this when appropriate for the conversation context.
    
    Args:
        speed: Wave speed (0.1-1.0). Default 0.7.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Hi TARS!"
        TARS: "Hello! *waves*"
        TARS calls: wave(speed=0.7)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Waving at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "wave",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def laugh(speed: float = 0.9) -> dict[str, Any]:
    """Laughing animation - bouncing motion.
    
    Use this when TARS finds something funny or to express joy.
    TARS can decide to use this in humorous conversation contexts.
    
    Args:
        speed: Bounce speed (0.1-1.0). Default 0.9 (energetic).
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: *tells a joke*
        TARS: "Haha! That's a good one! *laughs*"
        TARS calls: laugh(speed=0.9)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Laughing at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "laugh",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def bow(speed: float = 0.5) -> dict[str, Any]:
    """Bow forward - polite bow gesture.
    
    Use this to show respect, gratitude, or acknowledge applause.
    TARS can use this when being polite or formal.
    
    Args:
        speed: Bow speed (0.1-1.0). Default 0.5 (deliberate).
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Thank you TARS!"
        TARS: "You're welcome! *bows*"
        TARS calls: bow(speed=0.5)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Bowing at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "bow",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def point(speed: float = 0.7) -> dict[str, Any]:
    """Pointing gesture - extend right arm forward to point.
    
    Use this to emphasize a point, direct attention, or gesture while explaining.
    TARS can use this for emphasis during explanations.
    
    Args:
        speed: Pointing speed (0.1-1.0). Default 0.7.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "What time is it?"
        TARS: "It's 3 PM! *points at clock*"
        TARS calls: point(speed=0.7)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Pointing at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "now",  # ESP32 calls it "now"
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def pose(speed: float = 0.6) -> dict[str, Any]:
    """Strike a pose - confident stance.
    
    Use this to show confidence, celebrate success, or be dramatic.
    TARS can use this when feeling accomplished or showing off.
    
    Args:
        speed: Pose speed (0.1-1.0). Default 0.6.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "You're awesome TARS!"
        TARS: "Why thank you! *strikes a pose*"
        TARS calls: pose(speed=0.6)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Striking a pose at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "pose",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def celebrate(speed: float = 0.8) -> dict[str, Any]:
    """Celebration animation - balancing motion to show excitement.
    
    Use this to celebrate victories, good news, or successful outcomes.
    TARS can use this when something exciting happens.
    
    Args:
        speed: Celebration speed (0.1-1.0). Default 0.8.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "I got the job!"
        TARS: "Congratulations! That's fantastic! *celebrates*"
        TARS calls: celebrate(speed=0.8)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Celebrating at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "balance",  # ESP32 balance motion for celebration
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def swing_legs(speed: float = 0.6) -> dict[str, Any]:
    """Swing legs - pendulum leg motion for playfulness.
    
    Use this to show a playful, relaxed mood or during idle conversation.
    TARS can use this when being casual or playful.
    
    Args:
        speed: Swing speed (0.1-1.0). Default 0.6.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "What are you up to?"
        TARS: "Just hanging out! *swings legs*"
        TARS calls: swing_legs(speed=0.6)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Swinging legs at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "swing_legs",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def pezz_dispenser(speed: float = 0.5) -> dict[str, Any]:
    """Dispense candy motion - tilt head back and hold for 10 seconds.
    
    Use this for the Pez candy dispenser motion. TARS tilts back dramatically
    and holds the position for 10 seconds (classic Pez dispenser motion).
    
    Args:
        speed: Tilt speed (0.1-1.0). Default 0.5 (deliberate).
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Do the Pez dispenser thing"
        TARS: "Here comes the candy! *tilts back*"
        TARS calls: pezz_dispenser(speed=0.5)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Executing Pez dispenser motion at speed {speed} (10s hold)",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "pezz_dispenser",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def mic_drop(speed: float = 0.8) -> dict[str, Any]:
    """Dramatic mic drop gesture - raise arm then drop hand quickly.
    
    Use this after delivering a zinger, making a great point, or finishing
    a performance. TARS raises arm then drops hand in dramatic fashion.
    
    Args:
        speed: Movement speed (0.1-1.0). Default 0.8.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "What's 2+2?"
        TARS: "Four. *mic drop*"
        TARS calls: mic_drop(speed=0.8)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Dropping the mic at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "mic_drop",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def monster_pose(speed: float = 0.7) -> dict[str, Any]:
    """Defensive/threatening pose - arms up and spread wide.
    
    Use this to appear intimidating, protective, or when being playfully scary.
    TARS raises both arms up and spreads them wide while crouching slightly.
    
    Args:
        speed: Pose speed (0.1-1.0). Default 0.7.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        User: "Show me your scary face"
        TARS: "RAWR! *monster pose*"
        TARS calls: monster_pose(speed=0.7)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Striking monster pose at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "monster",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }


@app.tool()
def reset_position(speed: float = 0.8) -> dict[str, Any]:
    """Return to neutral position - reset all servos.
    
    Use this after complex movements or when TARS needs to return to rest state.
    Good for cleanup after sequences or preparing for next action.
    
    Args:
        speed: Reset speed (0.1-1.0). Default 0.8.
    
    Returns:
        dict with mqtt_publish directive for llm-worker
    
    Example:
        TARS: "Let me reset to neutral position"
        TARS calls: reset_position(speed=0.8)
    """
    if not 0.1 <= speed <= 1.0:
        return {
            "success": False,
            "error": f"Speed must be between 0.1-1.0, got {speed}",
        }
    
    return {
        "success": True,
        "message": f"Resetting to neutral position at speed {speed}",
        "mqtt_publish": {
            "topic": TOPIC_MOVEMENT_TEST,
            "event_type": "movement.command",
            "data": {
                "command": "reset",
                "speed": speed,
                "request_id": str(uuid.uuid4()),
            },
            "source": "mcp-movement",
        },
    }
