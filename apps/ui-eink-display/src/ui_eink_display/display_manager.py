"""
Display manager for UI E-Ink Display service.

Handles e-ink display hardware control, rendering, and mock display support.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .display_state import DisplayMode, DisplayState, MessageBubble

logger = logging.getLogger(__name__)


class MockDisplay:
    """Mock e-ink display for testing without hardware."""

    width = 250
    height = 122

    def init(self) -> None:
        """Initialize mock display."""
        logger.info("MockDisplay: Initialized (250x122)")

    def Clear(self) -> None:
        """Clear mock display."""
        logger.info("MockDisplay: Cleared")

    def display(self, image: Image.Image) -> None:
        """Display image on mock display."""
        logger.info(f"MockDisplay: Displaying {image.size} image")

    def sleep(self) -> None:
        """Put mock display to sleep."""
        logger.info("MockDisplay: Sleep mode")


class DisplayManager:
    """
    Manages e-ink display hardware and rendering.

    Handles initialization, rendering for each display mode, and graceful
    shutdown. Supports both real waveshare-epd hardware and mock display
    for testing.
    """

    # Display dimensions (landscape orientation)
    WIDTH = 250
    HEIGHT = 122

    # Layout constants
    MARGIN = 4
    FONT_SIZE_LARGE = 16
    FONT_SIZE_MEDIUM = 12
    FONT_SIZE_SMALL = 10

    def __init__(
        self,
        mock: bool = False,
        font_path: Path = Path("/usr/share/fonts/truetype/dejavu"),
    ):
        """
        Initialize display manager.

        Args:
            mock: If True, use mock display instead of hardware
            font_path: Path to font files directory
        """
        self.mock = mock
        self.font_path = font_path
        self.display: Optional[object] = None
        self._initialized = False

        # Load fonts
        try:
            font_file = font_path / "DejaVuSans.ttf"
            self.font_large = ImageFont.truetype(str(font_file), self.FONT_SIZE_LARGE)
            self.font_medium = ImageFont.truetype(str(font_file), self.FONT_SIZE_MEDIUM)
            self.font_small = ImageFont.truetype(str(font_file), self.FONT_SIZE_SMALL)
            logger.info(f"Loaded fonts from {font_path}")
        except Exception as e:
            logger.warning(f"Failed to load fonts: {e}, using default font")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    async def initialize(self) -> None:
        """
        Initialize the display hardware.

        Must be called before rendering. Uses asyncio.to_thread to avoid
        blocking the event loop.
        """
        if self._initialized:
            logger.warning("Display already initialized")
            return

        try:
            if self.mock:
                self.display = MockDisplay()
            else:
                # Import waveshare library with our custom epdconfig.py
                # The epdconfig.py uses libgpiod + spidev for Radxa Zero 3W
                try:
                    from waveshare_epd import epd2in13_V4
                    self.display = epd2in13_V4.EPD()
                    logger.info("Successfully initialized waveshare e-ink display")
                    
                except Exception as import_error:
                    logger.warning(f"Failed to import waveshare_epd: {import_error}")
                    logger.info("Falling back to mock display mode")
                    self.display = MockDisplay()
                    self.mock = True

            # Initialize in thread to avoid blocking
            await asyncio.to_thread(self._init_hardware)
            self._initialized = True
            
            if self.mock:
                logger.info("Display initialized successfully (MOCK MODE)")
            else:
                logger.info("Display initialized successfully (HARDWARE MODE)")

        except Exception as e:
            logger.error(f"Failed to initialize display: {e}")
            raise

    def _init_hardware(self) -> None:
        """Initialize hardware (blocking operation)."""
        if self.display:
            self.display.init()
            self.display.Clear()

    async def render(self, state: DisplayState) -> None:
        """
        Render the current display state.

        Args:
            state: Current display state to render
        """
        if not self._initialized:
            raise RuntimeError("Display not initialized")

        try:
            logger.info(f"Rendering display mode: {state.mode.value}")
            
            # Create image based on current mode
            if state.mode == DisplayMode.STANDBY:
                image = self._render_standby()
            elif state.mode == DisplayMode.LISTENING:
                image = self._render_listening()
            elif state.mode == DisplayMode.PROCESSING:
                image = self._render_processing(state)
            elif state.mode == DisplayMode.CONVERSATION:
                image = self._render_conversation(state)
            elif state.mode == DisplayMode.ERROR:
                image = self._render_error(state)
            else:
                logger.error(f"Unknown display mode: {state.mode}")
                image = self._render_error_generic()

            # Display image (blocking operation, run in thread)
            await asyncio.to_thread(self._display_image, image)
            logger.info(f"✅ Displayed {state.mode.value} mode successfully")

        except Exception as e:
            logger.error(f"Failed to render display: {e}")
            raise

    def _display_image(self, image):
        if not self.display:
            return

        # Ensure 1-bit and correct canvas size relative to the driver
        w = getattr(self.display, "width", self.WIDTH)
        h = getattr(self.display, "height", self.HEIGHT)

        # If your renderer produced 250x122 but the driver is 122x250, rotate 90°/270° or 180°.
        # Most 2.13 V4s need 180° for HAT wiring; try that first:
        img = image.convert("1")
        if (img.size != (w, h)):
            # If driver is portrait and our image is landscape, rotate
            if img.size == (self.WIDTH, self.HEIGHT) and (w, h) == (self.HEIGHT, self.WIDTH):
                img = img.rotate(90, expand=True)
            # Final orientation tweak many boards want:
            img = img.rotate(180, expand=False)

        if hasattr(self.display, "getbuffer"):
            buf = self.display.getbuffer(img)
        else:
            # Fallback packer (1-bit, MSB-first per row)
            buf = img.tobytes()

        self.display.display(buf)



    def _render_standby(self) -> Image.Image:
        """
        Render standby mode screen.

        Shows sci-fi inspired interface indicating system is ready.
        """
        image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)  # White background
        draw = ImageDraw.Draw(image)

        # Title
        title = "TARS REMOTE INTERFACE"
        bbox = draw.textbbox((0, 0), title, font=self.font_medium)
        title_width = bbox[2] - bbox[0]
        x = (self.WIDTH - title_width) // 2
        draw.text((x, 20), title, font=self.font_medium, fill=0)

        # Status
        status = "AWAITING SIGNAL"
        bbox = draw.textbbox((0, 0), status, font=self.font_large)
        status_width = bbox[2] - bbox[0]
        x = (self.WIDTH - status_width) // 2
        draw.text((x, 50), status, font=self.font_large, fill=0)

        # Decorative lines
        draw.line([(20, 80), (230, 80)], fill=0, width=1)
        draw.line([(20, 82), (230, 82)], fill=0, width=1)

        # Status indicator
        indicator = "[ READY ]"
        bbox = draw.textbbox((0, 0), indicator, font=self.font_small)
        ind_width = bbox[2] - bbox[0]
        x = (self.WIDTH - ind_width) // 2
        draw.text((x, 95), indicator, font=self.font_small, fill=0)

        return image

    def _render_listening(self) -> Image.Image:
        """
        Render listening mode screen.

        Shows listening indicator when wake word detected.
        """
        image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)

        # Listening indicator
        text = "● LISTENING ●"
        bbox = draw.textbbox((0, 0), text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        x = (self.WIDTH - text_width) // 2
        y = (self.HEIGHT - (bbox[3] - bbox[1])) // 2
        draw.text((x, y), text, font=self.font_large, fill=0)

        # Pulse circles (decorative)
        center_x = self.WIDTH // 2
        center_y = self.HEIGHT // 2
        for radius in [40, 50, 60]:
            draw.ellipse(
                [
                    (center_x - radius, center_y - radius),
                    (center_x + radius, center_y + radius),
                ],
                outline=0,
                width=1,
            )

        return image

    def _render_processing(self, state: DisplayState) -> Image.Image:
        """
        Render processing mode screen.

        Shows user message in right-aligned bubble with transmitting indicator.
        """
        image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)

        if state.user_message:
            # User message bubble (right-aligned)
            self._draw_message_bubble(
                draw,
                state.user_message,
                is_user=True,
            )

            # Transmitting indicator
            indicator = "transmitting..."
            bbox = draw.textbbox((0, 0), indicator, font=self.font_small)
            ind_width = bbox[2] - bbox[0]
            x = self.WIDTH - ind_width - self.MARGIN
            y = self.HEIGHT - (bbox[3] - bbox[1]) - self.MARGIN
            draw.text((x, y), indicator, font=self.font_small, fill=0)

        return image

    def _render_conversation(self, state: DisplayState) -> Image.Image:
        """
        Render conversation mode screen.

        Shows both user and TARS messages. If both don't fit, shows only
        TARS response (priority rule).
        """
        image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)

        # Check if both messages fit
        user_height = 0
        tars_height = 0

        if state.user_message:
            user_height = self._estimate_message_height(state.user_message)
        if state.tars_message:
            tars_height = self._estimate_message_height(state.tars_message)

        total_height = user_height + tars_height + (self.MARGIN * 3)

        if total_height > self.HEIGHT:
            # Only show TARS response (priority rule)
            if state.tars_message:
                self._draw_message_bubble(
                    draw,
                    state.tars_message,
                    is_user=False,
                    y_offset=10,
                )
        else:
            # Show both messages
            current_y = self.MARGIN

            if state.user_message:
                self._draw_message_bubble(
                    draw,
                    state.user_message,
                    is_user=True,
                    y_offset=current_y,
                )
                current_y += user_height + self.MARGIN

            if state.tars_message:
                self._draw_message_bubble(
                    draw,
                    state.tars_message,
                    is_user=False,
                    y_offset=current_y,
                )

        return image

    def _render_error(self, state: DisplayState) -> Image.Image:
        """
        Render error mode screen.

        Shows error indicator and message.
        """
        image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)

        # Error header
        header = "⚠ ERROR ⚠"
        bbox = draw.textbbox((0, 0), header, font=self.font_large)
        header_width = bbox[2] - bbox[0]
        x = (self.WIDTH - header_width) // 2
        draw.text((x, 20), header, font=self.font_large, fill=0)

        # Error message (wrapped)
        if state.error_message:
            lines = self._wrap_text(state.error_message, 30)
            y = 50
            for line in lines[:3]:  # Max 3 lines
                bbox = draw.textbbox((0, 0), line, font=self.font_small)
                line_width = bbox[2] - bbox[0]
                x = (self.WIDTH - line_width) // 2
                draw.text((x, y), line, font=self.font_small, fill=0)
                y += bbox[3] - bbox[1] + 2

        return image

    def _render_error_generic(self) -> Image.Image:
        """Render generic error screen."""
        image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)

        text = "DISPLAY ERROR"
        bbox = draw.textbbox((0, 0), text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        x = (self.WIDTH - text_width) // 2
        y = (self.HEIGHT - (bbox[3] - bbox[1])) // 2
        draw.text((x, y), text, font=self.font_large, fill=0)

        return image

    def _draw_message_bubble(
        self,
        draw: ImageDraw.ImageDraw,
        message: MessageBubble,
        is_user: bool,
        y_offset: int = 0,
    ) -> None:
        """
        Draw a message bubble.

        Args:
            draw: PIL ImageDraw object
            message: Message bubble to draw
            is_user: True for right-aligned user bubble, False for left-aligned TARS
            y_offset: Vertical offset from top
        """
        # Wrap text (22 chars per line max)
        lines = self._wrap_text(message.text, 22)

        # Calculate bubble dimensions
        max_line_width = 0
        line_height = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=self.font_small)
            line_width = bbox[2] - bbox[0]
            line_height = max(line_height, bbox[3] - bbox[1])
            max_line_width = max(max_line_width, line_width)

        bubble_width = max_line_width + (self.MARGIN * 2)
        bubble_height = len(lines) * (line_height + 2) + (self.MARGIN * 2)

        # Position bubble
        if is_user:
            # Right-aligned
            bubble_x = self.WIDTH - bubble_width - self.MARGIN
        else:
            # Left-aligned
            bubble_x = self.MARGIN

        bubble_y = y_offset

        # Draw bubble background (rounded rectangle)
        draw.rectangle(
            [
                (bubble_x, bubble_y),
                (bubble_x + bubble_width, bubble_y + bubble_height),
            ],
            outline=0,
            width=1,
        )

        # Draw text
        text_y = bubble_y + self.MARGIN
        for line in lines:
            draw.text(
                (bubble_x + self.MARGIN, text_y),
                line,
                font=self.font_small,
                fill=0,
            )
            text_y += line_height + 2

    def _estimate_message_height(self, message: MessageBubble) -> int:
        """
        Estimate the height of a message bubble.

        Args:
            message: Message bubble

        Returns:
            int: Estimated height in pixels
        """
        lines = self._wrap_text(message.text, 22)
        line_height = 12  # Approximate
        return len(lines) * (line_height + 2) + (self.MARGIN * 2)

    def _wrap_text(self, text: str, max_chars: int) -> list[str]:
        """
        Wrap text to maximum character width.

        Args:
            text: Text to wrap
            max_chars: Maximum characters per line

        Returns:
            list[str]: Wrapped lines
        """
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            if len(test_line) <= max_chars:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    async def shutdown(self) -> None:
        """
        Shutdown display hardware gracefully.

        Clears display and puts it to sleep mode.
        """
        if not self._initialized:
            return

        try:
            logger.info("Shutting down display")
            await asyncio.to_thread(self._shutdown_hardware)
            self._initialized = False
        except Exception as e:
            logger.error(f"Error during display shutdown: {e}")

    def _shutdown_hardware(self) -> None:
        """Shutdown hardware (blocking operation)."""
        if self.display:
            try:
                self.display.Clear()
                self.display.sleep()
            except Exception as e:
                logger.error(f"Error clearing/sleeping display: {e}")
