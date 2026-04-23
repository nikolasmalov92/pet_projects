import asyncio

from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram import F

from Gruzii.storage import save_user, load_users, delete_processed
from Gruzii.config import ADMIN_USER_ID
from Gruzii.subscription import subscription_manager
from Gruzii.menu import get_main_menu
from Gruzii.storage import tasks, active_searches

import logging

logging.basicConfig(level=logging.INFO)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()

    await asyncio.to_thread(save_user, user_id)

    allowed_users = await asyncio.to_thread(load_users)
    await asyncio.create_task(asyncio.to_thread(delete_processed))

    if user_id in allowed_users or user_id == ADMIN_USER_ID:
        first_name = message.from_user.first_name or "Пользователь"
        is_admin = (user_id == ADMIN_USER_ID)

        # Проверяем подписку
        has_subscription = subscription_manager.is_subscription_active(user_id)
        time_remaining = None
        if has_subscription:
            time_remaining = subscription_manager.get_formatted_time_remaining(user_id)

        if has_subscription:
            await message.answer(
                f"🚚 <b>Добро пожаловать, {first_name}!</b>\n\n"
                f"⚡ <b>Ваша подписка активна</b> ⏰\n"
                f"Осталось времени: <b>{time_remaining}</b>\n\n"
                "🔍 Нажмите 'Найти грузы', чтобы начать!",
                parse_mode="HTML",
                reply_markup=get_main_menu(has_subscription=True,
                                           subscription_time_remaining=time_remaining,
                                           is_admin=is_admin)
            )
        else:
            await message.answer(
                f"🚚 <b>Добро пожаловать, {first_name}!</b>\n\n"
                "📋 <b>Для работы с ботом необходима подписка</b>\n\n"
                "⏰ Подписка даёт доступ на 24 часа.\n"
                "Нажмите 'Подписаться', чтобы активировать доступ.",
                parse_mode="HTML",
                reply_markup=get_main_menu(has_subscription=False, is_admin=is_admin)
            )
    else:
        await message.answer(
            "❌ <b>Доступ ограничен</b>\n\n"
            "Для использования бота обратитесь к администратору",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    active_searches[user_id] = False
    task = tasks.get(user_id)
    if task:
        task.cancel()

    # Проверяем подписку
    has_subscription = subscription_manager.is_subscription_active(user_id)
    time_remaining = None
    if has_subscription:
        time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
    is_admin = (user_id == ADMIN_USER_ID)

    await callback.message.edit_text(
        "❌ <b>Действие отменено</b>\n\n"
        "Вернулись в главное меню",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "Что хотели бы сделать?",
        reply_markup=get_main_menu(has_subscription=has_subscription,
                                   subscription_time_remaining=time_remaining,
                                   is_admin=is_admin)
    )
    await state.clear()


@router.message(F.text == "⛔ Остановить")
async def stop_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    active_searches[user_id] = False
    task = tasks.get(user_id)
    if task:
        task.cancel()

    # Проверяем подписку
    has_subscription = subscription_manager.is_subscription_active(user_id)
    time_remaining = None
    if has_subscription:
        time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
    is_admin = (user_id == ADMIN_USER_ID)

    await state.clear()
    await message.answer(
        "⛔ <b>Поиск остановлен</b>\n\n"
        "Спасибо за использование! 😊",
        parse_mode="HTML",
        reply_markup=get_main_menu(has_subscription=has_subscription,
                                   subscription_time_remaining=time_remaining,
                                   is_admin=is_admin)
    )


@router.message(F.text == "🔙 Главное меню")
async def back_to_main(message: Message, state: FSMContext):
    user_id = message.from_user.id
    active_searches[user_id] = False

    await state.clear()

    # Проверяем подписку
    has_subscription = subscription_manager.is_subscription_active(user_id)
    time_remaining = None
    if has_subscription:
        time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
    is_admin = (user_id == ADMIN_USER_ID)

    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_main_menu(has_subscription=has_subscription,
                                   subscription_time_remaining=time_remaining,
                                   is_admin=is_admin)
    )


@router.callback_query(F.data == "stop_search")
async def inline_stop_search(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    active_searches[user_id] = False
    task = tasks.get(user_id)
    if task:
        task.cancel()

    # Проверяем подписку
    has_subscription = subscription_manager.is_subscription_active(user_id)
    time_remaining = None
    if has_subscription:
        time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
    is_admin = (user_id == ADMIN_USER_ID)

    await state.clear()
    await callback.message.edit_text(
        "⛔ <b>Поиск остановлен</b>\n\nСпасибо за использование! 😊",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "🏠 <b>Главное меню</b>",
        reply_markup=get_main_menu(has_subscription=has_subscription,
                                   subscription_time_remaining=time_remaining,
                                   is_admin=is_admin)
    )
