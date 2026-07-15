import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

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
from config import telegram_token, ADMIN_USER_ID
from storage import init_db, get_car_loading_types, get_car_types
from menu import get_main_menu
from aiogram import Router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Инициализация БД и кэшей
init_db()
get_car_loading_types()
get_car_types()


def get_user_main_menu(user_id: int):
    """Генерирует главное меню с учётом подписки и прав."""
    is_admin = (user_id == ADMIN_USER_ID)
    has_subscription = subscription_manager.is_subscription_active(user_id)
    time_remaining = None
    if has_subscription:
        time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
    return get_main_menu(
        has_subscription=has_subscription,
        subscription_time_remaining=time_remaining,
        is_admin=is_admin,
    )


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

# Catch-all роутер — ДОЛЖЕН быть последним, чтобы не перехватывать
# сообщения, обрабатываемые другими роутерами.
catch_all_router = Router()


@catch_all_router.message(~F.text.startswith("/"))
async def catch_all_message(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Пожалуйста, используйте кнопки меню ⬇️\n"
        "Или нажмите /start чтобы вернуться в главное меню",
        reply_markup=get_user_main_menu(message.from_user.id),
    )


@catch_all_router.callback_query()
async def catch_all_callback(callback: CallbackQuery):
    await callback.answer("Эта кнопка больше не актуальна", show_alert=True)


dp.include_router(catch_all_router)


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
