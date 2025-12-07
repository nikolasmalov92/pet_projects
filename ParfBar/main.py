import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from ParfBar.handlers.user_handler import router as user_router
from ParfBar.handlers.admin_handler import router as admin_router
from ParfBar.CallbackData.callbacks import router as callback_router
from ParfBar.database.db import init_db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    logging.info("Бот запущен")

    dp.include_router(user_router)
    dp.include_router(callback_router)
    dp.include_router(admin_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
