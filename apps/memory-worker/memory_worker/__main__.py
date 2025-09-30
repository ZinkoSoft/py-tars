from __future__ import annotations

import asyncio

from .service import MemoryService


async def _run() -> None:
    svc = MemoryService()
    await svc.run()


def main() -> None:
    """Entry point for running the memory worker."""

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover - module entry point
    main()
