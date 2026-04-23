import asyncio
from typing import Dict, Any

from aiogram import F
from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from Gruzii.config import ADMIN_USER_ID
from Gruzii.menu import (get_main_menu, get_type_keyboard, get_radius_keyboard,
                         get_to_type_keyboard, get_add_route_keyboard, get_search_controls)
from Gruzii.states import SearchStates
from Gruzii.storage import get_type_id
from Gruzii.subscription import subscription_manager
from Gruzii.search_cargo import search_cargo_for_user
from Gruzii.storage import tasks, active_searches

router = Router()


async def check_subscription_get_menu(user_id: int):
    is_admin = (user_id == ADMIN_USER_ID)
    has_subscription = subscription_manager.is_subscription_active(user_id)
    time_remaining = None
    if has_subscription:
        time_remaining = subscription_manager.get_formatted_time_remaining(user_id)

    return get_main_menu(
        has_subscription=has_subscription,
        subscription_time_remaining=time_remaining,
        is_admin=is_admin
    )


async def go_to_main_menu(message: Message, state: FSMContext):
    """Возвращает пользователя в главное меню"""
    user_id = message.from_user.id
    menu = await check_subscription_get_menu(user_id)
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=menu
    )
    await state.clear()


async def handle_radius(callback_query: CallbackQuery, state: FSMContext,
                        radius_type: str, next_state, custom_state, custom_prompt: str):
    data = callback_query.data
    if data == "radius_none":
        await state.update_data({f"{radius_type}_radius": None})
        await next_state(callback_query.message, state)
        await callback_query.answer()
    elif data == "radius_custom":
        await state.set_state(custom_state)
        await callback_query.message.edit_text(custom_prompt, parse_mode="HTML")
        await callback_query.answer()
    elif data.startswith("radius_"):
        km = int(data.split("_")[1])
        await state.update_data({f"{radius_type}_radius": km})
        await next_state(callback_query.message, state)
        await callback_query.answer()


async def handle_radius_custom_input(message: Message, state: FSMContext,
                                     radius_type: str, next_state):
    """Универсальный обработчик ручного ввода радиуса"""
    try:
        km = int(message.text.strip())
        if km <= 0:
            raise ValueError
        await state.update_data({f"{radius_type}_radius": km})
        await next_state(message, state)
    except ValueError:
        await message.answer("❌ Введите целое положительное число (например, 300):")


def create_route_from_state(data: Dict[str, Any], is_any_direction: bool = False) -> Dict[str, Any]:
    """Создает маршрут из данных состояния"""
    route = {
        'from_location': data['from_location'],
        'from_type': data['from_type'],
        'from_type_name': data.get('from_type_name', ''),
        'from_radius': data.get('from_radius'),
        'to_radius': data.get('to_radius'),
        'any_direction': is_any_direction,
    }

    if is_any_direction:
        route.update({
            'to_location': None,
            'to_type': None,
            'to_type_name': 'Любое направление',
        })
    else:
        route.update({
            'to_location': data['to_location'],
            'to_type': data['to_type'],
            'to_type_name': data.get('to_type_name', ''),
        })

    return route


async def add_route_and_show(message, state: FSMContext, is_any_direction: bool = False):
    """Добавляет маршрут и показывает список"""
    data = await state.get_data()
    routes = data.get('routes', [])

    route = create_route_from_state(data, is_any_direction)
    routes.append(route)
    await state.update_data(routes=routes)

    routes_text = "\n".join(
        f"  {i + 1}. {r['from_location']} → {r.get('to_location') or '🌐 Любоe'}"
        for i, r in enumerate(routes)
    )

    await state.set_state(SearchStates.adding_route)
    await message.answer(
        f"✅ Маршрут добавлен!\n\n"
        f"📋 <b>Текущие маршруты:</b>\n{routes_text}\n\n"
        "Добавить ещё маршрут или начать поиск?",
        parse_mode="HTML",
        reply_markup=get_add_route_keyboard()
    )


async def ask_to_type(message, state: FSMContext):
    """Переход к выбору типа пункта назначения."""
    await state.set_state(SearchStates.setting_to_type)
    await message.answer(
        "📍 <b>Шаг 2 из 4:</b> Куда доставляем?\n"
        "Выберите тип географической точки назначения\n"
        "или нажмите <b>«🌐 Любое направление»</b> — бот будет отслеживать все рейсы из этой точки:",
        parse_mode="HTML",
        reply_markup=get_to_type_keyboard()
    )


