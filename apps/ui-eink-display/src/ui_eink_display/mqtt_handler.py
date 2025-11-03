"""
MQTT handler for UI E-Ink Display service.

Manages MQTT connections, subscriptions, and message routing.
"""

import asyncio
import json
import logging
from typing import Optional

import asyncio_mqtt as aiomqtt
from pydantic import ValidationError

from .config import DisplayConfig
from .display_manager import DisplayManager
from .display_state import DisplayMode, DisplayState

# Import contracts from tars-core
try:
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

    Publishes to:
    - system/health/ui-eink-display: Health check heartbeats
    """

    TOPIC_HEALTH = "system/health/ui-eink-display"

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
        self.client: Optional[aiomqtt.Client] = None
        self._running = False
        self._health_task: Optional[asyncio.Task] = None
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
        logger.info(
            f"Starting MQTT handler (broker: {self.config.mqtt_host}:{self.config.mqtt_port})"
        )

        try:
            # Connect to MQTT broker
            async with aiomqtt.Client(
                hostname=self.config.mqtt_host,
                port=self.config.mqtt_port,
                client_id=self.config.mqtt_client_id,
            ) as client:
                self.client = client
                logger.info("Connected to MQTT broker")

                # Subscribe to topics
                await self._subscribe_topics()

                # Start background tasks
                self._health_task = asyncio.create_task(self._health_check_loop())
                self._timeout_task = asyncio.create_task(self._timeout_check_loop())

                # Process messages
                async with client.messages() as messages:
                    async for message in messages:
                        try:
                            await self._handle_message(message)
                        except Exception as e:
                            logger.error(f"Error handling message: {e}", exc_info=True)

        except aiomqtt.MqttError as e:
            logger.error(f"MQTT connection error: {e}")
            self.state.transition_to(
                DisplayMode.ERROR,
                error_message=f"MQTT connection failed: {e}",
            )
            await self.display_manager.render(self.state)
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

    async def _subscribe_topics(self) -> None:
        """Subscribe to MQTT topics."""
        if not self.client:
            raise RuntimeError("MQTT client not connected")

        topics = [
            TOPIC_STT_FINAL,
            TOPIC_LLM_RESPONSE,
            TOPIC_WAKE_EVENT,
        ]

        for topic in topics:
            await self.client.subscribe(topic)
            logger.info(f"Subscribed to {topic}")

    async def _handle_message(self, message: aiomqtt.Message) -> None:
        """
        Route incoming MQTT message to appropriate handler.

        Args:
            message: MQTT message
        """
        topic = str(message.topic)
        payload = message.payload.decode()

        logger.debug(f"Received message on {topic}: {payload[:100]}...")

        try:
            if topic == TOPIC_STT_FINAL:
                await self._handle_stt_final(payload)
            elif topic == TOPIC_LLM_RESPONSE:
                await self._handle_llm_response(payload)
            elif topic == TOPIC_WAKE_EVENT:
                await self._handle_wake_event(payload)
            else:
                logger.warning(f"Unexpected topic: {topic}")

        except ValidationError as e:
            logger.error(f"Contract validation failed for {topic}: {e}")
        except Exception as e:
            logger.error(f"Error processing {topic}: {e}", exc_info=True)

    async def _handle_stt_final(self, payload: str) -> None:
        """
        Handle STT final transcript.

        Displays user message in PROCESSING mode.

        Args:
            payload: JSON payload
        """
        data = json.loads(payload)
        transcript = FinalTranscript(**data)

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
            payload: JSON payload
        """
        data = json.loads(payload)
        response = LLMResponse(**data)

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
            payload: JSON payload
        """
        data = json.loads(payload)
        wake_event = WakeEvent(**data)

        logger.info(f"Wake event: {wake_event.type}")

        # Only handle wake detection (not "end" events)
        if wake_event.type == "wake":
            self.state.transition_to(DisplayMode.LISTENING)

            # Render display
            await self.display_manager.render(self.state)

    async def _health_check_loop(self) -> None:
        """
        Publish periodic health check heartbeats.

        Runs in background task.
        """
        logger.info(
            f"Starting health check loop (interval: {self.config.health_check_interval_sec}s)"
        )

        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval_sec)

                if not self.client:
                    continue

                # Publish health status
                health_data = {
                    "service": "ui-eink-display",
                    "status": "healthy",
                    "mode": self.state.mode.value,
                    "uptime": (
                        self.state.last_update.timestamp()
                        - self.state.last_activity.timestamp()
                    ),
                }

                await self.client.publish(
                    self.TOPIC_HEALTH,
                    payload=json.dumps(health_data),
                    qos=0,
                )

                logger.debug(f"Published health check: {health_data}")

            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)

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
        for task in [self._health_task, self._timeout_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._health_task = None
        self._timeout_task = None
