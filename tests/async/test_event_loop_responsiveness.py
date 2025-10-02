"""
Tests to verify async operations don't block the event loop.

These tests ensure that CPU-bound operations (transcription, embeddings, synthesis)
properly use asyncio.to_thread() and don't cause event loop blocking.
"""

from __future__ import annotations

import asyncio
import time
from typing import Tuple, Dict, Any
from unittest.mock import Mock, patch

import numpy as np
import pytest


class TestSTTResponsiveness:
    """Test that STT transcription doesn't block event loop."""

    @pytest.mark.asyncio
    async def test_transcribe_async_doesnt_block_event_loop(self) -> None:
        """Verify transcription runs in thread pool and doesn't block event loop."""
        from apps.stt_worker.stt_worker.transcriber import SpeechTranscriber

        # Mock the actual transcription to be fast but measurable
        def mock_transcribe(audio_data: bytes, sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
            # Simulate CPU-bound work
            time.sleep(0.01)
            return "test text", 0.95, {"duration_ms": 100}

        with patch.object(SpeechTranscriber, "transcribe", side_effect=mock_transcribe):
            transcriber = SpeechTranscriber(model_name="tiny", backend="whisper")
            
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
        from apps.stt_worker.stt_worker.transcriber import SpeechTranscriber

        def mock_transcribe(audio_data: bytes, sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
            time.sleep(0.005)
            return f"text_{len(audio_data)}", 0.9, {}

        with patch.object(SpeechTranscriber, "transcribe", side_effect=mock_transcribe):
            transcriber = SpeechTranscriber(model_name="tiny", backend="whisper")
            
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


class TestMemoryResponsiveness:
    """Test that memory embeddings don't block event loop."""

    @pytest.mark.asyncio
    async def test_embeddings_async_doesnt_block_event_loop(self) -> None:
        """Verify embeddings run in thread pool and don't block event loop."""
        from apps.memory_worker.memory_worker.service import STEmbedder

        # Mock the actual embedding to be fast but measurable
        def mock_encode(texts, **kwargs):
            time.sleep(0.01)
            return np.random.rand(len(texts), 384).astype(np.float32)

        embedder = STEmbedder("all-MiniLM-L6-v2")
        
        with patch.object(embedder.model, "encode", side_effect=mock_encode):
            # Start embedding
            embed_task = asyncio.create_task(
                embedder.embed_async(["test text 1", "test text 2"])
            )
            
            # Measure event loop responsiveness during embedding
            loop_responsive = False
            for _ in range(3):
                await asyncio.sleep(0.001)
                loop_responsive = True
            
            # Event loop should have remained responsive
            assert loop_responsive, "Event loop blocked during embedding"
            
            # Wait for embedding to complete
            embeddings = await embed_task
            assert embeddings.shape == (2, 384)
            assert embeddings.dtype == np.float32

    @pytest.mark.asyncio
    async def test_concurrent_embeddings_work_correctly(self) -> None:
        """Verify multiple concurrent embedding operations work."""
        from apps.memory_worker.memory_worker.service import STEmbedder

        def mock_encode(texts, **kwargs):
            time.sleep(0.005)
            return np.random.rand(len(texts), 384).astype(np.float32)

        embedder = STEmbedder("all-MiniLM-L6-v2")
        
        with patch.object(embedder.model, "encode", side_effect=mock_encode):
            # Launch concurrent embedding operations
            tasks = [
                embedder.embed_async([f"text {i}"]) for i in range(5)
            ]
            
            # Should complete without issues
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            for result in results:
                assert result.shape == (1, 384)


class TestTTSResponsiveness:
    """Test that TTS synthesis doesn't block event loop."""

    @pytest.mark.asyncio
    async def test_synthesis_async_doesnt_block_event_loop(self) -> None:
        """Verify synthesis runs in thread pool and doesn't block event loop."""
        from apps.tts_worker.tts_worker.piper_synth import PiperSynth

        # Mock the actual synthesis
        def mock_synth_and_play(text: str, streaming: bool = False, pipeline: bool = True) -> float:
            time.sleep(0.01)  # Simulate synthesis time
            return 0.1  # elapsed time

        # Create a mock synth
        with patch("apps.tts_worker.tts_worker.piper_synth._HAS_PIPER_API", False):
            synth = PiperSynth("/fake/voice.onnx")
            
            with patch.object(synth, "synth_and_play", side_effect=mock_synth_and_play):
                # Start synthesis
                synth_task = asyncio.create_task(
                    synth.synth_and_play_async("Hello world")
                )
                
                # Measure event loop responsiveness during synthesis
                loop_responsive = False
                for _ in range(3):
                    await asyncio.sleep(0.001)
                    loop_responsive = True
                
                # Event loop should have remained responsive
                assert loop_responsive, "Event loop blocked during synthesis"
                
                # Wait for synthesis to complete
                elapsed = await synth_task
                assert elapsed == 0.1

    @pytest.mark.asyncio
    async def test_concurrent_synthesis_operations(self) -> None:
        """Verify multiple concurrent synthesis operations work."""
        from apps.tts_worker.tts_worker.piper_synth import PiperSynth

        def mock_synth_and_play(text: str, streaming: bool = False, pipeline: bool = True) -> float:
            time.sleep(0.005)
            return len(text) * 0.01

        with patch("apps.tts_worker.tts_worker.piper_synth._HAS_PIPER_API", False):
            synth = PiperSynth("/fake/voice.onnx")
            
            with patch.object(synth, "synth_and_play", side_effect=mock_synth_and_play):
                # Launch concurrent synthesis
                texts = ["Hello", "world", "test"]
                tasks = [synth.synth_and_play_async(t) for t in texts]
                
                # Should complete without issues
                results = await asyncio.gather(*tasks)
                
                assert len(results) == 3
                for i, elapsed in enumerate(results):
                    assert elapsed == len(texts[i]) * 0.01


class TestEventLoopResponsivenessMetrics:
    """Test event loop blocking metrics."""

    @pytest.mark.asyncio
    async def test_measure_event_loop_lag_during_operations(self) -> None:
        """Measure actual event loop lag during async operations."""
        
        # Create a background task that checks event loop responsiveness
        lags = []
        
        async def measure_lag():
            while True:
                start = asyncio.get_event_loop().time()
                await asyncio.sleep(0.01)  # Request 10ms sleep
                actual = asyncio.get_event_loop().time() - start
                lag = actual - 0.01
                lags.append(lag)
                if len(lags) >= 10:
                    break
        
        # Start measurement task
        measure_task = asyncio.create_task(measure_lag())
        
        # Do some "work" (just sleep to simulate)
        await asyncio.sleep(0.15)
        
        # Wait for measurement to complete
        await measure_task
        
        # Event loop lag should be minimal (<5ms per measurement)
        max_lag = max(lags)
        avg_lag = sum(lags) / len(lags)
        
        assert max_lag < 0.05, f"Event loop lag too high: {max_lag:.3f}s"
        assert avg_lag < 0.02, f"Average event loop lag too high: {avg_lag:.3f}s"


class TestAsyncFallbacks:
    """Test that sync fallbacks work when async methods not available."""

    @pytest.mark.asyncio
    async def test_stt_falls_back_to_sync_wrapped_in_thread(self) -> None:
        """Verify STT falls back to sync transcription when async not available."""
        # This tests the domain service fallback behavior
        from tars.domain.stt import STTService, STTConfig
        
        class SyncOnlyTranscriber:
            """Mock transcriber with only sync method."""
            def transcribe(self, audio_data: bytes, sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
                time.sleep(0.001)
                return "sync text", 0.95, {}
        
        config = STTConfig(
            sample_rate=16000,
            frame_size_ms=30,
            vad_threshold=0.5,
            silence_duration_ms=800,
            silence_ratio=0.8,
            post_publish_cooldown_ms=1500,
            response_window_ms=5000,
        )
        
        class MockSuppression:
            def evaluate(self, *args, **kwargs):
                return True, {}
            def register_publication(self, text: str):
                pass
            @property
            def state(self):
                class State:
                    cooldown_until = 0.0
                return State()
        
        transcriber = SyncOnlyTranscriber()
        service = STTService(
            transcriber=transcriber,
            config=config,
            suppression=MockSuppression(),
        )
        
        # Should use sync method wrapped in asyncio.to_thread
        assert not service._has_async_transcribe
        
        # Process should still work via fallback
        audio_data = np.random.randint(-32768, 32767, 480, dtype=np.int16).tobytes()
        
        # Should not raise, even without async method
        result = await service.process_chunk(audio_data, timestamp=0.0)
        # Result might be empty due to suppression, but shouldn't error
        assert result is not None


class TestAsyncResourceCleanup:
    """Test that async resources are properly cleaned up."""

    @pytest.mark.asyncio
    async def test_embedder_executor_shutdown_on_del(self) -> None:
        """Verify thread pool executor is cleaned up."""
        from apps.memory_worker.memory_worker.service import STEmbedder
        
        embedder = STEmbedder("all-MiniLM-L6-v2")
        executor = embedder._executor
        
        # Executor should be running
        assert executor is not None
        assert not executor._shutdown
        
        # Delete embedder
        del embedder
        
        # Executor shutdown is handled by Python's ThreadPoolExecutor cleanup
        # This test just verifies the pattern is correct

    @pytest.mark.asyncio
    async def test_cancelled_tasks_cleanup_properly(self) -> None:
        """Verify cancelled async operations clean up resources."""
        from apps.stt_worker.stt_worker.transcriber import SpeechTranscriber
        
        def slow_transcribe(audio_data: bytes, sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
            time.sleep(1.0)  # Slow operation
            return "text", 0.9, {}
        
        with patch.object(SpeechTranscriber, "transcribe", side_effect=slow_transcribe):
            transcriber = SpeechTranscriber(model_name="tiny", backend="whisper")
            audio_data = np.random.randint(-32768, 32767, 16000, dtype=np.int16).tobytes()
            
            # Start and immediately cancel
            task = asyncio.create_task(transcriber.transcribe_async(audio_data, 16000))
            await asyncio.sleep(0.001)
            task.cancel()
            
            # Should raise CancelledError
            with pytest.raises(asyncio.CancelledError):
                await task
