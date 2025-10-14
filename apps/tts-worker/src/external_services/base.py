from __future__ import annotations

import abc


class TTSExternalService(abc.ABC):
    """Abstract base for external TTS providers.

    Providers should implement a blocking synth-and-play method (or return bytes)
    that the caller can use. Implementations must not block the event loop; all
    heavy work should be done in threads or via subprocesses inside the method.
    """

    @abc.abstractmethod
    def synth_and_play(self, text: str) -> float:
        """Synthesize and play text; returns total elapsed seconds until playback finishes."""
        raise NotImplementedError

    @abc.abstractmethod
    def synth_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize text to a WAV file at wav_path."""
        raise NotImplementedError
