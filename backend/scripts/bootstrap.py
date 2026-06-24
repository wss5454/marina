"""Run migrations then seed test users. Usage: python -m scripts.bootstrap"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marina_service.database import async_session_factory
from scripts.bootstrap_users import run_bootstrap


async def main() -> None:
    async with async_session_factory() as db:
        await run_bootstrap(db)


if __name__ == "__main__":
    asyncio.run(main())
