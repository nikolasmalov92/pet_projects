import asyncio
import logging

from bot import bot, dp, search, price_monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)


async def main():
    asyncio.create_task(price_monitor())
    try:
        await dp.start_polling(bot)
    finally:
        await search.close()


if __name__ == '__main__':
    asyncio.run(main())