async def finish_route(message, state: FSMContext):
    """Завершает добавление маршрута (не любое направление)"""
    await add_route_and_show(message, state, is_any_direction=False)


@router.message(F.text.startswith("🔍 Найти грузы"))
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


@router.message(StateFilter(SearchStates.setting_from_type))
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
        await go_to_main_menu(message, state)
    else:
        await message.answer(
            "❌ Пожалуйста, используйте кнопки для выбора",
            reply_markup=get_type_keyboard()
        )


@router.message(StateFilter(SearchStates.setting_from_location))
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


@router.callback_query(StateFilter(SearchStates.setting_from_radius))
async def handle_from_radius(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await handle_radius(callback, state, "from", ask_to_type,
                        SearchStates.setting_from_radius_custom,
                        "✏️ Введите радиус отгрузки в километрах (целое число, например 300):")


@router.message(StateFilter(SearchStates.setting_from_radius_custom))
async def handle_from_radius_custom(message: Message, state: FSMContext):
    await handle_radius_custom_input(message, state, "from", finish_route)


@router.message(StateFilter(SearchStates.setting_to_location))
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


@router.callback_query(StateFilter(SearchStates.setting_to_radius))
async def handle_to_radius(callback: CallbackQuery, state: FSMContext):
    data_cb = callback.data

    if data_cb == "radius_none":
        await state.update_data(to_radius=None)
        await finish_route(callback.message, state)
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
        await finish_route(callback.message, state)
        await callback.answer()


@router.message(StateFilter(SearchStates.setting_to_type))
async def set_to_type(message: Message, state: FSMContext):
    text = message.text.replace("🏙️ ", "").replace("🌍 ", "").replace("🗺️ ", "").replace("🌐 ", "")

    if text == "Любое направление":
        await add_route_and_show(message, state, is_any_direction=True)
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
        await state.set_state(SearchStates.setting_from_location)
        await message.answer(
            "📍 Введите название пункта отправления:",
            parse_mode="HTML",
            reply_markup=await check_subscription_get_menu(message.from_user.id)
        )


@router.callback_query(F.data == "add_another_route", StateFilter(SearchStates.adding_route))
async def add_another_route(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить ещё один маршрут"""
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await state.set_state(SearchStates.setting_from_type)
    await callback.message.answer(
        "📍 <b>Новый маршрут</b>\n\n"
        "Откуда отправляем груз?\n"
        "Выберите тип географической точки:",
        parse_mode="HTML",
        reply_markup=get_type_keyboard()
    )


@router.callback_query(F.data == "confirm_search_start", StateFilter(SearchStates.adding_route))
async def confirm_search_from_add_route(callback: CallbackQuery, state: FSMContext):
    """Начать поиск из меню добавления маршрута"""
    data = await state.get_data()
    user_id = callback.from_user.id
    active_searches[user_id] = True

    routes = data.get('routes', [])
    if routes:
        routes_text = "\n".join(
            f"  {i + 1}. {r['from_location']} → {r['to_location'] if r['to_location'] else '🌐 Любое направление'} "
            for i, r in enumerate(routes)
        )
        search_info = f"🔍 Ищу грузы:\n{routes_text}"
    else:
        search_info = f"🔍 Ищу грузы: {data['from_location']} → {data['to_location'] if data.get('to_location') else '🌐 Любое направление'}"

    filters_applied = []
    if data.get('weight_min'):
        filters_applied.append(f"вес от {data['weight_min']} т")
    if data.get('weight_max'):
        filters_applied.append(f"до {data['weight_max']} т")
    if data.get('volume_from'):
        filters_applied.append(f"объем от {data['volume_from']} м³")
    if data.get('volume_to'):
        filters_applied.append(f"объем до {data['volume_to']} м³")
    if filters_applied:
        search_info += f"\n🎯 Фильтры: {', '.join(filters_applied)}"

    await callback.message.edit_text(
        f"🚀 <b>Поиск запущен!</b>\n\n{search_info}\n",
        parse_mode="HTML"
    )
    await state.set_state(SearchStates.searching)
    await callback.message.answer(
        "<b>⏳ Первые результаты появятся через несколько секунд...</b>",
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
            data.get('weight_min'),
            data.get('weight_max'),
            callback.message,
            data.get('volume_from'),
            data.get('volume_to'),
            active_searches,
            data.get('car_load_type_ids'),
            data.get('car_type_ids', []),
            from_radius=route.get('from_radius'),
            to_radius=route.get('to_radius'),
            any_direction=route.get('any_direction', False), ))
        tasks[user_id] = task
