from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from movement_service.calibration import MovementCalibration
from movement_service.models import MovementAction, MovementFrame, MovementCommand


@dataclass(frozen=True)
class LegFrame:
    height: float | None
    starboard: float | None
    port: float | None
    duration_ms: int
    hold_ms: int = 0
    disable_after: bool = False


def build_frames(command: MovementCommand, calibration: MovementCalibration) -> Iterable[MovementFrame]:
    planner = _SEQUENCES.get(command.command)
    if planner is None:
        yield from _idle_frames(command, calibration)
        return
    frames = planner(command, calibration)
    for idx, frame in enumerate(frames):
        total = len(frames)
        yield MovementFrame(
            id=command.id,
            seq=idx,
            total=total,
            duration_ms=frame.duration_ms,
            hold_ms=frame.hold_ms,
            channels=calibration.to_channels(frame.height, frame.starboard, frame.port),
            disable_after=frame.disable_after,
            done=idx == total - 1,
        )


def _idle_frames(command: MovementCommand, calibration: MovementCalibration) -> list[MovementFrame]:
    return [
        MovementFrame(
            id=command.id,
            seq=0,
            total=1,
            duration_ms=200,
            hold_ms=calibration.neutral_hold_ms,
            channels=calibration.to_channels(50, 50, 50),
            disable_after=True,
            done=True,
        )
    ]


def _reset(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return [
        LegFrame(20, 0, 0, duration_ms=300),
        LegFrame(30, 50, 50, duration_ms=200),
        LegFrame(50, 50, 50, duration_ms=200, hold_ms=200, disable_after=True),
    ]


def _sequence(*frames: LegFrame) -> list[LegFrame]:
    return list(frames)


def _step_forward(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return _sequence(
        LegFrame(50, 50, 50, 400),
        LegFrame(22, 50, 50, 600),
        LegFrame(40, 17, 17, 650),
        LegFrame(85, 50, 50, 800),
        LegFrame(50, 50, 50, 1000, hold_ms=400, disable_after=True),
    )


def _step_backward(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return _sequence(
        LegFrame(50, 50, 50, 400),
        LegFrame(28, 0, 0, 600),
        LegFrame(35, 70, 70, 600),
        LegFrame(55, 40, 40, 200),
        LegFrame(50, 50, 50, 800, hold_ms=300, disable_after=True),
    )


def _turn_right(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return _sequence(
        LegFrame(50, 50, 50, 400),
        LegFrame(100, 0, 0, 800),
        LegFrame(0, 70, 30, 600),
        LegFrame(50, 0, 0, 600),
        LegFrame(0, 50, 50, 300),
        LegFrame(50, 50, 50, 400, hold_ms=200, disable_after=True),
    )


def _turn_left(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return _sequence(
        LegFrame(50, 50, 50, 400),
        LegFrame(100, 0, 0, 800),
        LegFrame(0, 30, 70, 300),
        LegFrame(50, 0, 0, 600),
        LegFrame(0, 50, 50, 300),
        LegFrame(50, 50, 50, 400, hold_ms=200, disable_after=True),
    )


def _balance(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return _sequence(
        LegFrame(50, 50, 50, 400),
        LegFrame(30, 50, 50, 800),
        LegFrame(30, 60, 60, 500),
        LegFrame(30, 40, 40, 500),
        LegFrame(30, 60, 60, 500),
        LegFrame(30, 40, 40, 500),
        LegFrame(30, 50, 50, 800),
        LegFrame(50, 50, 50, 800, hold_ms=300, disable_after=True),
    )


def _laugh(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    frames: list[LegFrame] = []
    for _ in range(5):
        frames.extend(
            [
                LegFrame(50, 50, 50, 200),
                LegFrame(1, 50, 50, 200),
            ]
        )
    frames.append(LegFrame(50, 50, 50, 200, hold_ms=200, disable_after=True))
    return frames


def _swing_legs(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return _sequence(
        LegFrame(50, 50, 50, 200),
        LegFrame(100, 50, 50, 200),
        LegFrame(0, 20, 80, 600),
        LegFrame(0, 80, 20, 600),
        LegFrame(0, 20, 80, 600),
        LegFrame(0, 80, 20, 600),
        LegFrame(0, 50, 50, 600),
        LegFrame(50, 50, 50, 700, hold_ms=200, disable_after=True),
    )


def _pose(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return _sequence(
        LegFrame(50, 50, 50, 400),
        LegFrame(30, 40, 40, 400),
        LegFrame(100, 30, 30, 400, hold_ms=1000),
        LegFrame(30, 30, 30, 400),
        LegFrame(30, 40, 40, 400),
        LegFrame(50, 50, 50, 400, hold_ms=200, disable_after=True),
    )


def _bow(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return _sequence(
        LegFrame(50, 50, 50, 400),
        LegFrame(15, 50, 50, 700),
        LegFrame(15, 70, 70, 700),
        LegFrame(60, 70, 70, 700),
        LegFrame(95, 65, 65, 700, hold_ms=1000),
        LegFrame(15, 65, 65, 700),
        LegFrame(50, 50, 50, 400, hold_ms=200, disable_after=True),
    )


def _disable(command: MovementCommand, calibration: MovementCalibration) -> list[LegFrame]:
    return [LegFrame(50, 50, 50, 200, hold_ms=0, disable_after=True)]


_SEQUENCES: dict[MovementAction, callable[[MovementCommand, MovementCalibration], list[LegFrame]]] = {
    MovementAction.RESET: _reset,
    MovementAction.DISABLE: _disable,
    MovementAction.STEP_FORWARD: _step_forward,
    MovementAction.STEP_BACKWARD: _step_backward,
    MovementAction.TURN_LEFT: _turn_left,
    MovementAction.TURN_RIGHT: _turn_right,
    MovementAction.BALANCE: _balance,
    MovementAction.LAUGH: _laugh,
    MovementAction.SWING_LEGS: _swing_legs,
    MovementAction.POSE: _pose,
    MovementAction.BOW: _bow,
}
