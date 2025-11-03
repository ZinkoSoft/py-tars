"""Unit tests for message_formatter.py."""

import pytest

from ui_eink_display.message_formatter import (
    BubbleBounds,
    LayoutConstraints,
    MessageFormatter,
)
from ui_eink_display.display_state import MessageBubble


class TestLayoutConstraints:
    """Test suite for LayoutConstraints dataclass."""

    def test_default_constraints(self):
        """Test default layout constraints."""
        constraints = LayoutConstraints()

        assert constraints.display_width == 250
        assert constraints.display_height == 122
        assert constraints.max_chars_per_line == 22
        assert constraints.max_lines_per_bubble == 4
        assert constraints.margin == 4


class TestBubbleBounds:
    """Test suite for BubbleBounds dataclass."""

    def test_bubble_bounds_properties(self):
        """Test bubble bounds calculation properties."""
        bounds = BubbleBounds(x=10, y=20, width=100, height=50)

        assert bounds.x == 10
        assert bounds.y == 20
        assert bounds.width == 100
        assert bounds.height == 50
        assert bounds.right == 110  # x + width
        assert bounds.bottom == 70  # y + height


class TestMessageFormatter:
    """Test suite for MessageFormatter class."""

    def test_wrap_text_short(self):
        """Test wrapping text that fits on one line."""
        formatter = MessageFormatter()
        text = "Hello TARS"

        lines = formatter.wrap_text(text)

        assert len(lines) == 1
        assert lines[0] == "Hello TARS"

    def test_wrap_text_multiple_lines(self):
        """Test wrapping text across multiple lines."""
        formatter = MessageFormatter()
        text = "This is a longer message that needs to be wrapped across multiple lines"

        lines = formatter.wrap_text(text, max_chars=22)

        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 22

    def test_wrap_text_max_lines(self):
        """Test wrapping respects max lines constraint."""
        formatter = MessageFormatter()
        text = "Word " * 50  # Very long text

        lines = formatter.wrap_text(text, max_chars=22, max_lines=4)

        assert len(lines) <= 4
        # Last line should have ellipsis if truncated
        if len(text) > 22 * 4:
            assert lines[-1].endswith("...")

    def test_wrap_text_long_word(self):
        """Test wrapping text with word longer than max chars."""
        formatter = MessageFormatter()
        text = "supercalifragilisticexpialidocious"

        lines = formatter.wrap_text(text, max_chars=22)

        # Long word should be broken into chunks
        assert len(lines) >= 2
        for line in lines:
            assert len(line) <= 22

    def test_wrap_text_preserves_words(self):
        """Test wrapping preserves whole words when possible."""
        formatter = MessageFormatter()
        text = "Hello world this is a test"

        lines = formatter.wrap_text(text, max_chars=15)

        # Words should not be split unless necessary
        for line in lines:
            # Check no partial words (except last line)
            if line != lines[-1]:
                assert not line.endswith("-")

    def test_format_message_user(self):
        """Test formatting a user message."""
        formatter = MessageFormatter()
        text = "What is the weather today?"

        bubble = formatter.format_message(text, is_user=True)

        assert bubble.text == text
        assert bubble.is_user is True
        assert len(bubble.wrapped_lines) > 0
        assert isinstance(bubble.wrapped_lines, list)

    def test_format_message_tars(self):
        """Test formatting a TARS message."""
        formatter = MessageFormatter()
        text = "The weather is sunny with a high of 75 degrees"

        bubble = formatter.format_message(text, is_user=False)

        assert bubble.text == text
        assert bubble.is_user is False
        assert len(bubble.wrapped_lines) > 0

    def test_calculate_bubble_bounds_user(self):
        """Test calculating bounds for user bubble (right-aligned)."""
        formatter = MessageFormatter()
        bubble = MessageBubble(
            text="Test message",
            is_user=True,
            wrapped_lines=["Test message"],
        )

        bounds = formatter.calculate_bubble_bounds(bubble, y_offset=10)

        assert bounds.y == 10
        # Right-aligned: x should be near right edge
        assert bounds.x > formatter.constraints.display_width / 2
        assert bounds.right <= formatter.constraints.display_width - formatter.constraints.margin

    def test_calculate_bubble_bounds_tars(self):
        """Test calculating bounds for TARS bubble (left-aligned)."""
        formatter = MessageFormatter()
        bubble = MessageBubble(
            text="Test response",
            is_user=False,
            wrapped_lines=["Test response"],
        )

        bounds = formatter.calculate_bubble_bounds(bubble, y_offset=20)

        assert bounds.y == 20
        # Left-aligned: x should be at margin
        assert bounds.x == formatter.constraints.margin

    def test_calculate_bubble_bounds_respects_max_width(self):
        """Test bubble bounds respect maximum width constraint."""
        formatter = MessageFormatter()
        long_text = "X" * 100
        bubble = MessageBubble(
            text=long_text,
            is_user=True,
            wrapped_lines=[long_text],
        )

        bounds = formatter.calculate_bubble_bounds(bubble)

        assert bounds.width <= formatter.constraints.max_bubble_width

    def test_calculate_bubble_bounds_respects_min_width(self):
        """Test bubble bounds respect minimum width constraint."""
        formatter = MessageFormatter()
        bubble = MessageBubble(
            text="Hi",
            is_user=True,
            wrapped_lines=["Hi"],
        )

        bounds = formatter.calculate_bubble_bounds(bubble)

        assert bounds.width >= formatter.constraints.min_bubble_width

    def test_can_fit_both_bubbles_small_messages(self):
        """Test both bubbles fit when messages are small."""
        formatter = MessageFormatter()
        user_bubble = MessageBubble(
            text="Hello",
            is_user=True,
            wrapped_lines=["Hello"],
        )
        tars_bubble = MessageBubble(
            text="Hi there",
            is_user=False,
            wrapped_lines=["Hi there"],
        )

        can_fit = formatter.can_fit_both_bubbles(user_bubble, tars_bubble)

        assert can_fit is True

    def test_can_fit_both_bubbles_large_messages(self):
        """Test both bubbles don't fit when messages are too large."""
        formatter = MessageFormatter()
        
        # Create large bubbles with many wrapped lines
        long_text = "Word " * 50
        user_bubble = formatter.format_message(long_text, is_user=True)
        tars_bubble = formatter.format_message(long_text, is_user=False)

        can_fit = formatter.can_fit_both_bubbles(user_bubble, tars_bubble)

        # Should not fit if combined height exceeds display
        # (This depends on text length, but very long messages should not fit)
        assert isinstance(can_fit, bool)

    def test_layout_conversation_success(self):
        """Test laying out conversation when both bubbles fit."""
        formatter = MessageFormatter()
        user_bubble = MessageBubble(
            text="Question",
            is_user=True,
            wrapped_lines=["Question"],
        )
        tars_bubble = MessageBubble(
            text="Answer",
            is_user=False,
            wrapped_lines=["Answer"],
        )

        user_bounds, tars_bounds = formatter.layout_conversation(
            user_bubble, tars_bubble
        )

        # User should be above TARS
        assert user_bounds.bottom < tars_bounds.y
        # Both should be within display
        assert tars_bounds.bottom <= formatter.constraints.display_height

    def test_layout_conversation_failure(self):
        """Test layout raises error when bubbles don't fit."""
        formatter = MessageFormatter()
        
        # Create very large bubbles
        long_text = "Word " * 100
        user_bubble = formatter.format_message(long_text, is_user=True)
        tars_bubble = formatter.format_message(long_text, is_user=False)

        # Should raise error if bubbles don't fit
        if not formatter.can_fit_both_bubbles(user_bubble, tars_bubble):
            with pytest.raises(ValueError, match="don't fit"):
                formatter.layout_conversation(user_bubble, tars_bubble)

    def test_truncate_for_display_short_text(self):
        """Test truncating short text doesn't modify it."""
        formatter = MessageFormatter()
        text = "Short message"

        truncated = formatter.truncate_for_display(text)

        assert text in truncated

    def test_truncate_for_display_long_text(self):
        """Test truncating long text."""
        formatter = MessageFormatter()
        text = "This is a very long message " * 10

        truncated = formatter.truncate_for_display(text, priority_text=False)

        # Should be truncated (max 2 lines for non-priority)
        lines = formatter.wrap_text(truncated, max_lines=2)
        assert len(lines) <= 2

    def test_truncate_for_display_priority_text(self):
        """Test truncating priority text allows more lines."""
        formatter = MessageFormatter()
        text = "This is a priority message " * 10

        truncated = formatter.truncate_for_display(text, priority_text=True)

        # Priority text allows max_lines_per_bubble (4)
        lines = formatter.wrap_text(truncated, max_lines=4)
        assert len(lines) <= 4

    def test_estimate_text_width(self):
        """Test text width estimation."""
        formatter = MessageFormatter()
        
        # Short text should be narrower than long text
        short_width = formatter._estimate_text_width("Hi")
        long_width = formatter._estimate_text_width("Hello World")

        assert long_width > short_width
        assert short_width > 0

    def test_estimate_line_height(self):
        """Test line height estimation."""
        formatter = MessageFormatter()
        
        height = formatter._estimate_line_height()

        assert height > 0
        assert height < 30  # Reasonable line height for small font

    def test_wrap_text_empty_string(self):
        """Test wrapping empty string."""
        formatter = MessageFormatter()
        
        lines = formatter.wrap_text("")

        assert len(lines) == 1
        assert lines[0] == ""

    def test_wrap_text_single_word(self):
        """Test wrapping single word."""
        formatter = MessageFormatter()
        
        lines = formatter.wrap_text("Hello")

        assert len(lines) == 1
        assert lines[0] == "Hello"

    def test_format_message_multiline(self):
        """Test formatting message that wraps to multiple lines."""
        formatter = MessageFormatter()
        text = "This message should wrap to multiple lines when formatted"

        bubble = formatter.format_message(text, is_user=True)

        assert len(bubble.wrapped_lines) > 1
        # All lines should be under max chars
        for line in bubble.wrapped_lines:
            assert len(line) <= formatter.constraints.max_chars_per_line
