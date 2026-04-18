import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from filter import *
from menu import *
from search_cargo import search_cargo_for_user
from storage import *
from handler_add_user import router
from subscription import subscription_manager
from states import AdminStates

logging.basicConfig(level=logging.INFO)

tasks = {}

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
active_searches = {}

dp.include_router(router)


@dp.message(Command("start"))
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
                reply_markup=get_main_menu(has_subscription=True, subscription_time_remaining=time_remaining, is_admin=is_admin)
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


@dp.message(Command("subscription"))
async def check_subscription(message: Message, state: FSMContext):
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


# ==================== АДМИН-КОМАНДЫ ====================

@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    """Админ-панель для управления подписками"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_all_users")],
        [InlineKeyboardButton(text="✅ Выдать подписку", callback_data="admin_give_subscription")],
        [InlineKeyboardButton(text="❌ Забрать подписку", callback_data="admin_take_subscription")],
        [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="admin_delete_user")],
        [InlineKeyboardButton(text="🔒 Отключить всем", callback_data="admin_disable_all")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])
    
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.message(Command("give_subscription"))
async def cmd_give_subscription(message: Message, state: FSMContext):
    """Выдать платную подписку пользователю"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    await message.answer(
        "💎 <b>Выдача платной подписки</b>\n\n"
        "Введите ID пользователя и количество дней (через пробел):\n"
        "Пример: <code>123456789 365</code>\n\n"
        "Или только ID для подписки на 1 год (365 дней)",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_subscription_id)


@dp.message(StateFilter(AdminStates.waiting_for_subscription_id))
async def process_give_subscription(message: Message, state: FSMContext):
    """Обработка выдачи подписки"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
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


@dp.message(Command("take_subscription"))
async def cmd_take_subscription(message: Message, state: FSMContext):
    """Забрать подписку у пользователя"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    await message.answer(
        "❌ <b>Отключение подписки</b>\n\n"
        "Введите ID пользователя:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_take_subscription_id)


@dp.message(StateFilter(AdminStates.waiting_for_take_subscription_id))
async def process_take_subscription(message: Message, state: FSMContext):
    """Обработка отключения подписки"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
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


@dp.message(StateFilter(AdminStates.waiting_for_delete_user_id))
async def process_delete_user(message: Message, state: FSMContext):
    """Обработка удаления пользователя"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    try:
        target_user_id = int(message.text.strip())
        
        if target_user_id == ADMIN_USER_ID:
            await message.answer(
                "❌ <b>Нельзя удалить самого себя!</b>",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"confirm_delete_{target_user_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
        
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
            "❌ Неверный формат. Введите ID пользователя:",
            parse_mode="HTML"
        )
    
    await state.clear()


