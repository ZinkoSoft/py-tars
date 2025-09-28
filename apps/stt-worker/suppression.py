"""Compatibility shim re-exporting packaged suppression components."""

from stt_worker import suppression as _impl

SuppressionEngine = _impl.SuppressionEngine
SuppressionState = _impl.SuppressionState
time = _impl.time

__all__ = ["SuppressionEngine", "SuppressionState", "time"]

__doc__ = _impl.__doc__

