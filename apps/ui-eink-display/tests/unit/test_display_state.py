"""Unit tests for display_state.py."""

from datetime import datetime, timedelta

import pytest

from ui_eink_display.display_state import (
    DisplayMode,
    DisplayState,
    MessageBubble,
)


class TestDisplayMode:
    """Test suite for DisplayMode enum."""

    def test_display_mode_values(self):
        """Test all display modes have correct values."""
        assert DisplayMode.STANDBY.value == "standby"
        assert DisplayMode.LISTENING.value == "listening"
        assert DisplayMode.PROCESSING.value == "processing"
        assert DisplayMode.CONVERSATION.value == "conversation"
        assert DisplayMode.ERROR.value == "error"


class TestMessageBubble:
    """Test suite for MessageBubble dataclass."""

    def test_create_user_message(self):
        """Test creating a user message bubble."""
        bubble = MessageBubble(text="Hello TARS", is_user=True)

        assert bubble.text == "Hello TARS"
        assert bubble.is_user is True
        assert isinstance(bubble.timestamp, datetime)
        assert bubble.wrapped_lines == ["Hello TARS"]

    def test_create_tars_message(self):
        """Test creating a TARS message bubble."""
        bubble = MessageBubble(text="Hello human", is_user=False)

        assert bubble.text == "Hello human"
        assert bubble.is_user is False
        assert isinstance(bubble.timestamp, datetime)

    def test_wrapped_lines_provided(self):
        """Test providing wrapped lines explicitly."""
        lines = ["Line 1", "Line 2", "Line 3"]
        bubble = MessageBubble(
            text="Original text",
            is_user=True,
            wrapped_lines=lines,
        )

        assert bubble.wrapped_lines == lines