@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_user(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления пользователя"""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    # Сразу отвечаем, чтобы убрать индикатор загрузки
    await callback.answer()
    
    # Извлекаем ID пользователя из callback_data
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


@dp.message(Command("disable_all"))
async def cmd_disable_all(message: Message, state: FSMContext):
    """Отключить все подписки"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Да, отключить всем", callback_data="confirm_disable_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    await message.answer(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы действительно хотите отключить ВСЕ подписки?\n"
        "Это действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "admin_give_subscription")
async def admin_give_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки выдачи подписки"""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await callback.answer()
    
    await callback.message.answer(
        "💎 <b>Выдача платной подписки</b>\n\n"
        "Введите ID пользователя и количество дней (через пробел):\n"
        "Пример: <code>123456789 365</code>\n\n"
        "Или только ID для подписки на 1 год (365 дней)",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_subscription_id)


@dp.callback_query(F.data == "admin_take_subscription")
async def admin_take_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки отключения подписки"""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await callback.answer()
    
    await callback.message.answer(
        "❌ <b>Отключение подписки</b>\n\n"
        "Введите ID пользователя:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_take_subscription_id)


@dp.callback_query(F.data == "admin_delete_user")
async def admin_delete_user(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки удаления пользователя"""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await callback.answer()
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    await callback.message.answer(
        "🗑 <b>Удаление пользователя</b>\n\n"
        "Введите ID пользователя для удаления:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_delete_user_id)


@dp.callback_query(F.data == "admin_disable_all")
async def admin_disable_all(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки отключения всех подписок"""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await callback.answer()
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Да, отключить всем", callback_data="confirm_disable_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    await callback.message.answer(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы действительно хотите отключить ВСЕ подписки?\n"
        "Это действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "confirm_disable_all")
async def confirm_disable_all(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отключения всех подписок"""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    # Сразу отвечаем, чтобы убрать индикатор загрузки
    await callback.answer()
    
    count = subscription_manager.deactivate_all_user_subscriptions()
    
    await callback.message.edit_text(
        f"✅ <b>Все подписки отключены!</b>\n\n"
        f"Деактивировано подписок: <b>{count}</b>",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "admin_all_users")
async def admin_show_all_users(callback: CallbackQuery, state: FSMContext):
    """Показать всех пользователей с подписками"""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    # Сразу отвечаем, чтобы убрать индикатор загрузки
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


@dp.callback_query(F.data == "admin_stats")
async def admin_show_stats(callback: CallbackQuery, state: FSMContext):
    """Показать статистику"""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    # Сразу отвечаем, чтобы убрать индикатор загрузки
    await callback.answer()
    
    users = subscription_manager.get_all_users_with_subscriptions()
    
    total = len(users)
    active = sum(1 for u in users if u["is_active"])
    trial = sum(1 for u in users if u["subscription_type"].value == "trial")
    paid = sum(1 for u in users if u["subscription_type"].value == "paid")
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


@dp.message(F.text == "📝 Подписаться")
async def subscribe_user(message: Message, state: FSMContext):
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
        # Пробная подписка уже использована
        await message.answer(
            "⚠️ <b>Пробная подписка уже использована</b>\n\n"
            "Ваш пробный период закончился.\n"
            "Для продолжения работы обратитесь к администратору\n"
            "для приобретения платной подписки.",
            parse_mode="HTML"
        )


@dp.message(F.text == "🛠 Админ-панель")
async def admin_panel_button(message: Message, state: FSMContext):
    """Обработчик кнопки админ-панели"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_all_users")],
        [InlineKeyboardButton(text="✅ Выдать подписку", callback_data="admin_give_subscription")],
        [InlineKeyboardButton(text="❌ Забрать подписку", callback_data="admin_take_subscription")],
        [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="admin_delete_user")],
        [InlineKeyboardButton(text="🔒 Отключить всем", callback_data="admin_disable_all")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])
    
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.message(F.text.startswith("🔍 Найти грузы"))
async def start_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_USER_ID)

    # Проверяем подписку
    if not is_admin and not subscription_manager.is_subscription_active(user_id):
        await message.answer(
            "⚠️ <b>Подписка истекла</b>\n\n"
            "Ваша подписка закончилась. Для продолжения работы\n"
            "нажмите 'Подписаться' для активации новой подписки.",
            parse_mode="HTML",
            reply_markup=get_main_menu(has_subscription=False, is_admin=is_admin)
        )
        return
    
    await state.set_state(SearchStates.setting_from_type)
    await message.answer(
        "🎯 <b>Настройка поиска грузов</b>\n\n"
        "📍 <b>Шаг 1 из 4:</b> Откуда отправляем груз?\n"
        "Выберите тип географической точки:",
        parse_mode="HTML",
        reply_markup=get_type_keyboard()
    )


@dp.message(StateFilter(SearchStates.setting_from_type))
async def set_from_type(message: Message, state: FSMContext):
    text = message.text.replace("🏙️ ", "").replace("🌍 ", "").replace("🗺️ ", "")
    if text in ["Город", "Регион", "Страна"]:
        await state.update_data(from_type=get_type_id(text), from_type_name=text)
        await state.set_state(SearchStates.setting_from_location)
        emoji_map = {"Город": "🏙️", "Регион": "🌍", "Страна": "🗺️"}
        await message.answer(
            f"✅ Выбрано: <b>{emoji_map.get(text, '')} {text}</b>\n\n"
            f"📍 Введите название пункта отправления ({text.lower()}):",
            parse_mode="HTML"
        )
    elif text == "🔙 Назад":
        # Проверяем подписку
        user_id = message.from_user.id
        has_subscription = subscription_manager.is_subscription_active(user_id)
        time_remaining = None
        if has_subscription:
            time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
        is_admin = (user_id == ADMIN_USER_ID)
            
        await message.answer(
            "🏠 <b>Главное меню</b>\n\nВыберите действие:",
            reply_markup=get_main_menu(has_subscription=has_subscription, subscription_time_remaining=time_remaining, is_admin=is_admin),
            parse_mode="HTML"
        )
        await state.clear()
    else:
        await message.answer(
            "❌ Пожалуйста, используйте кнопки для выбора",
            reply_markup=get_type_keyboard()
        )


