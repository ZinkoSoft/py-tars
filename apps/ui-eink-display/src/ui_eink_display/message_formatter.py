"""
Message formatting utilities for UI E-Ink Display service.

Handles text wrapping, bubble layout calculations, and constraint validation.
"""

from dataclasses import dataclass
from typing import List, Tuple

from PIL import ImageFont

from .display_state import MessageBubble


@dataclass
class LayoutConstraints:
    """Display layout constraints for the 250x122 e-ink display."""

    # Display dimensions (landscape)
    display_width: int = 250
    display_height: int = 122

    # Font sizes
    font_size_large: int = 16
    font_size_medium: int = 12
    font_size_small: int = 10

    # Layout margins
    margin: int = 4
    bubble_padding: int = 4

    # Text wrapping
    max_chars_per_line: int = 22
    max_lines_per_bubble: int = 4

    # Bubble constraints
    max_bubble_width: int = 180  # Leave room for alignment
    min_bubble_width: int = 40


@dataclass
class BubbleBounds:
    """Bounding box for a message bubble."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """Right edge x-coordinate."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Bottom edge y-coordinate."""
        return self.y + self.height


class MessageFormatter:
    """
    Formats messages for display on e-ink screen.

    Handles text wrapping, bubble layout calculations, and ensures messages
    fit within display constraints.
    """

    def __init__(
        self,
        constraints: LayoutConstraints = LayoutConstraints(),
        font: ImageFont.ImageFont = None,
    ):
        """
        Initialize message formatter.

        Args:
            constraints: Layout constraints for the display
            font: PIL font to use for measurements (optional)
        """
        self.constraints = constraints
        self.font = font or ImageFont.load_default()

    def wrap_text(
        self,
        text: str,
        max_chars: int = None,
        max_lines: int = None,
    ) -> List[str]:
        """
        Wrap text to fit within character width constraint.

        Uses word wrapping to avoid breaking words when possible.

        Args:
            text: Text to wrap
            max_chars: Maximum characters per line (default: from constraints)
            max_lines: Maximum number of lines (default: from constraints)

        Returns:
            List[str]: Wrapped lines
        """
        max_chars = max_chars or self.constraints.max_chars_per_line
        max_lines = max_lines or self.constraints.max_lines_per_bubble

        words = text.split()
        lines = []
        current_line = []

        for word in words:
            # If word itself is too long, break it
            if len(word) > max_chars:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = []
                # Break long word into chunks
                for i in range(0, len(word), max_chars):
                    chunk = word[i : i + max_chars]
                    lines.append(chunk)
                continue

            # Try adding word to current line
            test_line = " ".join(current_line + [word])
            if len(test_line) <= max_chars:
                current_line.append(word)
            else:
                # Line would be too long, start new line
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

            # Check max lines constraint
            if len(lines) >= max_lines - 1 and current_line:
                # Truncate and add ellipsis
                remaining = " ".join(current_line)
                if len(remaining) > max_chars - 3:
                    remaining = remaining[: max_chars - 3] + "..."
                else:
                    remaining = remaining + "..."
                lines.append(remaining)
                current_line = []
                break

        # Add remaining words
        if current_line and len(lines) < max_lines:
            lines.append(" ".join(current_line))

        return lines[:max_lines]

    def format_message(
        self,
        text: str,
        is_user: bool,
    ) -> MessageBubble:
        """
        Format a message into a bubble with wrapped text.

        Args:
            text: Message text
            is_user: True for user message, False for TARS

        Returns:
            MessageBubble: Formatted message bubble with wrapped lines
        """
        wrapped_lines = self.wrap_text(text)

        return MessageBubble(
            text=text,
            is_user=is_user,
            wrapped_lines=wrapped_lines,
        )

    def calculate_bubble_bounds(
        self,
        bubble: MessageBubble,
        y_offset: int = 0,
    ) -> BubbleBounds:
        """
        Calculate the bounding box for a message bubble.

        Args:
            bubble: Message bubble to calculate bounds for
            y_offset: Vertical offset from top of display

        Returns:
            BubbleBounds: Calculated bounding box
        """
        # Calculate text dimensions
        line_height = self._estimate_line_height()
        text_height = len(bubble.wrapped_lines) * line_height

        # Calculate maximum line width
        max_line_width = 0
        for line in bubble.wrapped_lines:
            line_width = self._estimate_text_width(line)
            max_line_width = max(max_line_width, line_width)

        # Calculate bubble dimensions with padding
        bubble_width = min(
            max_line_width + (self.constraints.bubble_padding * 2),
            self.constraints.max_bubble_width,
        )
        bubble_width = max(bubble_width, self.constraints.min_bubble_width)

        bubble_height = text_height + (self.constraints.bubble_padding * 2)

        # Calculate x position based on alignment
        if bubble.is_user:
            # Right-aligned
            x = (
                self.constraints.display_width
                - bubble_width
                - self.constraints.margin
            )
        else:
            # Left-aligned
            x = self.constraints.margin

        return BubbleBounds(
            x=x,
            y=y_offset,
            width=bubble_width,
            height=bubble_height,
        )

    def can_fit_both_bubbles(
        self,
        user_bubble: MessageBubble,
        tars_bubble: MessageBubble,
    ) -> bool:
        """
        Check if both user and TARS bubbles can fit on screen simultaneously.

        Args:
            user_bubble: User message bubble
            tars_bubble: TARS message bubble

        Returns:
            bool: True if both bubbles fit within display height
        """
        user_bounds = self.calculate_bubble_bounds(
            user_bubble,
            y_offset=self.constraints.margin,
        )
        tars_bounds = self.calculate_bubble_bounds(
            tars_bubble,
            y_offset=user_bounds.bottom + self.constraints.margin,
        )

        total_height = tars_bounds.bottom + self.constraints.margin
        return total_height <= self.constraints.display_height

    def layout_conversation(
        self,
        user_bubble: MessageBubble,
        tars_bubble: MessageBubble,
    ) -> Tuple[BubbleBounds, BubbleBounds]:
        """
        Calculate layout for conversation mode (both bubbles).

        Args:
            user_bubble: User message bubble
            tars_bubble: TARS message bubble

        Returns:
            Tuple[BubbleBounds, BubbleBounds]: User and TARS bubble bounds

        Raises:
            ValueError: If bubbles don't fit (should show TARS only)
        """
        if not self.can_fit_both_bubbles(user_bubble, tars_bubble):
            raise ValueError("Both bubbles don't fit on screen")

        # Calculate user bubble at top
        user_bounds = self.calculate_bubble_bounds(
            user_bubble,
            y_offset=self.constraints.margin,
        )

        # Calculate TARS bubble below user bubble
        tars_bounds = self.calculate_bubble_bounds(
            tars_bubble,
            y_offset=user_bounds.bottom + self.constraints.margin,
        )

        return user_bounds, tars_bounds

    def _estimate_text_width(self, text: str) -> int:
        """
        Estimate text width in pixels.

        Args:
            text: Text to measure

        Returns:
            int: Estimated width in pixels
        """
        # Use PIL font if available
        try:
            bbox = self.font.getbbox(text)
            return bbox[2] - bbox[0]
        except Exception:
            # Fallback to character count estimation
            # Approximate 6 pixels per character for small font
            return len(text) * 6

    def _estimate_line_height(self) -> int:
        """
        Estimate line height in pixels.

        Returns:
            int: Estimated line height in pixels
        """
        # Use PIL font if available
        try:
            bbox = self.font.getbbox("Ay")  # Test with ascender/descender
            return (bbox[3] - bbox[1]) + 2  # Add spacing
        except Exception:
            # Fallback to fixed height for small font
            return 12

    def truncate_for_display(
        self,
        text: str,
        priority_text: bool = False,
    ) -> str:
        """
        Truncate text to fit display constraints.

        Args:
            text: Text to truncate
            priority_text: If True, allow more lines (for priority messages)

        Returns:
            str: Truncated text with ellipsis if needed
        """
        max_lines = (
            self.constraints.max_lines_per_bubble if priority_text else 2
        )
        lines = self.wrap_text(text, max_lines=max_lines)

        return " ".join(lines)
