"""Integration tests for display_manager.py."""

import pytest

from ui_eink_display.config import DisplayConfig
from ui_eink_display.display_manager import DisplayManager, MockDisplay
from ui_eink_display.display_state import DisplayMode, DisplayState, MessageBubble


@pytest.mark.asyncio
class TestDisplayManagerIntegration:
    """Integration tests for DisplayManager with mock display."""

    async def test_initialize_mock_display(self):
        """Test initializing display manager with mock display."""
        manager = DisplayManager(mock=True)

        await manager.initialize()

        assert manager._initialized is True
        assert isinstance(manager.display, MockDisplay)

    async def test_render_standby(self):
        """Test rendering standby mode."""
        manager = DisplayManager(mock=True)
        await manager.initialize()

        state = DisplayState(mode=DisplayMode.STANDBY)

        # Should not raise exception
        await manager.render(state)

    async def test_render_listening(self):
        """Test rendering listening mode."""
        manager = DisplayManager(mock=True)
        await manager.initialize()

        state = DisplayState(mode=DisplayMode.LISTENING)

        await manager.render(state)

    async def test_render_processing_with_user_message(self):
        """Test rendering processing mode with user message."""
        manager = DisplayManager(mock=True)
        await manager.initialize()

        state = DisplayState(mode=DisplayMode.PROCESSING)
        state.user_message = MessageBubble(
            text="What is the weather?",
            is_user=True,
        )

        await manager.render(state)

    async def test_render_conversation_both_messages(self):
        """Test rendering conversation mode with both messages."""
        manager = DisplayManager(mock=True)
        await manager.initialize()

        state = DisplayState(mode=DisplayMode.CONVERSATION)
        state.user_message = MessageBubble(
            text="What is the weather?",
            is_user=True,
        )
        state.tars_message = MessageBubble(
            text="The weather is sunny.",
            is_user=False,
        )

        await manager.render(state)

    async def test_render_error(self):
        """Test rendering error mode."""
        manager = DisplayManager(mock=True)
        await manager.initialize()

        state = DisplayState(mode=DisplayMode.ERROR)
        state.error_message = "Connection failed"

        await manager.render(state)

    async def test_render_before_initialize_raises(self):
        """Test rendering before initialization raises error."""
        manager = DisplayManager(mock=True)

        state = DisplayState(mode=DisplayMode.STANDBY)

        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.render(state)

    async def test_shutdown(self):
        """Test shutting down display manager."""
        manager = DisplayManager(mock=True)
        await manager.initialize()

        await manager.shutdown()

        assert manager._initialized is False

    async def test_shutdown_before_initialize(self):
        """Test shutdown before initialization doesn't error."""
        manager = DisplayManager(mock=True)

        # Should not raise
        await manager.shutdown()

    async def test_full_lifecycle(self):
        """Test full lifecycle: initialize -> render -> shutdown."""
        manager = DisplayManager(mock=True)

        # Initialize
        await manager.initialize()
        assert manager._initialized is True

        # Render standby
        state = DisplayState(mode=DisplayMode.STANDBY)
        await manager.render(state)

        # Transition to listening
        state.transition_to(DisplayMode.LISTENING)
        await manager.render(state)

        # Set user message
        state.set_user_message("Hello TARS")
        await manager.render(state)

        # Set TARS response
        state.set_tars_message("Hello human")
        await manager.render(state)

        # Shutdown
        await manager.shutdown()
        assert manager._initialized is False

    async def test_render_long_user_message(self):
        """Test rendering long user message that requires wrapping."""
        manager = DisplayManager(mock=True)
        await manager.initialize()

        long_message = "This is a very long message that will need to be wrapped across multiple lines to fit on the small e-ink display"

        state = DisplayState(mode=DisplayMode.PROCESSING)
        state.user_message = MessageBubble(
            text=long_message,
            is_user=True,
        )

        await manager.render(state)

    async def test_render_long_tars_message(self):
        """Test rendering long TARS message."""
        manager = DisplayManager(mock=True)
        await manager.initialize()

        long_message = "Here is a comprehensive answer that provides detailed information about your question and includes several points that need to be communicated"

        state = DisplayState(mode=DisplayMode.CONVERSATION)
        state.tars_message = MessageBubble(
            text=long_message,
            is_user=False,
        )

        await manager.render(state)

    async def test_wrap_text_preserves_words(self):
        """Test text wrapping preserves whole words."""
        manager = DisplayManager(mock=True)

        text = "Hello world this is a test"
        lines = manager._wrap_text(text, max_chars=15)

        # Check words aren't split
        for line in lines:
            assert len(line) <= 15
            # No partial words (heuristic: no ending with partial word)
            words = line.split()
            assert all(len(word) <= 15 for word in words)

    async def test_wrap_text_long_word(self):
        """Test wrapping handles word longer than max chars."""
        manager = DisplayManager(mock=True)

        text = "supercalifragilisticexpialidocious"
        lines = manager._wrap_text(text, max_chars=15)

        # Long word should be broken into chunks
        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 15

    async def test_estimate_message_height(self):
        """Test message height estimation."""
        manager = DisplayManager(mock=True)

        short_bubble = MessageBubble(text="Hi", is_user=True)
        long_bubble = MessageBubble(
            text="This is a much longer message that will wrap",
            is_user=True,
        )

        short_height = manager._estimate_message_height(short_bubble)
        long_height = manager._estimate_message_height(long_bubble)

        assert long_height > short_height
        assert short_height > 0


@pytest.mark.asyncio
class TestMockDisplay:
    """Tests for MockDisplay class."""

    def test_mock_display_initialization(self):
        """Test MockDisplay can be initialized."""
        display = MockDisplay()

        assert display.width == 250
        assert display.height == 122

    def test_mock_display_init(self):
        """Test MockDisplay init method."""
        display = MockDisplay()

        # Should not raise
        display.init()

    def test_mock_display_clear(self):
        """Test MockDisplay Clear method."""
        display = MockDisplay()

        # Should not raise
        display.Clear()

    def test_mock_display_display(self):
        """Test MockDisplay display method."""
        from PIL import Image

        display = MockDisplay()
        image = Image.new("1", (250, 122), 255)

        # Should not raise
        display.display(image)

    def test_mock_display_sleep(self):
        """Test MockDisplay sleep method."""
        display = MockDisplay()

        # Should not raise
        display.sleep()
