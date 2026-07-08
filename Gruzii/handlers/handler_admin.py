from functools import wraps

from aiogram import F
from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import ADMIN_USER_ID
from states import AdminStates
from subscription import subscription_manager
from menu import admin_panel_keyboard, remove_user_keyboard, disabling_subscriptions_keyboard

import logging

logger = logging.getLogger(__name__)

router = Router()


def admin_only(handler):
    """ Декоратор для проверки прав администратора. """

    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        if user_id != ADMIN_USER_ID:
            if isinstance(event, Message):
                await event.answer("❌ У вас нет прав администратора")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ У вас нет прав администратора", show_alert=True)
            return

        return await handler(event, *args, **kwargs)

    return wrapper


@router.message(F.text == "🛠 Админ-панель")
@admin_only
async def admin_panel_button(message: Message):
    """Обработчик кнопки админ-панели"""
    keyboard = admin_panel_keyboard()
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "admin_delete_user")
@admin_only
async def admin_delete_user(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки удаления пользователя - запрашиваем ID"""
    await callback.answer()

    await callback.message.answer(
        "🗑 <b>Удаление пользователя</b>\n\n"
        "Введите ID пользователя для удаления:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_delete_user_id)


@router.message(StateFilter(AdminStates.waiting_for_delete_user_id))
@admin_only
async def process_delete_user(message: Message, state: FSMContext):
    """Получаем ID пользователя и запрашиваем подтверждение"""
    try:
        target_user_id = int(message.text.strip())

        if target_user_id == ADMIN_USER_ID:
            await message.answer(
                "❌ <b>Нельзя удалить самого себя!</b>",
                parse_mode="HTML"
            )
            await state.clear()
            return

        await state.update_data(target_user_id=target_user_id)

        keyboard = remove_user_keyboard(target_user_id)
        await message.answer(
            f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
            f"Вы действительно хотите удалить пользователя <code>{target_user_id}</code>?\n"
            f"Будет удалена подписка и запись в базе данных.\n"
            f"Это действие нельзя отменить!",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введите ID пользователя (только цифры):",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("confirm_delete_"))
@admin_only
async def confirm_delete_user(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления пользователя"""
    await callback.answer()

    target_user_id = int(callback.data.split("_")[-1])
    result = subscription_manager.delete_user(target_user_id)

    if result["success"]:
        await callback.message.edit_text(
            f"✅ <b>Пользователь удалён!</b>\n\n"
            f"ID: <code>{target_user_id}</code>\n"
            f"Подписка удалена: {'Да' if result['subscription_deleted'] else 'Нет'}",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ {result['message']}",
            parse_mode="HTML"
        )

    await state.clear()


@router.callback_query(F.data == "admin_give_subscription")
@admin_only
async def admin_give_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки выдачи подписки"""
    await callback.answer()

    await callback.message.answer(
        "💎 <b>Выдача платной подписки</b>\n\n"
        "Введите ID пользователя и количество дней (через пробел):\n"
        "Пример: <code>123456789 365</code>\n\n"
        "Или только ID для подписки на 1 год (365 дней)",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_subscription_id)


@router.message(StateFilter(AdminStates.waiting_for_subscription_id))
@admin_only
async def process_give_subscription(message: Message, state: FSMContext):
    """Обработка выдачи подписки"""
    try:
        parts = message.text.strip().split()
        target_user_id = int(parts[0])
        days = int(parts[1]) if len(parts) > 1 else 365

        subscription = subscription_manager.activate_paid_subscription(target_user_id, days)
        end_time = subscription["end_time"].strftime("%d.%m.%Y %H:%M")

        await message.answer(
            f"✅ <b>Подписка выдана!</b>\n\n"
            f"Пользователь: <code>{target_user_id}</code>\n"
            f"Длительность: <b>{days} дней</b>\n"
            f"Действует до: <b>{end_time}</b>",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Пример: <code>123456789 365</code>",
            parse_mode="HTML"
        )

    await state.clear()


@router.callback_query(F.data == "admin_take_subscription")
@admin_only
async def admin_take_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки отключения подписки"""
    await callback.answer()

    await callback.message.answer(
        "❌ <b>Отключение подписки</b>\n\n"
        "Введите ID пользователя:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_take_subscription_id)


@router.callback_query(F.data == "admin_disable_all")
@admin_only
async def admin_disable_all(callback: CallbackQuery):
    """Обработчик кнопки отключения всех подписок"""
    await callback.answer()

    keyboard = disabling_subscriptions_keyboard()

    await callback.message.answer(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы действительно хотите отключить ВСЕ подписки?\n"
        "Это действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "confirm_disable_all")
@admin_only
async def confirm_disable_all(callback: CallbackQuery):
    """Подтверждение отключения всех подписок"""
    await callback.answer()

    count = subscription_manager.deactivate_all_user_subscriptions()

    await callback.message.edit_text(
        f"✅ <b>Все подписки отключены!</b>\n\n"
        f"Деактивировано подписок: <b>{count}</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_all_users")
@admin_only
async def admin_show_all_users(callback: CallbackQuery):
    """Показать всех пользователей с подписками"""
    await callback.answer()

    users = subscription_manager.get_all_users_with_subscriptions()

    if not users:
        await callback.message.answer("👥 Нет пользователей с подписками")
        return

    text = "👥 <b>Все пользователи с подписками:</b>\n\n"
    for user in users:
        sub_type = "💎" if user["subscription_type"].value == "paid" else "🎁"
        status = "✅" if user["is_active"] else "❌"
        text += (
            f"{status} {sub_type} ID: <code>{user['user_id']}</code>\n"
            f"   До: {user['end_time'].strftime('%d.%m.%Y %H:%M')} | "
            f"Осталось: {user['time_remaining']}\n\n"
        )

    await callback.message.answer(
        text,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_stats")
@admin_only
async def admin_show_stats(callback: CallbackQuery):
    """Показать статистику"""
    await callback.answer()

    users = subscription_manager.get_all_users_with_subscriptions()

    total = len(users)
    active = sum(1 for u in users if u["is_active"])
    active_trial = sum(1 for u in users if u["is_active"] and u["subscription_type"].value == "trial")
    active_paid = sum(1 for u in users if u["is_active"] and u["subscription_type"].value == "paid")

    text = (
        f"📊 <b>Статистика подписок:</b>\n\n"
        f"Всего пользователей: <b>{total}</b>\n"
        f"Активных подписок: <b>{active}</b>\n\n"
        f"💎 Платных (активных): <b>{active_paid}</b>\n"
        f"🎁 Пробных (активных): <b>{active_trial}</b>\n"
        f"Истекших: <b>{total - active}</b>"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML"
    )


@router.message(StateFilter(AdminStates.waiting_for_take_subscription_id))
@admin_only
async def process_take_subscription(message: Message, state: FSMContext):
    """Обработка отключения подписки"""
    try:
        target_user_id = int(message.text.strip())
        success = subscription_manager.deactivate_subscription(target_user_id)

        if success:
            await message.answer(
                f"✅ <b>Подписка отключена!</b>\n\n"
                f"Пользователь: <code>{target_user_id}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ У пользователя <code>{target_user_id}</code> нет активной подписки",
                parse_mode="HTML"
            )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введите ID пользователя:",
            parse_mode="HTML"
        )

    await state.clear()
