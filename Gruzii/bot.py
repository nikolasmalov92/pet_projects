import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

from Gruzii.handlers.handler_admin import router as admin_router
from Gruzii.handlers.handler_start import router as handler_start
from Gruzii.handlers.handler_subscription import router as subscription_router
from Gruzii.handlers.handler_direction import router as direction_router
from Gruzii.handlers.handler_filter import router as filter_router
from Gruzii.handlers.handler_volume import router as volume_router
from Gruzii.handlers.handler_weight import router as weight_router
from Gruzii.handlers.handler_type_selection_car_load import router as type_selection_car_load_router
from Gruzii.handlers.handler_type_car import router as type_car_router

from Gruzii.subscription import subscription_manager
from Gruzii.config import telegram_token
from Gruzii.storage import init_db, get_car_loading_types, get_car_types


logging.basicConfig(level=logging.INFO)

init_db()
get_car_loading_types()
get_car_types()

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

dp.include_router(handler_start)
dp.include_router(subscription_router)
dp.include_router(admin_router)
dp.include_router(direction_router)
dp.include_router(filter_router)
dp.include_router(volume_router)
dp.include_router(weight_router)
dp.include_router(type_selection_car_load_router)
dp.include_router(type_car_router)


async def main():
    logging.info("🚀 Запуск бота")
    session = AiohttpSession(timeout=200)
    bot = Bot(token=telegram_token, session=session)

    expired_count = subscription_manager.cleanup_expired()
    if expired_count > 0:
        logging.info(f"🧹 Деактивировано {expired_count} истекших подписок")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, polling_timeout=60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("⛔ Бот остановлен пользователем")
