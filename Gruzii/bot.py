import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery

from handlers.handler_admin import router as admin_router
from handlers.handler_start import router as handler_start
from handlers.handler_subscription import router as subscription_router
from handlers.handler_direction import router as direction_router
from handlers.handler_filter import router as filter_router
from handlers.handler_volume import router as volume_router
from handlers.handler_weight import router as weight_router
from handlers.handler_type_selection_car_load import router as type_selection_car_load_router
from handlers.handler_type_car import router as type_car_router
from handlers.handler_presets import router as presets_router

from subscription import subscription_manager
from config import telegram_token
from storage import init_db, get_car_loading_types, get_car_types

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Инициализация БД и кэшей
init_db()
get_car_loading_types()
get_car_types()

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация роутеров
dp.include_router(handler_start)
dp.include_router(subscription_router)
dp.include_router(admin_router)
dp.include_router(direction_router)
dp.include_router(filter_router)
dp.include_router(volume_router)
dp.include_router(weight_router)
dp.include_router(type_selection_car_load_router)
dp.include_router(type_car_router)
dp.include_router(presets_router)


# Catch-all для необработанных сообщений и callback-кнопок
@dp.message()
async def catch_all_message(message: Message):
    await message.answer("Пожалуйста, используйте кнопки меню ⬇️")


@dp.callback_query()
async def catch_all_callback(callback: CallbackQuery):
    await callback.answer("Эта кнопка больше не актуальна", show_alert=True)


async def main():
    logger.info("Запуск бота")

    # Увеличенный таймаут (секунды) для стабильности при проблемах с сетью
    session = AiohttpSession(timeout=180)
    bot = Bot(token=telegram_token, session=session)

    # Очистка истекших подписок при старте
    try:
        expired_count = subscription_manager.cleanup_expired()
        if expired_count > 0:
            logger.info(f"Деактивировано {expired_count} истекших подписок")
    except Exception as e:
        logger.error(f"Ошибка при очистке подписок: {e}")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, polling_timeout=60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
