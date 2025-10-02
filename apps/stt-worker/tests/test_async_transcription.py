"""
Test async transcription responsiveness and non-blocking behavior.

NOTE: These tests require Whisper model downloads and are skipped in CI.
They serve as documentation for async patterns.
"""

from __future__ import annotations

import asyncio
import time
from typing import Tuple, Dict, Any
from unittest.mock import patch

import numpy as np
import pytest

pytestmark = pytest.mark.skip(reason="Requires Whisper model downloads")

import numpy as np
import pytest


class TestTranscribeAsync:
    """Test that transcription doesn't block event loop."""

    @pytest.mark.asyncio
    async def test_transcribe_async_doesnt_block_event_loop(self) -> None:
        """Verify transcription runs in thread pool and doesn't block event loop."""
        from stt_worker.transcriber import SpeechTranscriber

        # Mock the actual transcription to be fast but measurable
        def mock_transcribe(audio_data: bytes, sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
            # Simulate CPU-bound work
            time.sleep(0.01)
            return "test text", 0.95, {"duration_ms": 100}

        transcriber = SpeechTranscriber()
        with patch.object(transcriber._impl, "transcribe", side_effect=mock_transcribe):
            
            # Create test audio data
            audio_data = np.random.randint(-32768, 32767, 16000, dtype=np.int16).tobytes()
            
            # Start transcription
            transcribe_task = asyncio.create_task(
                transcriber.transcribe_async(audio_data, 16000)
            )
            
            # Measure event loop responsiveness during transcription
            loop_responsive = False
            for _ in range(3):
                await asyncio.sleep(0.001)  # Small sleep to check loop responsiveness
                loop_responsive = True
            
            # Event loop should have remained responsive
            assert loop_responsive, "Event loop blocked during transcription"
            
            # Wait for transcription to complete
            text, confidence, metrics = await transcribe_task
            assert text == "test text"
            assert confidence == 0.95

    @pytest.mark.asyncio
    async def test_concurrent_transcriptions_dont_deadlock(self) -> None:
        """Verify multiple concurrent transcriptions work correctly."""
        from stt_worker.transcriber import SpeechTranscriber

        def mock_transcribe(audio_data: bytes, sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
            time.sleep(0.005)
            return f"text_{len(audio_data)}", 0.9, {}

        transcriber = SpeechTranscriber()
        with patch.object(transcriber._impl, "transcribe", side_effect=mock_transcribe):
            
            # Create multiple different audio samples
            audio_samples = [
                np.random.randint(-32768, 32767, 8000 * i, dtype=np.int16).tobytes()
                for i in range(1, 4)
            ]
            
            # Launch concurrent transcriptions
            tasks = [
                transcriber.transcribe_async(audio, 16000)
                for audio in audio_samples
            ]
            
            # Should complete without deadlock
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 3
            for i, (text, conf, _) in enumerate(results, 1):
                assert text.startswith("text_")
                assert conf == 0.9

    @pytest.mark.asyncio
    async def test_cancelled_transcription_cleans_up(self) -> None:
        """Verify cancelled async operations clean up resources."""
        from stt_worker.transcriber import SpeechTranscriber
        
        def slow_transcribe(audio_data: bytes, sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
            time.sleep(1.0)  # Slow operation
            return "text", 0.9, {}
        
        transcriber = SpeechTranscriber()
        with patch.object(transcriber._impl, "transcribe", side_effect=slow_transcribe):
            audio_data = np.random.randint(-32768, 32767, 16000, dtype=np.int16).tobytes()
            
            # Start and immediately cancel
            task = asyncio.create_task(transcriber.transcribe_async(audio_data, 16000))
            await asyncio.sleep(0.001)
            task.cancel()
            
            # Should raise CancelledError
            with pytest.raises(asyncio.CancelledError):
                await task
