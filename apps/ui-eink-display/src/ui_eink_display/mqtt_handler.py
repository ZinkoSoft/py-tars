"""
MQTT handler for UI E-Ink Display service.

Manages MQTT connections, subscriptions, and message routing.
"""

import asyncio
import json
import logging
from typing import Optional

from pydantic import ValidationError

from .config import DisplayConfig, MQTT_URL
from .display_manager import DisplayManager
from .display_state import DisplayMode, DisplayState

# Import contracts from tars-core
try:
    from tars.adapters.mqtt_client import MQTTClient
    from tars.contracts.envelope import Envelope
    from tars.contracts.v1.stt import FinalTranscript, TOPIC_STT_FINAL
    from tars.contracts.v1.llm import LLMResponse, TOPIC_LLM_RESPONSE
    from tars.contracts.v1.wake import WakeEvent, TOPIC_WAKE_EVENT
except ImportError as e:
    raise ImportError(
        f"Failed to import tars-core contracts: {e}. "
        "Ensure tars-core package is installed."
    )

logger = logging.getLogger(__name__)


class MQTTHandler:
    """
    Handles MQTT communication for the e-ink display service.

    Subscribes to:
    - stt/final: User speech transcripts
    - llm/response: TARS responses
    - wake/event: Wake word detection events

    Publishes health via centralized MQTTClient.
    """

    def __init__(
        self,
        config: DisplayConfig,
        state: DisplayState,
        display_manager: DisplayManager,
    ):
        """
        Initialize MQTT handler.

        Args:
            config: Service configuration
            state: Display state manager
            display_manager: Display rendering manager
        """
        self.config = config
        self.state = state
        self.display_manager = display_manager
        self.mqtt = MQTTClient(MQTT_URL, "tars-ui-eink-display", enable_health=True, enable_heartbeat=True)
        self._running = False
        self._timeout_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """
        Start MQTT client and begin processing messages.

        Establishes connection, subscribes to topics, and starts background tasks.
        """
        if self._running:
            logger.warning("MQTT handler already running")
            return

        self._running = True
        logger.info(f"Starting MQTT handler (broker: {MQTT_URL})")

        try:
            # Connect to MQTT broker
            await self.mqtt.connect()
            await self.publish_health(True, "UI E-Ink Display service ready")
            logger.info("Connected to MQTT broker")

            # Subscribe to topics
            await self._subscribe_topics()

            # Start background task
            self._timeout_task = asyncio.create_task(self._timeout_check_loop())

            # Keep running
            while self._running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Unexpected error in MQTT handler: {e}", exc_info=True)
            self.state.transition_to(
                DisplayMode.ERROR,
                error_message=f"System error: {e}",
            )
            await self.display_manager.render(self.state)
        finally:
            self._running = False
            await self._cleanup_tasks()

    async def stop(self) -> None:
        """Stop MQTT handler and cleanup resources."""
        logger.info("Stopping MQTT handler")
        self._running = False
        await self._cleanup_tasks()
        await self.mqtt.shutdown()

    async def publish_health(self, ok: bool, message: str = "") -> None:
        """Publish health status."""
        await self.mqtt.publish_health(
            ok=ok,
            event=message or ("ready" if ok else ""),
            err=None if ok else (message or "error")
        )

    async def _subscribe_topics(self) -> None:
        """Subscribe to MQTT topics."""
        await self.mqtt.subscribe(TOPIC_STT_FINAL, self._handle_stt_final_raw)
        await self.mqtt.subscribe(TOPIC_LLM_RESPONSE, self._handle_llm_response_raw)
        await self.mqtt.subscribe(TOPIC_WAKE_EVENT, self._handle_wake_event_raw)
        
        logger.info(f"Subscribed to {TOPIC_STT_FINAL}")
        logger.info(f"Subscribed to {TOPIC_LLM_RESPONSE}")
        logger.info(f"Subscribed to {TOPIC_WAKE_EVENT}")

    async def _handle_stt_final_raw(self, payload: bytes) -> None:
        """Raw callback wrapper for STT final transcript."""
        try:
            await self._handle_stt_final(payload.decode())
        except Exception as e:
            logger.error(f"Error handling STT final: {e}", exc_info=True)

    async def _handle_llm_response_raw(self, payload: bytes) -> None:
        """Raw callback wrapper for LLM response."""
        try:
            await self._handle_llm_response(payload.decode())
        except Exception as e:
            logger.error(f"Error handling LLM response: {e}", exc_info=True)

    async def _handle_wake_event_raw(self, payload: bytes) -> None:
        """Raw callback wrapper for wake event."""
        try:
            await self._handle_wake_event(payload.decode())
        except Exception as e:
            logger.error(f"Error handling wake event: {e}", exc_info=True)

    async def _handle_stt_final(self, payload: str) -> None:
        """
        Handle STT final transcript.

        Displays user message in PROCESSING mode.

        Args:
            payload: JSON payload (Envelope with FinalTranscript data)
        """
        # Parse envelope
        envelope_data = json.loads(payload)
        envelope = Envelope(**envelope_data)
        
        # Extract and validate FinalTranscript from envelope data
        transcript = FinalTranscript(**envelope.data)

        logger.info(f"STT final: {transcript.text}")

        # Update state with user message
        self.state.set_user_message(transcript.text)

        # Render display
        await self.display_manager.render(self.state)

    async def _handle_llm_response(self, payload: str) -> None:
        """
        Handle LLM response.

        Displays TARS message in CONVERSATION mode.

        Args:
            payload: JSON payload (Envelope with LLMResponse data)
        """
        # Parse envelope
        envelope_data = json.loads(payload)
        envelope = Envelope(**envelope_data)
        
        # Extract and validate LLMResponse from envelope data
        response = LLMResponse(**envelope.data)

        if response.error:
            logger.error(f"LLM error: {response.error}")
            self.state.transition_to(
                DisplayMode.ERROR,
                error_message=f"LLM error: {response.error}",
            )
        elif response.reply:
            logger.info(f"LLM response: {response.reply[:50]}...")

            # Update state with TARS message
            self.state.set_tars_message(response.reply)

        # Render display
        await self.display_manager.render(self.state)

    async def _handle_wake_event(self, payload: str) -> None:
        """
        Handle wake word detection event.

        Transitions to LISTENING mode.

        Args:
            payload: JSON payload (Envelope with WakeEvent data)
        """
        # Parse envelope
        envelope_data = json.loads(payload)
        envelope = Envelope(**envelope_data)
        
        # Extract and validate WakeEvent from envelope data
        wake_event = WakeEvent(**envelope.data)

        logger.info(f"Wake event: {wake_event.type}")

        # Only handle wake detection (not "end" events)
        if wake_event.type == "wake":
            self.state.transition_to(DisplayMode.LISTENING)

            # Render display
            await self.display_manager.render(self.state)

    async def _timeout_check_loop(self) -> None:
        """
        Check for display timeout and return to standby.

        Runs in background task.
        """
        logger.info(
            f"Starting timeout check loop (timeout: {self.config.display_timeout_sec}s)"
        )

        while self._running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds

                # Check if should timeout
                if self.state.should_timeout(self.config.display_timeout_sec):
                    logger.info("Display timeout, returning to standby")
                    self.state.handle_timeout()
                    await self.display_manager.render(self.state)

            except asyncio.CancelledError:
                logger.info("Timeout check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in timeout check loop: {e}", exc_info=True)

    async def _cleanup_tasks(self) -> None:
        """Cancel and cleanup background tasks."""
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass

        self._timeout_task = None
