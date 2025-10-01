from __future__ import annotations

from movement_service.calibration import MovementCalibration
from movement_service.models import MovementAction, MovementCommand
from movement_service.sequences import build_frames


def test_reset_sequence_has_disable() -> None:
    calibration = MovementCalibration()
    command = MovementCommand(command=MovementAction.RESET)
    frames = list(build_frames(command, calibration))
    assert frames[-1].disable_after is True
    assert frames[-1].done is True


def test_disable_sequence_cuts_power() -> None:
    calibration = MovementCalibration()
    command = MovementCommand(command=MovementAction.DISABLE)
    frames = list(build_frames(command, calibration))
    assert len(frames) == 1
    assert frames[0].disable_after is True


def test_frames_increment_sequence_numbers() -> None:
    calibration = MovementCalibration()
    command = MovementCommand(command=MovementAction.STEP_FORWARD)
    frames = list(build_frames(command, calibration))
    assert [frame.seq for frame in frames] == list(range(len(frames)))
    assert frames[0].total == len(frames)
