import json
import math
from pathlib import Path

import numpy as np
import pytest

from wake_activation.detector import DetectorUnavailableError, WakeDetector, create_wake_detector


class DummyBackend:
    frame_samples = 1280
    sample_rate = 16_000

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self._calls = 0

    def process(self, frame: np.ndarray) -> float:
        try:
            value = self._scores[self._calls]
        except IndexError:
            value = 0.0
        self._calls += 1
        return value

    def reset(self) -> None:
        self._calls = 0


def _build_detector(scores: list[float], **kwargs: float) -> WakeDetector:
    backend = DummyBackend(scores)
    return WakeDetector(
        backend,
        threshold=kwargs.get("threshold", 0.5),
        min_retrigger_sec=kwargs.get("min_retrigger_sec", 0.5),
        energy_window_ms=int(kwargs.get("energy_window_ms", 750)),
    )


def _load_regression_sequences() -> dict[str, dict[str, list[float]]]:
    data_path = Path(__file__).with_name("data") / "wake_regression_sequences.json"
    with data_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


def test_wake_detector_triggers_when_threshold_exceeded() -> None:
    detector = _build_detector([0.2, 0.7])
    frame = np.ones(detector.frame_samples, dtype=np.float32) * 0.5

    assert detector.process_frame(frame, ts=0.0) is None
    result = detector.process_frame(frame, ts=1.0)
    assert result is not None
    assert math.isclose(result.score, 0.7, rel_tol=1e-6)
    assert result.energy > 0.0


def test_wake_detector_respects_min_retrigger() -> None:
    detector = _build_detector([0.8, 0.9, 0.95], min_retrigger_sec=1.0)
    frame = np.ones(detector.frame_samples, dtype=np.float32) * 0.3

    first = detector.process_frame(frame, ts=0.0)
    assert first is not None

    # Within min retrigger window -> suppressed
    second = detector.process_frame(frame, ts=0.4)
    assert second is None

    third = detector.process_frame(frame, ts=1.2)
    assert third is not None
    assert third.score > first.score


def test_wake_detector_energy_matches_rms() -> None:
    detector = _build_detector([0.6], energy_window_ms=1000)
    frame = np.ones(detector.frame_samples, dtype=np.float32)

    result = detector.process_frame(frame, ts=0.0)
    assert result is not None
    assert math.isclose(result.energy, 1.0, rel_tol=1e-3)


def test_create_wake_detector_missing_model(tmp_path: Path) -> None:
    missing = tmp_path / "missing_model.tflite"
    with pytest.raises(DetectorUnavailableError):
        create_wake_detector(
            missing,
            threshold=0.5,
            min_retrigger_sec=1.0,
            energy_window_ms=750,
        )


@pytest.mark.parametrize(
    ("scenario", "expected_detection"),
    [
        ("wake_positive", True),
        ("wake_near_miss", False),
        ("background_noise", False),
    ],
)
def test_regression_sequences_trigger_expected_detection(scenario: str, expected_detection: bool) -> None:
    sequences = _load_regression_sequences()
    sample = sequences[scenario]

    threshold = 0.6
    detector = _build_detector(sample["scores"], threshold=threshold, min_retrigger_sec=0.4, energy_window_ms=1000)

    expected_first_trigger = next((score for score in sample["scores"] if score >= threshold), None)

    detection = None
    timestamp = 0.0
    triggered_index: int | None = None
    for idx, (amplitude, _) in enumerate(zip(sample["amplitudes"], sample["scores"])):
        frame = np.full(detector.frame_samples, float(amplitude), dtype=np.float32)
        detection = detector.process_frame(frame, ts=timestamp)
        timestamp += 0.25
        if detection is not None:
            triggered_index = idx
            break

    assert (detection is not None) == expected_detection

    if detection is not None:
        assert expected_first_trigger is not None
        assert math.isclose(detection.score, expected_first_trigger, rel_tol=1e-6)
        assert triggered_index is not None
        assert triggered_index <= sample["scores"].index(expected_first_trigger)
        assert detection.energy > 0.0