@dp.message(StateFilter(SearchStates.setting_from_location))
async def set_from_location(message: Message, state: FSMContext):
    location = message.text.strip().title()
    await state.update_data(from_location=location)
    await state.set_state(SearchStates.setting_from_radius)
    await message.answer(
        f"✅ Пункт отправления: <b>{location}</b>\n\n"
        "📍 <b>Шаг 1б:</b> Укажите радиус поиска от этой точки\n"
        "(например, «Челябинск, радиус 300 км» — бот найдёт грузы из города и его окрестностей):",
        parse_mode="HTML",
        reply_markup=get_radius_keyboard()
    )


@dp.callback_query(StateFilter(SearchStates.setting_from_radius))
async def handle_from_radius(callback: CallbackQuery, state: FSMContext):
    data_cb = callback.data

    if data_cb == "radius_none":
        await state.update_data(from_radius=None)
        await _ask_to_type(callback.message, state)
        await callback.answer()

    elif data_cb == "radius_custom":
        await state.set_state(SearchStates.setting_from_radius_custom)
        await callback.message.edit_text(
            "✏️ Введите радиус отгрузки в километрах (целое число, например 300):",
            parse_mode="HTML"
        )
        await callback.answer()

    elif data_cb.startswith("radius_"):
        km = int(data_cb.split("_")[1])
        await state.update_data(from_radius=km)
        await _ask_to_type(callback.message, state)
        await callback.answer()


@dp.message(StateFilter(SearchStates.setting_from_radius_custom))
async def handle_from_radius_custom(message: Message, state: FSMContext):
    try:
        km = int(message.text.strip())
        if km <= 0:
            raise ValueError
        await state.update_data(from_radius=km)
        await _ask_to_type(message, state)
    except ValueError:
        await message.answer("❌ Введите целое положительное число (например, 300):")


async def _ask_to_type(message, state: FSMContext):
    """Переход к выбору типа пункта назначения."""
    await state.set_state(SearchStates.setting_to_type)
    await message.answer(
        "📍 <b>Шаг 2 из 4:</b> Куда доставляем?\n"
        "Выберите тип географической точки назначения\n"
        "или нажмите <b>«🌐 Любое направление»</b> — бот будет отслеживать все рейсы из этой точки:",
        parse_mode="HTML",
        reply_markup=get_to_type_keyboard()  # ← новая клавиатура с кнопкой «Любое направление»
    )


