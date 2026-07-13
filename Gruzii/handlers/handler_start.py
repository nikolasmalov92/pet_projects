import asyncio

from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram import F

from storage import (
    save_user, load_users, delete_processed, get_user_presets,
    tasks, active_searches, search_paused,
)
from config import ADMIN_USER_ID
from subscription import subscription_manager
from menu import get_main_menu, get_active_search_keyboard, get_multi_select_presets_keyboard
from states import PresetStates

import logging

logger = logging.getLogger(__name__)

router = Router()

message_start = """
🚚 <b>Добро пожаловать, {first_name}!</b>

🎁 <b>24 часа полного доступа в подарок</b>

<b><u>Что вы получаете:</u></b>
⚡ Автомониторинг <b>каждые 3 минуты</b>
🔔 Мгновенные уведомления о новых грузах
🎯 Вы всегда видите заявки <b>первыми</b>

🚀 <b>Готовы перехватывать лучшие грузы?</b>

<b>Нажмите «Подписаться», чтобы активировать доступ</b>
"""


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()

    await asyncio.to_thread(save_user, user_id)

    allowed_users = await asyncio.to_thread(load_users)
    asyncio.create_task(asyncio.to_thread(delete_processed))

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
                message_start.format(first_name=first_name),
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
    user_tasks = tasks.pop(user_id, {})
    for task_info in user_tasks.values():
        if task_info.get('task') and not task_info['task'].done():
            task_info['task'].cancel()

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
    await callback.answer()
    await state.clear()


@router.message(F.text == "⛔ Остановить")
async def stop_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    active_searches[user_id] = False
    user_tasks = tasks.pop(user_id, {})
    for task_info in user_tasks.values():
        if task_info.get('task') and not task_info['task'].done():
            task_info['task'].cancel()

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


@router.message(F.text == "📊 Направления")
async def show_active_directions(message: Message, state: FSMContext):
    """Показывает inline-клавиатуру с активными направлениями."""
    user_id = message.from_user.id
    search_paused[user_id] = True
    user_tasks = tasks.get(user_id, {})

    if not user_tasks:
        await message.answer("Нет активных поисков.", parse_mode="HTML")
        return

    active_count = sum(
        1 for v in user_tasks.values()
        if v.get('task') and not v['task'].done()
    )
    await message.answer(
        f"📊 <b>Активные направления ({active_count}):</b>",
        parse_mode="HTML",
        reply_markup=get_active_search_keyboard(user_tasks)
    )


@router.message(F.text == "➕ Добавить")
async def add_direction_from_keyboard(message: Message, state: FSMContext):
    """Показывает список пресетов для добавления нового направления."""
    user_id = message.from_user.id
    search_paused[user_id] = True

    if not tasks.get(user_id):
        await message.answer("Сначала запустите поиск.", parse_mode="HTML")
        return

    presets = get_user_presets(user_id)
    if not presets:
        await message.answer(
            "Нет сохранённых фильтров. Сначала создайте хотя бы один.",
            parse_mode="HTML"
        )
        return

    user_tasks = tasks.get(user_id, {})
    active_preset_ids = {
        v.get('preset_id') for v in user_tasks.values()
        if v.get('preset_id')
    }
    available = [p for p in presets if p['id'] not in active_preset_ids]

    if not available:
        await message.answer("Все направления уже активны!", parse_mode="HTML")
        return

    available_ids = [p['id'] for p in available]
    await state.update_data(selected_preset_ids=available_ids)
    await message.answer(
        "➕ <b>Добавить направление в поиск:</b>\n\n"
        "Выберите фильтр из сохранённых:",
        parse_mode="HTML",
        reply_markup=get_multi_select_presets_keyboard(available, set(available_ids))
    )
    await state.set_state(PresetStates.selecting_preset)


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
    user_tasks = tasks.pop(user_id, {})
    for task_info in user_tasks.values():
        if task_info.get('task') and not task_info['task'].done():
            task_info['task'].cancel()

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
    await callback.answer()


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📘 <b>Инструкция по использованию бота</b>\n\n"
        "🎥 Видео-инструкция:\n"
        "https://disk.yandex.ru/i/Uvju7uyCycpXJQ\n\n"
        "Если останутся вопросы — пишите @vakhtang_p",
        parse_mode="HTML"
    )


@router.message(Command("tariffs"))
async def tariffs_command(message: Message):
    await message.answer(
        "💼 <b>Тарифы</b>\n\n"
        "📅 1 месяц — <b>1 000₽</b>\n"
        "📅 3 месяца — <b>2 850₽</b> (950₽/мес) — 💰 экономия 5%\n"
        "📅 6 месяцев — <b>5 100₽</b> (850₽/мес) — 💰 экономия 15%\n"
        "📅 12 месяцев — <b>8 400₽</b> (700₽/мес) — 💰 экономия 30%\n\n"
        "📲 <b>Для подключения напишите:</b> @vakhtang_p",
        parse_mode="HTML"
    )


@router.message(Command("contacts"))
async def contacts_command(message: Message):
    await message.answer(
        "📞 <b>Контакты администратора</b>\n\n"
        "Если вам нужна помощь, подключение подписки или есть вопросы по работе бота — пишите:\n\n"
        "💬 <b>@vakhtang_p</b>",
        parse_mode="HTML"
    )
