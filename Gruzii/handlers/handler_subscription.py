import asyncio

from aiogram import F
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from Gruzii.config import ADMIN_USER_ID
from Gruzii.menu import get_main_menu
from Gruzii.storage import load_users
from Gruzii.subscription import subscription_manager

import logging

logging.basicConfig(level=logging.INFO)

router = Router()


@router.message(F.text == "📝 Подписаться")
async def subscribe_user(message: Message):
    user_id = message.from_user.id
    allowed_users = await asyncio.to_thread(load_users)

    if user_id not in allowed_users and user_id != ADMIN_USER_ID:
        await message.answer(
            "❌ <b>Доступ ограничен</b>\n\n"
            "Для использования бота обратитесь к администратору",
            parse_mode="HTML"
        )
        return

    try:
        # Активируем подписку
        subscription = subscription_manager.activate_subscription(user_id)
        end_time = subscription["end_time"].strftime("%d.%m.%Y %H:%M")
        is_admin = (user_id == ADMIN_USER_ID)

        await message.answer(
            f"✅ <b>Подписка активирована!</b>\n\n"
            f"⏰ Действует до: <b>{end_time}</b>\n"
            f"🕐 Длительность: <b>24 часа</b>\n\n"
            "🔍 Теперь вы можете искать грузы!\n"
            "Нажмите 'Найти грузы', чтобы начать.",
            parse_mode="HTML",
            reply_markup=get_main_menu(has_subscription=True, is_admin=is_admin)
        )
    except ValueError as e:
        await message.answer(
            "⚠️ <b>Пробная подписка уже использована</b>\n\n"
            "Ваш пробный период закончился.\n"
            "Для продолжения работы обратитесь к администратору\n"
            "для приобретения платной подписки.",
            parse_mode="HTML"
        )


@router.message(Command("subscription"))
async def check_subscription(message: Message):
    user_id = message.from_user.id
    sub_info = subscription_manager.get_subscription_info(user_id)

    if not sub_info:
        await message.answer(
            "📋 <b>У вас нет активной подписки</b>\n\n"
            "Нажмите 'Подписаться', чтобы получить доступ на 24 часа.",
            parse_mode="HTML"
        )
    else:
        start_time = sub_info["start_time"].strftime("%d.%m.%Y %H:%M")
        end_time = sub_info["end_time"].strftime("%d.%m.%Y %H:%M")
        is_active = sub_info["is_active"]
        time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
        sub_type = sub_info["subscription_type"]

        type_label = "💎 Платная" if sub_type.value == "paid" else "🎁 Пробная"

        if is_active and time_remaining:
            status = "✅ Активна"
            await message.answer(
                f"📋 <b>Информация о подписке</b>\n\n"
                f"Тип: <b>{type_label}</b>\n"
                f"Статус: <b>{status}</b>\n"
                f"Начало: <b>{start_time}</b>\n"
                f"Окончание: <b>{end_time}</b>\n"
                f"Осталось времени: <b>{time_remaining}</b>",
                parse_mode="HTML"
            )
        else:
            status = "❌ Истекла"
            await message.answer(
                f"📋 <b>Информация о подписке</b>\n\n"
                f"Тип: <b>{type_label}</b>\n"
                f"Статус: <b>{status}</b>\n"
                f"Начало: <b>{start_time}</b>\n"
                f"Окончание: <b>{end_time}</b>\n\n"
                "Нажмите 'Подписаться', чтобы активировать новую подписку.",
                parse_mode="HTML"
            )