@dp.message(StateFilter(SearchStates.setting_to_type))
async def set_to_type(message: Message, state: FSMContext):
    text = message.text.replace("🏙️ ", "").replace("🌍 ", "").replace("🗺️ ", "").replace("🌐 ", "")

    # ── НОВОЕ: режим «Любое направление» ──────────────────────────────────────
    if text == "Любое направление":
        await state.update_data(
            any_direction=True,
            to_location=None,
            to_type=None,
            to_type_name="Любое направление",
            to_radius=None,
        )
        # Сразу сохраняем маршрут (без точки назначения) и показываем итог
        data = await state.get_data()
        routes = data.get('routes', [])
        routes.append({
            'from_location': data['from_location'],
            'from_type': data['from_type'],
            'from_type_name': data.get('from_type_name', ''),
            'from_radius': data.get('from_radius'),
            'to_location': None,
            'to_type': None,
            'to_type_name': 'Любое направление',
            'to_radius': None,
            'any_direction': True,
        })
        await state.update_data(routes=routes)

        routes_text = "\n".join(
            f"  {i + 1}. {r['from_location']} → {r.get('to_location') or '🌐 Любое'}"
            for i, r in enumerate(routes)
        )
        await state.set_state(SearchStates.adding_route)
        from menu import get_add_route_keyboard
        await message.answer(
            f"✅ Маршрут добавлен!\n\n"
            f"📋 <b>Текущие маршруты:</b>\n{routes_text}\n\n"
            "Добавить ещё маршрут или начать поиск?",
            parse_mode="HTML",
            reply_markup=get_add_route_keyboard()
        )
        return

    if text in ["Город", "Регион", "Страна"]:
        await state.update_data(to_type=get_type_id(text), to_type_name=text, any_direction=False)
        await state.set_state(SearchStates.setting_to_location)
        emoji_map = {"Город": "🏙️", "Регион": "🌍", "Страна": "🗺️"}
        await message.answer(
            f"✅ Выбрано: <b>{emoji_map.get(text, '')} {text}</b>\n\n"
            f"🏁 Введите название пункта назначения ({text.lower()}):",
            parse_mode="HTML"
        )
    elif text == "🔙 Назад":
        user_id = message.from_user.id
        has_subscription = subscription_manager.is_subscription_active(user_id)
        time_remaining = None
        if has_subscription:
            time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
        is_admin = (user_id == ADMIN_USER_ID)

        await state.set_state(SearchStates.setting_from_location)
        await message.answer(
            "📍 Введите название пункта отправления:",
            parse_mode="HTML",
            reply_markup=get_main_menu(
                has_subscription=has_subscription,
                subscription_time_remaining=time_remaining,
                is_admin=is_admin
            )
        )

@dp.message(StateFilter(SearchStates.setting_to_location))
async def set_to_location(message: Message, state: FSMContext):
    location = message.text.strip().title()
    await state.update_data(to_location=location)
    await state.set_state(SearchStates.setting_to_radius)
    await message.answer(
        f"✅ Пункт назначения: <b>{location}</b>\n\n"
        "🏁 <b>Шаг 3б:</b> Радиус у пункта назначения?",
        parse_mode="HTML",
        reply_markup=get_radius_keyboard()
    )


@dp.callback_query(StateFilter(SearchStates.setting_to_radius))
async def handle_to_radius(callback: CallbackQuery, state: FSMContext):
    data_cb = callback.data

    if data_cb == "radius_none":
        await state.update_data(to_radius=None)
        await _finish_route(callback.message, state)
        await callback.answer()

    elif data_cb == "radius_custom":
        await state.set_state(SearchStates.setting_to_radius_custom)
        await callback.message.edit_text(
            "✏️ Введите радиус выгрузки в километрах (целое число, например 150):",
            parse_mode="HTML"
        )
        await callback.answer()

    elif data_cb.startswith("radius_"):
        km = int(data_cb.split("_")[1])
        await state.update_data(to_radius=km)
        await _finish_route(callback.message, state)
        await callback.answer()


@dp.message(StateFilter(SearchStates.setting_to_radius_custom))
async def handle_to_radius_custom(message: Message, state: FSMContext):
    try:
        km = int(message.text.strip())
        if km <= 0:
            raise ValueError
        await state.update_data(to_radius=km)
        await _finish_route(message, state)
    except ValueError:
        await message.answer("❌ Введите целое положительное число (например, 150):")


async def _finish_route(message, state: FSMContext):
    """Сохраняем маршрут и показываем список маршрутов."""
    data = await state.get_data()
    routes = data.get('routes', [])
    routes.append({
        'from_location': data['from_location'],
        'from_type': data['from_type'],
        'from_type_name': data.get('from_type_name', ''),
        'from_radius': data.get('from_radius'),
        'to_location': data['to_location'],
        'to_type': data['to_type'],
        'to_type_name': data.get('to_type_name', ''),
        'to_radius': data.get('to_radius'),
        'any_direction': False,
    })
    await state.update_data(routes=routes)

    routes_text = "\n".join(
        f"  {i + 1}. {r['from_location']} → {r.get('to_location') or '🌐 Любое'}"
        for i, r in enumerate(routes)
    )
    await state.set_state(SearchStates.adding_route)
    from menu import get_add_route_keyboard
    await message.answer(
        f"✅ Маршрут добавлен!\n\n"
        f"📋 <b>Текущие маршруты:</b>\n{routes_text}\n\n"
        "Добавить ещё маршрут или начать поиск?",
        parse_mode="HTML",
        reply_markup=get_add_route_keyboard()
    )

