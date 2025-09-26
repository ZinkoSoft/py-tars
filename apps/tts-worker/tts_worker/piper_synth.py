from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
import threading
import time
import re
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable


logger = logging.getLogger("tts-worker.piper")


_PLAYER_OBSERVER: Callable[[subprocess.Popen, str], None] | None = None
_STOP_CHECKER: Callable[[], bool] | None = None


def set_player_observer(observer: Callable[[subprocess.Popen, str], None] | None) -> None:
    global _PLAYER_OBSERVER
    _PLAYER_OBSERVER = observer


def set_stop_checker(checker: Callable[[], bool] | None) -> None:
    global _STOP_CHECKER
    _STOP_CHECKER = checker


def _notify_observer(proc: subprocess.Popen, role: str) -> None:
    observer = _PLAYER_OBSERVER
    if observer is None:
        return
    try:
        observer(proc, role)
    except Exception:
        logger.debug("player observer raised", exc_info=True)


def _should_abort() -> bool:
    checker = _STOP_CHECKER
    if checker is None:
        return False
    try:
        return bool(checker())
    except Exception:
        logger.debug("stop checker raised", exc_info=True)
        return False


try:
    from piper.voice import PiperVoice  # type: ignore
    logger.info("Piper Python API is available")
    _HAS_PIPER_API = True
except Exception as e:  # pragma: no cover - environment dependent
    logger.info(f"Piper Python API not available, will use CLI fallback: {e}")
    PiperVoice = None  # type: ignore
    _HAS_PIPER_API = False


