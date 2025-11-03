"""Integration tests for MQTT handler and display manager interaction."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ui_eink_display.config import DisplayConfig
from ui_eink_display.display_manager import DisplayManager
from ui_eink_display.display_state import DisplayMode, DisplayState
from ui_eink_display.mqtt_handler import MQTTHandler


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = DisplayConfig(
        mqtt_host="test-broker",
        mqtt_port=1883,
        mock_display=True,
        display_timeout_sec=45,
        log_level="DEBUG",
    )
    return config


@pytest.fixture
async def display_manager():
    """Create and initialize a display manager."""
    manager = DisplayManager(mock=True)
    await manager.initialize()
    yield manager
    await manager.shutdown()


@pytest.fixture
def display_state():
    """Create a display state instance."""
    return DisplayState(mode=DisplayMode.STANDBY)


@pytest.fixture
def mqtt_handler(mock_config, display_state, display_manager):
    """Create an MQTT handler instance."""
    return MQTTHandler(mock_config, display_state, display_manager)


@pytest.mark.asyncio
class TestMQTTDisplayIntegration:
    """Integration tests for MQTT handler and display manager."""

    async def test_wake_event_triggers_listening_mode(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test that wake event transitions display to LISTENING mode."""
        # Create wake event payload
        wake_payload = json.dumps({
            "type": "wake",
            "confidence": 0.85,
            "ts": 1699999999.0,
        })

        # Handle the wake event
        await mqtt_handler._handle_wake_event(wake_payload)

        # Verify state transition
        assert display_state.mode == DisplayMode.LISTENING

    async def test_wake_end_event_does_not_trigger_listening(
        self,
        mqtt_handler,
        display_state,
    ):
        """Test that wake end event does not trigger listening mode."""
        initial_mode = display_state.mode

        # Create wake end event payload
        wake_payload = json.dumps({
            "type": "end",
            "cause": "timeout",
        })

        # Handle the wake event
        await mqtt_handler._handle_wake_event(wake_payload)

        # Verify state did NOT change
        assert display_state.mode == initial_mode

    async def test_stt_final_triggers_processing_mode(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test that STT final transcript transitions to PROCESSING mode."""
        # Start from LISTENING mode
        display_state.transition_to(DisplayMode.LISTENING)

        # Create STT final payload
        stt_payload = json.dumps({
            "text": "What is the weather today?",
            "confidence": 0.92,
            "is_final": True,
        })

        # Handle the STT final
        await mqtt_handler._handle_stt_final(stt_payload)

        # Verify state transition
        assert display_state.mode == DisplayMode.PROCESSING
        assert display_state.user_message is not None
        assert display_state.user_message.text == "What is the weather today?"
        assert display_state.user_message.is_user is True

    async def test_llm_response_triggers_conversation_mode(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test that LLM response transitions to CONVERSATION mode."""
        # Start from PROCESSING mode with user message
        display_state.transition_to(DisplayMode.LISTENING)
        display_state.set_user_message("What is the weather?")

        # Create LLM response payload
        llm_payload = json.dumps({
            "id": "req123",
            "reply": "The weather is sunny with a high of 75 degrees.",
            "provider": "openai",
            "model": "gpt-4",
        })

        # Handle the LLM response
        await mqtt_handler._handle_llm_response(llm_payload)

        # Verify state transition
        assert display_state.mode == DisplayMode.CONVERSATION
        assert display_state.tars_message is not None
        assert display_state.tars_message.text == "The weather is sunny with a high of 75 degrees."
        assert display_state.tars_message.is_user is False

    async def test_llm_error_triggers_error_mode(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test that LLM error response transitions to ERROR mode."""
        # Start from PROCESSING mode
        display_state.transition_to(DisplayMode.LISTENING)
        display_state.set_user_message("Test question")

        # Create LLM error payload
        llm_payload = json.dumps({
            "id": "req456",
            "error": "API rate limit exceeded",
        })

        # Handle the LLM response
        await mqtt_handler._handle_llm_response(llm_payload)

        # Verify state transition
        assert display_state.mode == DisplayMode.ERROR
        assert "API rate limit exceeded" in display_state.error_message

    async def test_full_conversation_flow(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test complete conversation flow: wake → STT → LLM."""
        # 1. Start in STANDBY
        assert display_state.mode == DisplayMode.STANDBY

        # 2. Wake event → LISTENING
        wake_payload = json.dumps({"type": "wake", "confidence": 0.85})
        await mqtt_handler._handle_wake_event(wake_payload)
        assert display_state.mode == DisplayMode.LISTENING

        # 3. STT final → PROCESSING
        stt_payload = json.dumps({
            "text": "Tell me a joke",
            "confidence": 0.95,
        })
        await mqtt_handler._handle_stt_final(stt_payload)
        assert display_state.mode == DisplayMode.PROCESSING
        assert display_state.user_message.text == "Tell me a joke"

        # 4. LLM response → CONVERSATION
        llm_payload = json.dumps({
            "id": "req789",
            "reply": "Why did the robot go to therapy? It had bad AI-magination!",
        })
        await mqtt_handler._handle_llm_response(llm_payload)
        assert display_state.mode == DisplayMode.CONVERSATION
        assert display_state.tars_message.text == "Why did the robot go to therapy? It had bad AI-magination!"

    async def test_timeout_returns_to_standby(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test that timeout check returns display to STANDBY."""
        # Set up CONVERSATION mode
        display_state.transition_to(DisplayMode.LISTENING)
        display_state.set_user_message("Test")
        display_state.set_tars_message("Response")

        # Simulate timeout by setting old activity timestamp
        from datetime import datetime, timedelta
        display_state.last_activity = datetime.utcnow() - timedelta(seconds=60)

        # Check timeout should return true
        assert display_state.should_timeout(45) is True

        # Handle timeout
        display_state.handle_timeout()

        # Verify return to STANDBY
        assert display_state.mode == DisplayMode.STANDBY
        assert display_state.user_message is None
        assert display_state.tars_message is None

    async def test_invalid_stt_payload_logs_error(
        self,
        mqtt_handler,
        display_state,
        caplog,
    ):
        """Test that invalid STT payload logs validation error."""
        # Create invalid payload (missing required 'text' field)
        invalid_payload = json.dumps({"confidence": 0.9})

        # Should not raise exception, but should log error
        try:
            await mqtt_handler._handle_stt_final(invalid_payload)
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")

        # State should remain unchanged
        assert display_state.mode == DisplayMode.STANDBY

    async def test_invalid_llm_payload_logs_error(
        self,
        mqtt_handler,
        display_state,
        caplog,
    ):
        """Test that invalid LLM payload logs validation error."""
        # Create invalid payload (missing required 'id' field)
        invalid_payload = json.dumps({"reply": "Test"})

        # Should not raise exception, but should log error
        try:
            await mqtt_handler._handle_llm_response(invalid_payload)
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")

    async def test_invalid_wake_payload_logs_error(
        self,
        mqtt_handler,
        display_state,
    ):
        """Test that invalid wake payload logs validation error."""
        # Create invalid payload (missing required 'type' field)
        invalid_payload = json.dumps({"confidence": 0.8})

        # Should not raise exception, but should log error
        try:
            await mqtt_handler._handle_wake_event(invalid_payload)
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")

        # State should remain unchanged
        assert display_state.mode == DisplayMode.STANDBY

    async def test_consecutive_conversations(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test handling multiple consecutive conversations."""
        # First conversation
        await mqtt_handler._handle_wake_event(json.dumps({"type": "wake"}))
        await mqtt_handler._handle_stt_final(json.dumps({"text": "First question"}))
        await mqtt_handler._handle_llm_response(json.dumps({
            "id": "1",
            "reply": "First answer"
        }))
        assert display_state.mode == DisplayMode.CONVERSATION

        # Second conversation (new wake word)
        display_state.transition_to(DisplayMode.LISTENING)
        await mqtt_handler._handle_stt_final(json.dumps({"text": "Second question"}))
        await mqtt_handler._handle_llm_response(json.dumps({
            "id": "2",
            "reply": "Second answer"
        }))

        # Verify state updated with new messages
        assert display_state.mode == DisplayMode.CONVERSATION
        assert display_state.user_message.text == "Second question"
        assert display_state.tars_message.text == "Second answer"

    async def test_long_stt_message_handling(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test handling very long STT transcript."""
        display_state.transition_to(DisplayMode.LISTENING)

        long_text = "This is a very long transcription " * 20
        stt_payload = json.dumps({"text": long_text})

        await mqtt_handler._handle_stt_final(stt_payload)

        assert display_state.mode == DisplayMode.PROCESSING
        assert display_state.user_message.text == long_text

    async def test_long_llm_response_handling(
        self,
        mqtt_handler,
        display_state,
        display_manager,
    ):
        """Test handling very long LLM response."""
        display_state.transition_to(DisplayMode.LISTENING)
        display_state.set_user_message("Tell me a story")

        long_response = "Once upon a time in a galaxy far away " * 30
        llm_payload = json.dumps({"id": "story1", "reply": long_response})

        await mqtt_handler._handle_llm_response(llm_payload)

        assert display_state.mode == DisplayMode.CONVERSATION
        assert display_state.tars_message.text == long_response


@pytest.mark.asyncio
class TestHealthCheckIntegration:
    """Integration tests for health check functionality."""

    async def test_health_check_publishes_status(
        self,
        mock_config,
        display_state,
        display_manager,
    ):
        """Test that health check publishes status messages."""
        mqtt_handler = MQTTHandler(mock_config, display_state, display_manager)

        # Mock the MQTT client
        mock_client = AsyncMock()
        mqtt_handler.client = mock_client
        mqtt_handler._running = True

        # Run one iteration of health check
        mock_config.health_check_interval_sec = 0.1
        task = asyncio.create_task(mqtt_handler._health_check_loop())

        # Let it run briefly
        await asyncio.sleep(0.2)

        # Stop the task
        mqtt_handler._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify publish was called
        assert mock_client.publish.called


@pytest.mark.asyncio
class TestTimeoutCheckIntegration:
    """Integration tests for timeout check functionality."""

    async def test_timeout_check_transitions_to_standby(
        self,
        mock_config,
        display_state,
        display_manager,
    ):
        """Test that timeout check transitions to standby after timeout."""
        mqtt_handler = MQTTHandler(mock_config, display_state, display_manager)
        mqtt_handler._running = True

        # Set up state that should timeout
        display_state.transition_to(DisplayMode.LISTENING)
        display_state.set_user_message("Test")
        display_state.set_tars_message("Response")

        # Simulate old activity
        from datetime import datetime, timedelta
        display_state.last_activity = datetime.utcnow() - timedelta(seconds=60)

        # Set short timeout for testing
        mock_config.display_timeout_sec = 5

        # Run one iteration of timeout check
        task = asyncio.create_task(mqtt_handler._timeout_check_loop())

        # Let it run briefly
        await asyncio.sleep(0.1)

        # Stop the task
        mqtt_handler._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify state transitioned to STANDBY
        assert display_state.mode == DisplayMode.STANDBY