@dp.callback_query(StateFilter(WeightStates.setting_weight))
async def handle_weight_range(callback: CallbackQuery, state: FSMContext):
    await process_weight_input(callback, state, callback.data)


@dp.message(StateFilter(WeightStates.setting_weight_min, WeightStates.setting_weight_max))
async def handle_weight_value(message: Message, state: FSMContext):
    await process_weight_value(message, state)


@dp.callback_query(StateFilter(VolumeStates.setting_volume))
async def handle_volume_range(callback: CallbackQuery, state: FSMContext):
    await process_volume_input(callback, state, callback.data)


@dp.message(StateFilter(VolumeStates.setting_volume_min, VolumeStates.setting_volume_max))
async def handle_volume_value(message: Message, state: FSMContext):
    await process_volume_value(message, state)


@dp.callback_query(F.data.startswith("filter_"))
async def handle_filter_button(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки '⚙️ Фильтр'"""
    await start_filter_setup(callback, state)


@dp.callback_query(StateFilter(FilterStates.setting_filters))
async def handle_filter_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор фильтров в состоянии настройки"""
    await process_filter_selection(callback, state)


@dp.callback_query(StateFilter(CarLoadTypeStates.selecting_car_load_type))
async def handle_car_load_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа загрузки"""
    await process_car_load_type_selection(callback, state)


@dp.callback_query(F.data == "add_another_route", StateFilter(SearchStates.adding_route))
async def add_another_route(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить ещё один маршрут"""
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(SearchStates.setting_from_type)
    await callback.message.answer(
        "📍 <b>Новый маршрут</b>\n\n"
        "Откуда отправляем груз?\n"
        "Выберите тип географической точки:",
        parse_mode="HTML",
        reply_markup=get_type_keyboard()
    )


@dp.callback_query(F.data.startswith("filter_"), StateFilter(SearchStates.adding_route))
async def handle_filter_from_add_route(callback: CallbackQuery, state: FSMContext):
    """Фильтр из меню добавления маршрута"""
    await start_filter_setup(callback, state)


@dp.callback_query(F.data == "confirm_search_start", StateFilter(SearchStates.adding_route))
async def confirm_search_from_add_route(callback: CallbackQuery, state: FSMContext):
    """Начать поиск из меню добавления маршрута"""
    await state.set_state(SearchStates.confirming_search)
    data = await state.get_data()
    user_id = callback.from_user.id
    active_searches[user_id] = True

    routes = data.get('routes', [])
    if routes:
        routes_text = "\n".join(
            f"  {i+1}. {r['from_location']} → {r['to_location']}"
            for i, r in enumerate(routes)
        )
        search_info = f"🔍 Ищу грузы:\n{routes_text}"
    else:
        search_info = f"🔍 Ищу грузы: {data['from_location']} → {data['to_location']}"

    filters_applied = []
    if data.get('weight_from'):
        filters_applied.append(f"вес от {data['weight_from']} т")
    if data.get('weight_to'):
        filters_applied.append(f"до {data['weight_to']} т")
    if data.get('volume_from'):
        filters_applied.append(f"объем от {data['volume_from']} м³")
    if data.get('volume_to'):
        filters_applied.append(f"объем до {data['volume_to']} м³")
    if filters_applied:
        search_info += f"\n🎯 Фильтры: {', '.join(filters_applied)}"

    await callback.message.edit_text(
        f"🚀 <b>Поиск запущен!</b>\n\n{search_info}\n"
        "⏳ Первые результаты появятся через несколько секунд...",
        parse_mode="HTML"
    )
    await state.set_state(SearchStates.searching)
    await callback.message.answer(
        "🎛️ <b>Управление поиском:</b>",
        parse_mode="HTML",
        reply_markup=get_search_controls()
    )

    search_routes = routes if routes else [{
        'from_location': data['from_location'],
        'from_type': data['from_type'],
        'to_location': data['to_location'],
        'to_type': data['to_type'],
    }]

    for route in search_routes:
        task = asyncio.create_task(search_cargo_for_user(
          user_id,
          route['from_location'],
          route['from_type'],
          route.get('to_location'),
          route.get('to_type'),
          data.get('weight_from'),
          data.get('weight_to'),
          callback.message,
          data.get('volume_from'),
          data.get('volume_to'),
          active_searches,
          data.get('car_load_type_ids'),
          from_radius=route.get('from_radius'),
          to_radius=route.get('to_radius'),
          any_direction=route.get('any_direction', False),))
        tasks[user_id] = task

@dp.callback_query(F.data == "confirm_search_start", StateFilter(SearchStates.confirming_search))
async def confirm_search(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    active_searches[user_id] = True

    routes = data.get('routes', [])

    # Формируем текст с маршрутами
    if routes:
        routes_text = "\n".join(
            f"  {i+1}. {r['from_location']} → {r['to_location']}"
            for i, r in enumerate(routes)
        )
        search_info = f"🔍 Ищу грузы:\n{routes_text}"
    else:
        search_info = f"🔍 Ищу грузы: {data['from_location']} → {data['to_location']}"

    filters_applied = []
    if data.get('weight_from'):
        filters_applied.append(f"вес от {data['weight_from']} т")
    if data.get('weight_to'):
        filters_applied.append(f"до {data['weight_to']} т")
    if data.get('volume_from'):
        filters_applied.append(f"объем от {data['volume_from']} м³")
    if data.get('volume_to'):
        filters_applied.append(f"объем до {data['volume_to']} м³")
    if filters_applied:
        search_info += f"\n🎯 Фильтры: {', '.join(filters_applied)}"

    await callback.message.edit_text(
        f"🚀 <b>Поиск запущен!</b>\n\n{search_info}\n"
        "⏳ Первые результаты появятся через несколько секунд...",
        parse_mode="HTML"
    )
    await state.set_state(SearchStates.searching)
    await callback.message.answer(
        "🎛️ <b>Управление поиском:</b>",
        parse_mode="HTML",
        reply_markup=get_search_controls()
    )

    # Запускаем поиск для каждого маршрута
    search_routes = routes if routes else [{
        'from_location': data['from_location'],
        'from_type': data['from_type'],
        'to_location': data['to_location'],
        'to_type': data['to_type'],
    }]

    for route in search_routes:
        logging.info(
            f"Поиск для user_id={user_id}: from={route['from_location']}, to={route['to_location']}, "
            f"weight_from={data.get('weight_from')}, weight_to={data.get('weight_to')}, "
            f"volume_from={data.get('volume_from')}, volume_to={data.get('volume_to')}"
        )
        await asyncio.create_task(search_cargo_for_user(
            user_id,
            route['from_location'],
            route['from_type'],
            route['to_location'],
            route['to_type'],
            data.get('weight_from'),
            data.get('weight_to'),
            callback.message,
            data.get('volume_from'),
            data.get('volume_to'),
            active_searches,
            data.get('car_load_type_ids'),
            from_radius=route.get('from_radius'),
            to_radius=route.get('to_radius'),
            any_direction=route.get('any_direction', False),
        ))


@dp.callback_query(F.data == "cancel")
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
        reply_markup=get_main_menu(has_subscription=has_subscription, subscription_time_remaining=time_remaining, is_admin=is_admin)
    )
    await state.clear()


@dp.message(F.text == "⛔ Остановить")
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
        reply_markup=get_main_menu(has_subscription=has_subscription, subscription_time_remaining=time_remaining, is_admin=is_admin)
    )


@dp.message(F.text == "🔙 Главное меню")
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
        reply_markup=get_main_menu(has_subscription=has_subscription, subscription_time_remaining=time_remaining, is_admin=is_admin)
    )


@dp.callback_query(F.data == "stop_search")
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
        reply_markup=get_main_menu(has_subscription=has_subscription, subscription_time_remaining=time_remaining, is_admin=is_admin)
    )


async def main():
    logging.info("🚀 Запуск бота")
    session = AiohttpSession(timeout=150)
    bot = Bot(token=telegram_token, session=session)

    # Очищаем истекшие подписки при запуске
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