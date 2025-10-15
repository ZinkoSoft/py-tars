__all__ = ["MemoryService"]


def __getattr__(name: str):  # pragma: no cover - module-level lazy import
    if name == "MemoryService":
        from .service import MemoryService as _MemoryService

        return _MemoryService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