class PiperSynth:
    """Piper text-to-speech wrapper.

    - Keeps voice model loaded (when API available)
    - Supports two playback modes: streaming to player or synth-to-file then play
    - Provides robust fallbacks to ensure audible output
    """

    def __init__(self, voice_path: str):
        self.voice_path = voice_path
        self.voice: Optional[object] = None
        if _HAS_PIPER_API:
            self._load_voice()

    # ----- Public API -----
    def synth_and_play(self, text: str, streaming: bool = False, pipeline: bool = True) -> float:
        """Synthesize `text` and play it.

        Returns total elapsed seconds until playback finishes.
        """
        # Optionally split long text into sentence-sized chunks to reduce time-to-first-audio
        chunks = self._split_sentences(text) if pipeline else [text]
        # If the splitter produced no chunks (empty/whitespace), keep behavior predictable
        if not chunks:
            return 0.0

        # If streaming is enabled, we can't pre-synthesize and cache effectively; use existing path
        if streaming:
            total = 0.0
            for idx, chunk in enumerate(chunks):
                if not chunk:
                    continue
                try:
                    total += self._stream_to_player(chunk)
                except Exception as e:
                    logger.warning(f"Streaming failed on chunk {idx+1}/{len(chunks)}: {e}; falling back to file playback for this chunk")
                    total += self._file_playback(chunk)
            return total

        # Non-streaming: optionally synthesize multiple chunks concurrently, cache WAVs, and play in order
        concurrency = 1
        try:
            # Late import to avoid circulars
            from .config import TTS_CONCURRENCY  # type: ignore
            concurrency = max(1, int(TTS_CONCURRENCY))
        except Exception:
            concurrency = 1

        if pipeline and len(chunks) > 1:
            # Use pipelined pre-synthesis and sequential playback to minimize gaps
            return self._file_playback_pipelined(chunks, concurrency=concurrency)

        # Default sequential file playback
        total = 0.0
        for chunk in chunks:
            if not chunk:
                continue
            total += self._file_playback(chunk)
        return total

    # ----- Internals -----
    def _load_voice(self) -> None:
        assert PiperVoice is not None
        try:
            logger.info(f"Loading Piper voice model once: {self.voice_path}")
            # Try both path and file-object forms; support optional config json
            try:
                self.voice = PiperVoice.load(self.voice_path)  # type: ignore[attr-defined]
            except TypeError:
                with open(self.voice_path, "rb") as mf:
                    config_path = self.voice_path + ".json" if os.path.exists(self.voice_path + ".json") else None
                    if config_path:
                        try:
                            self.voice = PiperVoice.load(mf, config_path=config_path)  # type: ignore
                        except TypeError:
                            self.voice = PiperVoice.load(mf)  # type: ignore
                    else:
                        self.voice = PiperVoice.load(mf)  # type: ignore
            logger.info("Piper voice loaded and ready")
        except Exception as e:
            logger.warning(f"Failed to load Piper API model, will use CLI fallback: {e}")
            self.voice = None

    def _synth_to_wav(self, text: str, wav_path: str) -> None:
        if self.voice is not None:
            # API path: write to file (works across versions)
            try:
                with open(wav_path, "wb") as f:
                    # Try known keyword variants first to write directly to file handle
                    wrote_via_kw = False
                    for kw in ("wav_file", "wavfile", "audio_out"):
                        try:
                            self.voice.synthesize(text, **{kw: f})  # type: ignore[arg-type]
                            wrote_via_kw = True
                            break
                        except TypeError:
                            continue

                    if not wrote_via_kw:
                        # Fall back to return-value style; support bytes, numpy-like, or generators/iterables
                        audio_obj = self.voice.synthesize(text)  # type: ignore[call-arg]

                        def _write_chunk(chunk) -> None:
                            if chunk is None:
                                return
                            if isinstance(chunk, (bytes, bytearray)):
                                f.write(chunk)
                            elif isinstance(chunk, memoryview):
                                f.write(chunk.tobytes())
                            elif hasattr(chunk, "tobytes"):
                                f.write(chunk.tobytes())  # type: ignore[attr-defined]
                            else:
                                # Let outer logic decide on unsupported chunk types
                                raise TypeError(f"Unsupported chunk type: {type(chunk)!r}")

                        if isinstance(audio_obj, (bytes, bytearray, memoryview)) or hasattr(audio_obj, "tobytes"):
                            _write_chunk(audio_obj)
                        elif hasattr(audio_obj, "__iter__") and not isinstance(audio_obj, (str, bytes, bytearray)):
                            # Generator/iterable of chunks
                            iterator = iter(audio_obj)
                            try:
                                first = next(iterator)
                            except StopIteration:
                                # Nothing produced; fall back to CLI silently
                                f.close()
                                self._cli_synth(text, wav_path)
                                return

                            # If chunks have samples+sample_rate, write a proper WAV via wave module
                            if hasattr(first, "samples") and hasattr(first, "sample_rate"):
                                import wave

                                def _as_bytes(samples):
                                    if isinstance(samples, (bytes, bytearray, memoryview)):
                                        return bytes(samples)
                                    if hasattr(samples, "tobytes"):
                                        return samples.tobytes()  # type: ignore[attr-defined]
                                    return bytes(samples)

                                channels = getattr(first, "channels", getattr(first, "num_channels", 1))
                                sampwidth = getattr(first, "sample_width", 2)  # default 16-bit
                                framerate = getattr(first, "sample_rate", 22050)

                                with wave.open(f, "wb") as wf:
                                    wf.setnchannels(int(channels) or 1)
                                    wf.setsampwidth(int(sampwidth) or 2)
                                    wf.setframerate(int(framerate) or 22050)
                                    wf.writeframes(_as_bytes(getattr(first, "samples")))
                                    for ch in iterator:
                                        if hasattr(ch, "samples"):
                                            wf.writeframes(_as_bytes(getattr(ch, "samples")))
                                        else:
                                            # Mixed types; fallback for safety
                                            raise TypeError(f"Mixed or unsupported chunk type: {type(ch)!r}")
                            else:
                                # Unsupported chunk structure; fall back to CLI silently
                                f.close()
                                self._cli_synth(text, wav_path)
                                return
                        else:
                            # Unknown return type; fall back to CLI silently
                            f.close()
                            self._cli_synth(text, wav_path)
                            return
            except Exception as e:
                logger.warning(f"Piper API synth failed: {e}; using CLI fallback")
                self._cli_synth(text, wav_path)
        else:
            self._cli_synth(text, wav_path)

    def _file_playback(self, text: str) -> float:
        t0 = time.time()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            self._synth_to_wav(text, f.name)
            self._play_wav(f.name)
        return time.time() - t0

    def _file_playback_pipelined(self, chunks: list[str], concurrency: int = 2) -> float:
        """Pre-synthesize chunks concurrently to WAV files, then play in-order from cache.

        This reduces wait time between sentences. Uses a temporary directory for cache.
        """
        t0 = time.time()
        # Guard against excessive workers
        workers = max(1, min(concurrency, 8))
        # Cache dir survives until method exit for stable file paths
        with tempfile.TemporaryDirectory(prefix="piper_cache_") as cache_dir:
            # Submit synthesis tasks
            def _task(idx_and_text: tuple[int, str]) -> tuple[int, str]:
                idx, txt = idx_and_text
                out_path = os.path.join(cache_dir, f"chunk_{idx:03d}.wav")
                try:
                    self._synth_to_wav(txt, out_path)
                except Exception as e:
                    logger.warning(f"Synthesis failed for chunk {idx}: {e}; retrying via CLI fallback")
                    # _synth_to_wav already falls back internally; in case of persistent failure, create empty file
                    try:
                        open(out_path, "wb").close()
                    except Exception:
                        pass
                return idx, out_path

            # Kick off synth jobs with limited parallelism
            idx_texts = [(i, c) for i, c in enumerate(chunks) if c]
            ready: dict[int, str] = {}
            next_to_play = 0
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="piper-synth") as ex:
                futures = {ex.submit(_task, it): it[0] for it in idx_texts}
                # While there are pending futures or unplayed chunks
                while futures or next_to_play < len(chunks):
                    # Play any already-ready chunks in order
                    played_any = False
                    while next_to_play in ready:
                        path = ready.pop(next_to_play)
                        try:
                            self._play_wav(path)
                        finally:
                            # Remove file after playback to keep cache small
                            try:
                                os.remove(path)
                            except Exception:
                                pass
                        next_to_play += 1
                        played_any = True
                    if next_to_play >= len(chunks):
                        break
                    if played_any:
                        # Loop back to check for more in-order ready items
                        continue
                    # Wait for at least one synth to complete
                    if not futures:
                        # Nothing to wait on; likely empty chunks ahead. Advance to end.
                        next_to_play = len(chunks)
                        break
                    done, _pending = next(as_completed(futures)), None
                    try:
                        fut = done
                        idx = futures.pop(fut)
                        res_idx, out_path = fut.result()
                        ready[res_idx] = out_path
                    except Exception as e:
                        logger.warning(f"Synthesis task error: {e}")
                        # Mark this index as ready with an empty placeholder to avoid deadlock
                        ready[idx] = os.path.join(cache_dir, f"chunk_{idx:03d}.wav")
                        try:
                            open(ready[idx], "wb").close()
                        except Exception:
                            pass
        return time.time() - t0

    def _stream_to_player(self, text: str) -> float:
        """Try API streaming if supported, else CLI streaming to paplay/aplay."""
        t0 = time.time()
        if self.voice is not None and _supports_wav_file(self.voice):
            return self._api_stream(text, t0)
        return self._cli_stream(text, t0)

    def _api_stream(self, text: str, t0: float) -> float:
        assert self.voice is not None
        r_fd, w_fd = os.pipe()
        r = os.fdopen(r_fd, "rb", buffering=0)
        w = os.fdopen(w_fd, "wb", buffering=0)

        class _PipeWriter(io.RawIOBase):
            def __init__(self, fh):
                self.fh = fh
            def writable(self):
                return True
            def write(self, b):
                return self.fh.write(b)
            def flush(self):
                try:
                    self.fh.flush()
                except Exception:
                    pass

        writer = _PipeWriter(w)

        def _synth_thread():
            try:
                try:
                    self.voice.synthesize(text, wav_file=writer)  # type: ignore[arg-type]
                except TypeError:
                    try:
                        self.voice.synthesize(text, wavfile=writer)  # type: ignore
                    except TypeError:
                        self.voice.synthesize(text, audio_out=writer)  # type: ignore
            finally:
                try:
                    writer.flush()
                except Exception:
                    pass
                try:
                    w.close()
                except Exception:
                    pass

        th = threading.Thread(target=_synth_thread, daemon=True)
        th.start()
        p_play = _spawn_player(stdin=r, role="stream-player")
        rc = p_play.wait()
        th.join(timeout=1.0)
        try:
            r.close()
        except Exception:
            pass
        if rc != 0:
            if rc < 0 or _should_abort():
                logger.debug(f"Streaming player exited with code {rc}; aborting playback per stop request")
                return time.time() - t0
            logger.warning(f"paplay/aplay exited with code {rc}; falling back to file playback")
            return self._file_playback(text)
        return time.time() - t0

    def _cli_stream(self, text: str, t0: float) -> float:
        cmd = ["piper", "-m", self.voice_path, "-f", "-"]
        logger.debug(f"Streaming via Piper CLI -> player: {' '.join(cmd)} | paplay -")
        p_piper = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=False)
        p_play = _spawn_player(stdin=p_piper.stdout, role="stream-player")
        assert p_piper.stdin is not None
        p_piper.stdin.write(text.encode("utf-8"))
        p_piper.stdin.close()
        rc = p_play.wait()
        p_piper.wait()
        if rc != 0:
            if rc < 0 or _should_abort():
                logger.debug(f"CLI streaming player exited with code {rc}; aborting playback per stop request")
                return time.time() - t0
            logger.warning(f"paplay/aplay exited with code {rc} (CLI stream); falling back to file playback")
            return self._file_playback(text)
        return time.time() - t0

    def _cli_synth(self, text: str, wav_path: str) -> None:
        cmd = ["piper", "-m", self.voice_path, "-f", wav_path]
        logger.debug(f"Synthesizing via Piper CLI: {' '.join(cmd)}")
        subprocess.run(cmd, input=text, text=True, check=True)

    def _play_wav(self, path: str) -> None:
        # If configured and available, use simpleaudio to play in-process
        try:
            from .config import TTS_SIMPLEAUDIO  # local import to avoid circulars at module import
        except Exception:
            TTS_SIMPLEAUDIO = 0  # type: ignore

        if TTS_SIMPLEAUDIO:
            try:
                import simpleaudio as sa  # type: ignore
                import wave
                with wave.open(path, 'rb') as wf:
                    audio_data = wf.readframes(wf.getnframes())
                    sample_rate = wf.getframerate()
                    num_channels = wf.getnchannels()
                    sample_width = wf.getsampwidth()
                # simpleaudio expects raw PCM parameters
                play_obj = sa.play_buffer(audio_data, num_channels=num_channels, bytes_per_sample=sample_width, sample_rate=sample_rate)
                play_obj.wait_done()
                return
            except Exception as e:
                logger.warning(f"simpleaudio playback failed, falling back to system player: {e}")

        # Fallback: system player via paplay/aplay
        p = _spawn_player(args=[path], role="playback")
        rc = p.wait()
        if rc != 0:
            if rc < 0 or _should_abort():
                return
            # Try alternate player
            alt = _spawn_player(args=[path], prefer_aplay=True, role="playback-alt")
            alt.wait()

    # ----- helpers -----
    def _split_sentences(self, text: str) -> list[str]:
        """Lightweight sentence splitter.

        Splits on punctuation that typically ends sentences: . ! ?
        Collapses extra whitespace and preserves punctuation with the chunk.
        """
        t = (text or "").strip()
        if not t:
            return []
        # Split on whitespace following ., !, or ?
        parts = re.split(r"(?<=[.!?])\s+", t)
        # If no sentence-ending punctuation, return as single chunk
        chunks = [p.strip() for p in parts if p and p.strip()]
        return chunks if chunks else [t]


def _supports_wav_file(voice: object) -> bool:
    import inspect
    try:
        sig = inspect.signature(voice.synthesize)  # type: ignore[attr-defined]
    except Exception:
        return False
    return any(p.name in ("wav_file", "wavfile", "audio_out") for p in sig.parameters.values())


def _spawn_player(
    stdin=None,
    args: Optional[list[str]] = None,
    prefer_aplay: bool = False,
    *,
    role: str = "player",
):
    """Start paplay/aplay with given stdin or path args."""
    if args is None:
        args = ["-"]
    if prefer_aplay:
        try:
            proc = subprocess.Popen(["aplay", *args], stdin=stdin)
        except FileNotFoundError:
            proc = subprocess.Popen(["paplay", *args], stdin=stdin)
        _notify_observer(proc, role)
        return proc
    try:
        proc = subprocess.Popen(["paplay", *args], stdin=stdin)
    except FileNotFoundError:
        proc = subprocess.Popen(["aplay", *args], stdin=stdin)
    _notify_observer(proc, role)
    return proc
