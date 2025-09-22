from __future__ import annotations

import asyncio
from .service import MemoryService


async def main():
    svc = MemoryService()
    await svc.run()


if __name__ == "__main__":
    asyncio.run(main())
