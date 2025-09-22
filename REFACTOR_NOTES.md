# Refactor notes

Date: 2025-09-22
Target Python: 3.11+
Style: PEP 8/257, black 88, isort profile=black

## Overview
Non-functional refactors focused on clarity, types, and class design. No behavior changes intended.

## Modules and classes

### apps/stt-worker/suppression.py
- Converted SuppressionState to `@dataclass(slots=True)` with a safe `default_factory` for the deque.
- Added module docstring, `__all__`, and comprehensive type hints + docstrings.
- Why/Impact: Dataclass makes state explicit and cheaper; slots prevent accidental attributes. Behavior unchanged as fields and defaults match prior code.

### apps/stt-worker/vad.py
- Added module docstring and `from __future__ import annotations`.
- Expanded docstrings and added return doc for `process_chunk` and `get_active_buffer`.
- Why/Impact: Improved readability and typing without changing control flow.

### apps/stt-worker/audio_capture.py
- Added module docstring and `from __future__ import annotations`.
- Annotated public methods; no logic changes.
- Why/Impact: Clarifies API surfaces and supports static analysis.

### apps/stt-worker/mqtt_utils.py
- Added module docstring, `__future__` annotations, explicit `__all__`.
- Light docstrings on public methods; no behavior change.
- Why/Impact: Clarifies intent and stable public API for reuse.

### apps/stt-worker/transcriber.py
- Added module docstring and `__all__` exposing only `SpeechTranscriber`.
- Added class/method docstrings; kept lazy imports to avoid unnecessary deps for WS backend.
- Why/Impact: Improves testability and separation of concerns while preserving behavior.

### apps/stt-worker/ws_stream.py
- Added module docstring and class docstring; `__future__` annotations.
- Why/Impact: Documentation and typing only.

### apps/router/main.py
- Added module docstring, annotations import, and return type hints on coroutines.
- Why/Impact: Improves readability and static checking; runtime unchanged.

### apps/tts-worker/tts_worker/service.py
- Tightened type hints on public methods; doc updates.
- Why/Impact: No behavior change; clearer contract.

### apps/tts-worker/tts_worker/piper_synth.py
- Minor regex cleanup in sentence splitter and docstrings; fixed an indentation issue introduced during edit.
- Why/Impact: Maintains functionality while simplifying regex.

### apps/ui/config.py
- Added module docstring.

### apps/ui/main.py
- Added module docstring and light doc comments; no logic changes.

### server/stt-ws/main.py
- Added module docstring and `__future__` annotations.

## Follow-ups
- Add ruff, black, isort, and mypy config to repo and run in CI.
- Consider extracting interfaces for audio I/O and MQTT to allow in-process testing with fakes.
- Add unit tests for suppression heuristics (pure function style makes it ideal).
- Evaluate logging verbosity and add structured logger if desired.
- Consider `@final` annotations for classes not intended for inheritance.

## Optional quality upgrades (added)

These are opt-in via environment variables; defaults preserve current behavior.

- Suppression heuristics
	- SUPPRESS_USE_SYLLAPY=1 enables syllable counting via syllapy for better accuracy.
	- SUPPRESS_USE_RAPIDFUZZ=1 enables fuzzy echo suppression using rapidfuzz.ratio.
	- ECHO_FUZZ_MIN_RATIO sets the similarity threshold (default 0.85).
	- Dependencies (apps/stt-worker/requirements.txt): syllapy, rapidfuzz.

- TTS playback
	- TTS_SIMPLEAUDIO=1 makes PiperSynth play WAVs using simpleaudio in-process instead of paplay/aplay.
	- Note: simpleaudio is NOT installed by default to keep images minimal and avoid build toolchain on aarch64. If desired, add `simpleaudio` to `apps/tts-worker/requirements.txt` or install it in a derived image.

- Resampling (not enabled): we kept numpy.interp for minimal footprint. If higher-quality resampling is desired, consider adding resampy/librosa and gating via config.

## Validation
- Behavioral changes none expected. Docker-compose build/run should verify end-to-end.
- Note: Editor may flag imports that are installed only in containers; this is expected.
