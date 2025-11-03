"""
Display state management for UI E-Ink Display service.

Defines display modes and state machine logic for transitioning between modes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class DisplayMode(str, Enum):
    """Display modes for the e-ink display."""

    STANDBY = "standby"  # Waiting for wake word, showing standby screen
    LISTENING = "listening"  # Wake word detected, capturing audio
    PROCESSING = "processing"  # Showing user message, waiting for LLM response
    CONVERSATION = "conversation"  # Showing user + TARS messages
    ERROR = "error"  # Display error state


@dataclass
class MessageBubble:
    """Represents a message bubble for display."""

    text: str
    is_user: bool  # True for user (right-aligned), False for TARS (left-aligned)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    wrapped_lines: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize wrapped lines if not provided."""
        if not self.wrapped_lines:
            self.wrapped_lines = [self.text]


@dataclass
class DisplayState:
    """
    Current state of the display.

    Manages transitions between display modes and tracks message history.
    """

    mode: DisplayMode = DisplayMode.STANDBY
    last_update: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    # Message tracking
    user_message: Optional[MessageBubble] = None
    tars_message: Optional[MessageBubble] = None
    
    # Error tracking
    error_message: Optional[str] = None
    error_timestamp: Optional[datetime] = None

    def transition_to(
        self,
        new_mode: DisplayMode,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Transition to a new display mode.

        Args:
            new_mode: Target display mode
            error_message: Optional error message if transitioning to ERROR mode

        Raises:
            ValueError: If transition is invalid
        """
        now = datetime.utcnow()
        
        # Validate transition
        if not self._is_valid_transition(self.mode, new_mode):
            raise ValueError(
                f"Invalid transition from {self.mode} to {new_mode}"
            )

        # Handle mode-specific transitions
        if new_mode == DisplayMode.ERROR:
            self.error_message = error_message
            self.error_timestamp = now
        elif new_mode == DisplayMode.STANDBY:
            # Clear messages when returning to standby
            self.user_message = None
            self.tars_message = None
            self.error_message = None
            self.error_timestamp = None
        elif new_mode == DisplayMode.LISTENING:
            # Clear previous messages when starting new interaction
            self.user_message = None
            self.tars_message = None

        self.mode = new_mode
        self.last_update = now
        self.last_activity = now

    def set_user_message(self, text: str) -> None:
        """
        Set the user message and transition to PROCESSING mode.

        Args:
            text: User's transcribed message
        """
        self.user_message = MessageBubble(text=text, is_user=True)
        self.transition_to(DisplayMode.PROCESSING)

    def set_tars_message(self, text: str) -> None:
        """
        Set TARS message and transition to CONVERSATION mode.

        Args:
            text: TARS response message
        """
        self.tars_message = MessageBubble(text=text, is_user=False)
        self.transition_to(DisplayMode.CONVERSATION)

    def should_timeout(self, timeout_sec: int) -> bool:
        """
        Check if display should timeout to standby mode.

        Args:
            timeout_sec: Timeout duration in seconds

        Returns:
            bool: True if timeout duration has elapsed since last activity
        """
        if self.mode == DisplayMode.STANDBY:
            return False
        
        if self.mode == DisplayMode.ERROR:
            # Errors should timeout back to standby
            return (datetime.utcnow() - self.last_activity).total_seconds() > timeout_sec
        
        # Don't timeout while listening (active interaction)
        if self.mode == DisplayMode.LISTENING:
            return False
        
        # Timeout for PROCESSING and CONVERSATION modes
        elapsed = (datetime.utcnow() - self.last_activity).total_seconds()
        return elapsed > timeout_sec

    def handle_timeout(self) -> None:
        """Handle timeout by transitioning to STANDBY mode."""
        if self.mode != DisplayMode.STANDBY:
            self.transition_to(DisplayMode.STANDBY)

    @staticmethod
    def _is_valid_transition(
        from_mode: DisplayMode,
        to_mode: DisplayMode,
    ) -> bool:
        """
        Validate if a mode transition is allowed.

        Valid transitions:
        - STANDBY -> LISTENING (wake word detected)
        - LISTENING -> PROCESSING (STT final received)
        - LISTENING -> STANDBY (timeout or cancel)
        - PROCESSING -> CONVERSATION (LLM response received)
        - PROCESSING -> STANDBY (timeout)
        - CONVERSATION -> STANDBY (timeout)
        - CONVERSATION -> LISTENING (new wake word)
        - Any mode -> ERROR (error occurred)
        - ERROR -> STANDBY (recovery)

        Args:
            from_mode: Current display mode
            to_mode: Target display mode

        Returns:
            bool: True if transition is valid
        """
        # Can always transition to same mode
        if from_mode == to_mode:
            return True

        # Can always transition to ERROR from any state
        if to_mode == DisplayMode.ERROR:
            return True

        # Can always return to STANDBY (recovery/timeout)
        if to_mode == DisplayMode.STANDBY:
            return True

        # Define valid forward transitions
        valid_transitions = {
            DisplayMode.STANDBY: {DisplayMode.LISTENING},
            DisplayMode.LISTENING: {DisplayMode.PROCESSING},
            DisplayMode.PROCESSING: {DisplayMode.CONVERSATION},
            DisplayMode.CONVERSATION: {DisplayMode.LISTENING},
        }

        allowed = valid_transitions.get(from_mode, set())
        return to_mode in allowed

    def get_status_summary(self) -> str:
        """
        Get a human-readable status summary.

        Returns:
            str: Status summary for logging/debugging
        """
        elapsed = (datetime.utcnow() - self.last_activity).total_seconds()
        
        summary = f"Mode: {self.mode.value}, Elapsed: {elapsed:.1f}s"
        
        if self.mode == DisplayMode.ERROR and self.error_message:
            summary += f", Error: {self.error_message}"
        elif self.mode in (DisplayMode.PROCESSING, DisplayMode.CONVERSATION):
            msg_count = sum([
                1 for msg in [self.user_message, self.tars_message]
                if msg is not None
            ])
            summary += f", Messages: {msg_count}"
        
        return summary
