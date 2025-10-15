"""Router service for TARS voice assistant.

The router is the central message orchestration service that:
- Routes STT transcripts to LLM worker
- Streams LLM responses to TTS worker
- Manages wake word mode transitions
- Tracks service health
- Implements routing rules and policies
"""

__version__ = "0.1.0"
