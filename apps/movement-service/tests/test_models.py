from __future__ import annotations

import pytest
from pathlib import Path

from movement_service.calibration import MovementCalibration
from movement_service.models import MovementAction, MovementCommand, MovementFrame


def test_movement_command_roundtrip() -> None:
    command = MovementCommand(command=MovementAction.RESET)
    data = command.model_dump()
    parsed = MovementCommand.model_validate(data)
    assert parsed.id == command.id
    assert parsed.command is MovementAction.RESET
    assert parsed.params == {}


def test_movement_frame_defaults() -> None:
    cmd = MovementCommand(command=MovementAction.RESET)
    frame = MovementFrame(
        id=cmd.id,
        seq=0,
        total=1,
        duration_ms=200,
        hold_ms=0,
        channels={}
    )
    assert frame.duration_ms == 200
    assert frame.hold_ms == 0
    assert frame.channels == {}
    assert frame.disable_after is False
    assert frame.done is False


def test_calibration_interpolation() -> None:
    calibration = MovementCalibration()
    channels = calibration.to_channels(50, 75, 25)
    assert set(channels.keys()) == {0, 1, 2}
    assert channels[0] != channels[1]
    assert channels[0] != channels[2]
    assert isinstance(channels[0], int)


def test_calibration_load_missing(tmp_path: Path) -> None:
    calibration = MovementCalibration.load(None)
    assert calibration.lift.minimum < calibration.lift.maximum
    with pytest.raises(FileNotFoundError):
        MovementCalibration.load(str(tmp_path / "missing.json"))