class TestDisplayState:
    """Test suite for DisplayState dataclass."""

    def test_initial_state(self):
        """Test initial state is STANDBY."""
        state = DisplayState()

        assert state.mode == DisplayMode.STANDBY
        assert isinstance(state.last_update, datetime)
        assert isinstance(state.last_activity, datetime)
        assert state.user_message is None
        assert state.tars_message is None
        assert state.error_message is None

    def test_transition_to_listening(self):
        """Test transitioning from STANDBY to LISTENING."""
        state = DisplayState()
        initial_time = state.last_update

        state.transition_to(DisplayMode.LISTENING)

        assert state.mode == DisplayMode.LISTENING
        assert state.last_update > initial_time
        assert state.last_activity > initial_time
        assert state.user_message is None
        assert state.tars_message is None

    def test_transition_to_processing(self):
        """Test transitioning from LISTENING to PROCESSING."""
        state = DisplayState(mode=DisplayMode.LISTENING)

        state.transition_to(DisplayMode.PROCESSING)

        assert state.mode == DisplayMode.PROCESSING

    def test_transition_to_conversation(self):
        """Test transitioning from PROCESSING to CONVERSATION."""
        state = DisplayState(mode=DisplayMode.PROCESSING)

        state.transition_to(DisplayMode.CONVERSATION)

        assert state.mode == DisplayMode.CONVERSATION

    def test_transition_to_error(self):
        """Test transitioning to ERROR from any state."""
        state = DisplayState()
        error_msg = "Test error"

        state.transition_to(DisplayMode.ERROR, error_message=error_msg)

        assert state.mode == DisplayMode.ERROR
        assert state.error_message == error_msg
        assert isinstance(state.error_timestamp, datetime)

    def test_transition_to_standby_clears_messages(self):
        """Test transitioning to STANDBY clears messages."""
        state = DisplayState(mode=DisplayMode.CONVERSATION)
        state.user_message = MessageBubble(text="User msg", is_user=True)
        state.tars_message = MessageBubble(text="TARS msg", is_user=False)
        state.error_message = "Error"

        state.transition_to(DisplayMode.STANDBY)

        assert state.mode == DisplayMode.STANDBY
        assert state.user_message is None
        assert state.tars_message is None
        assert state.error_message is None

    def test_transition_invalid(self):
        """Test invalid state transition raises error."""
        state = DisplayState(mode=DisplayMode.STANDBY)

        # Cannot go directly from STANDBY to PROCESSING
        with pytest.raises(ValueError, match="Invalid transition"):
            state.transition_to(DisplayMode.PROCESSING)

    def test_transition_same_state(self):
        """Test transitioning to same state is allowed."""
        state = DisplayState()

        state.transition_to(DisplayMode.STANDBY)

        assert state.mode == DisplayMode.STANDBY

    def test_set_user_message(self):
        """Test setting user message transitions to PROCESSING."""
        state = DisplayState(mode=DisplayMode.LISTENING)
        text = "What is the weather?"

        state.set_user_message(text)

        assert state.mode == DisplayMode.PROCESSING
        assert state.user_message is not None
        assert state.user_message.text == text
        assert state.user_message.is_user is True

    def test_set_tars_message(self):
        """Test setting TARS message transitions to CONVERSATION."""
        state = DisplayState(mode=DisplayMode.PROCESSING)
        state.user_message = MessageBubble(text="Question", is_user=True)
        text = "The weather is sunny"

        state.set_tars_message(text)

        assert state.mode == DisplayMode.CONVERSATION
        assert state.tars_message is not None
        assert state.tars_message.text == text
        assert state.tars_message.is_user is False

    def test_should_timeout_standby(self):
        """Test STANDBY mode never times out."""
        state = DisplayState(mode=DisplayMode.STANDBY)
        state.last_activity = datetime.utcnow() - timedelta(hours=1)

        assert state.should_timeout(60) is False

    def test_should_timeout_listening(self):
        """Test LISTENING mode never times out."""
        state = DisplayState(mode=DisplayMode.LISTENING)
        state.last_activity = datetime.utcnow() - timedelta(hours=1)

        assert state.should_timeout(60) is False

    def test_should_timeout_processing(self):
        """Test PROCESSING mode times out after threshold."""
        state = DisplayState(mode=DisplayMode.PROCESSING)
        
        # Just before timeout
        state.last_activity = datetime.utcnow() - timedelta(seconds=59)
        assert state.should_timeout(60) is False

        # After timeout
        state.last_activity = datetime.utcnow() - timedelta(seconds=61)
        assert state.should_timeout(60) is True

    def test_should_timeout_conversation(self):
        """Test CONVERSATION mode times out after threshold."""
        state = DisplayState(mode=DisplayMode.CONVERSATION)
        
        # Just before timeout
        state.last_activity = datetime.utcnow() - timedelta(seconds=44)
        assert state.should_timeout(45) is False

        # After timeout
        state.last_activity = datetime.utcnow() - timedelta(seconds=46)
        assert state.should_timeout(45) is True

    def test_should_timeout_error(self):
        """Test ERROR mode times out after threshold."""
        state = DisplayState(mode=DisplayMode.ERROR)
        
        # Just before timeout
        state.last_activity = datetime.utcnow() - timedelta(seconds=29)
        assert state.should_timeout(30) is False

        # After timeout
        state.last_activity = datetime.utcnow() - timedelta(seconds=31)
        assert state.should_timeout(30) is True

    def test_handle_timeout(self):
        """Test handling timeout transitions to STANDBY."""
        state = DisplayState(mode=DisplayMode.CONVERSATION)
        state.user_message = MessageBubble(text="Test", is_user=True)

        state.handle_timeout()

        assert state.mode == DisplayMode.STANDBY
        assert state.user_message is None

    def test_handle_timeout_from_standby(self):
        """Test handling timeout from STANDBY does nothing."""
        state = DisplayState(mode=DisplayMode.STANDBY)
        original_mode = state.mode

        state.handle_timeout()

        assert state.mode == original_mode

    def test_get_status_summary_standby(self):
        """Test status summary for STANDBY mode."""
        state = DisplayState(mode=DisplayMode.STANDBY)

        summary = state.get_status_summary()

        assert "Mode: standby" in summary
        assert "Elapsed:" in summary

    def test_get_status_summary_error(self):
        """Test status summary for ERROR mode."""
        state = DisplayState(mode=DisplayMode.ERROR)
        state.error_message = "Connection failed"

        summary = state.get_status_summary()

        assert "Mode: error" in summary
        assert "Error: Connection failed" in summary

    def test_get_status_summary_conversation(self):
        """Test status summary for CONVERSATION mode."""
        state = DisplayState(mode=DisplayMode.CONVERSATION)
        state.user_message = MessageBubble(text="User", is_user=True)
        state.tars_message = MessageBubble(text="TARS", is_user=False)

        summary = state.get_status_summary()

        assert "Mode: conversation" in summary
        assert "Messages: 2" in summary

    def test_valid_transition_paths(self):
        """Test all valid transition paths work."""
        # STANDBY -> LISTENING
        state = DisplayState(mode=DisplayMode.STANDBY)
        state.transition_to(DisplayMode.LISTENING)
        assert state.mode == DisplayMode.LISTENING

        # LISTENING -> PROCESSING
        state.transition_to(DisplayMode.PROCESSING)
        assert state.mode == DisplayMode.PROCESSING

        # PROCESSING -> CONVERSATION
        state.transition_to(DisplayMode.CONVERSATION)
        assert state.mode == DisplayMode.CONVERSATION

        # CONVERSATION -> LISTENING (new wake word)
        state.transition_to(DisplayMode.LISTENING)
        assert state.mode == DisplayMode.LISTENING

        # Any -> ERROR
        state.transition_to(DisplayMode.ERROR, error_message="Test")
        assert state.mode == DisplayMode.ERROR

        # ERROR -> STANDBY (recovery)
        state.transition_to(DisplayMode.STANDBY)
        assert state.mode == DisplayMode.STANDBY

    def test_transition_listening_clears_old_messages(self):
        """Test transitioning to LISTENING clears previous interaction."""
        state = DisplayState(mode=DisplayMode.CONVERSATION)
        state.user_message = MessageBubble(text="Old user msg", is_user=True)
        state.tars_message = MessageBubble(text="Old TARS msg", is_user=False)

        state.transition_to(DisplayMode.LISTENING)

        assert state.mode == DisplayMode.LISTENING
        assert state.user_message is None
        assert state.tars_message is None
