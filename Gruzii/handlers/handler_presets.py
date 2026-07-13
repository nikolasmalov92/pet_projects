import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_USER_ID
from states import SearchStates, PresetStates, FilterStates
from storage import (
    save_filter_preset, get_user_presets, get_preset_by_id,
    delete_preset, active_searches, tasks, search_paused,
)
from menu import (
    get_preset_actions_keyboard,
    get_add_route_keyboard, get_main_menu, get_search_controls,
    get_type_keyboard, get_multi_select_presets_keyboard,
    get_active_search_keyboard, get_direction_actions_keyboard,
    get_filter_setup_keyboard,
)
from search_cargo import search_cargo_for_user
from subscription import subscription_manager

logger = logging.getLogger(__name__)
router = Router()


# ── Показать список пресетов ─────────────────────────────────────────

@router.callback_query(F.data == "show_my_presets", StateFilter(SearchStates.adding_route))
async def show_my_presets(callback: CallbackQuery, state: FSMContext):
    """Показывает список сохранённых фильтров с мультивыбором."""
    user_id = callback.from_user.id
    presets = get_user_presets(user_id)

    if not presets:
        await callback.answer("У вас нет сохранённых фильтров", show_alert=True)
        return

    # По умолчанию все пресеты выбраны
    all_ids = [p['id'] for p in presets]
    await state.update_data(selected_preset_ids=all_ids)
    await callback.message.edit_text(
        "📂 <b>Ваши сохранённые фильтры:</b>\n\n"
        "Отметьте нужные фильтры и нажмите «Искать»:",
        parse_mode="HTML",
        reply_markup=get_multi_select_presets_keyboard(presets, set(all_ids))
    )
    await state.set_state(PresetStates.selecting_preset)
    await callback.answer()


# ── Мультивыбор пресетов ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("toggle_preset_"), StateFilter(PresetStates.selecting_preset))
async def toggle_preset_selection(callback: CallbackQuery, state: FSMContext):
    """Переключает выбор конкретного пресета."""
    preset_id = int(callback.data.replace("toggle_preset_", ""))
    data = await state.get_data()
    selected = set(data.get("selected_preset_ids", []))

    if preset_id in selected:
        selected.remove(preset_id)
    else:
        selected.add(preset_id)

    await state.update_data(selected_preset_ids=list(selected))

    presets = get_user_presets(callback.from_user.id)
    await callback.message.edit_reply_markup(
        reply_markup=get_multi_select_presets_keyboard(presets, selected)
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_all_presets", StateFilter(PresetStates.selecting_preset))
async def toggle_all_presets(callback: CallbackQuery, state: FSMContext):
    """Выбрать все / снять все пресеты."""
    data = await state.get_data()
    selected = set(data.get("selected_preset_ids", []))
    presets = get_user_presets(callback.from_user.id)
    preset_ids = {p['id'] for p in presets}

    if selected == preset_ids:
        selected = set()
    else:
        selected = preset_ids

    await state.update_data(selected_preset_ids=list(selected))
    await callback.message.edit_reply_markup(
        reply_markup=get_multi_select_presets_keyboard(presets, selected)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_single_preset_"), StateFilter(PresetStates.selecting_preset))
async def edit_single_preset_from_list(callback: CallbackQuery, state: FSMContext):
    """Открывает действия с отдельным пресетом из мультивыбора."""
    preset_id = int(callback.data.replace("edit_single_preset_", ""))
    user_id = callback.from_user.id
    preset = get_preset_by_id(preset_id, user_id)

    if not preset:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    await state.update_data(selected_preset_id=preset_id)

    text = _format_preset_info(preset)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_preset_actions_keyboard(preset_id)
    )
    await state.set_state(PresetStates.editing_preset)
    await callback.answer()


@router.callback_query(F.data == "start_multi_preset_search", StateFilter(PresetStates.selecting_preset))
async def start_multi_preset_search(callback: CallbackQuery, state: FSMContext):
    """Запускает параллельный поиск по выбранным пресетам (или добавляет к существующему)."""
    data = await state.get_data()
    selected_ids = data.get("selected_preset_ids", [])
    user_id = callback.from_user.id

    if not selected_ids:
        await callback.answer("Выберите хотя бы один фильтр", show_alert=True)
        return

    presets = []
    for pid in selected_ids:
        preset = get_preset_by_id(pid, user_id)
        if preset:
            presets.append(preset)

    if not presets:
        await callback.answer("Фильтры не найдены", show_alert=True)
        return

    # Проверяем, идёт ли уже поиск
    existing_tasks = tasks.get(user_id, {})
    is_adding = bool(existing_tasks)

    active_searches[user_id] = True

    # Формируем сводку
    lines = []
    for i, p in enumerate(presets, 1):
        to_text = p.get('to_location') or 'Любое'
        lines.append(f"  {i}. {p['from_location']} → {to_text}")
    routes_text = "\n".join(lines)

    if is_adding:
        await callback.message.edit_text(
            f"➕ <b>Добавлено {len(presets)} направлений:</b>\n\n{routes_text}",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"🚀 <b>Поиск запущен по {len(presets)} направлениям!</b>\n\n{routes_text}",
            parse_mode="HTML"
        )
        await state.set_state(SearchStates.searching)

    await callback.answer()

    # Показываем ReplyKeyboard с управлением
    if not is_adding:
        await callback.message.answer(
            "<b>⏳ Первые результаты появятся через несколько секунд...</b>",
            parse_mode="HTML",
            reply_markup=get_search_controls()
        )

    # Запускаем параллельные задачи
    user_tasks = existing_tasks
    tasks[user_id] = user_tasks

    for preset in presets:
        task_key = f"preset_{preset['id']}"
        task = asyncio.create_task(
            _run_preset_search(user_id, preset, callback.message)
        )
        user_tasks[task_key] = {
            'task': task,
            'name': preset['name'],
            'preset_id': preset['id'],
        }


async def _run_preset_search(user_id: int, preset: dict, message):
    """Запускает поиск по одному пресету."""
    try:
        await search_cargo_for_user(
            user_id,
            preset['from_location'],
            preset['from_type'],
            preset.get('to_location'),
            preset.get('to_type'),
            preset.get('weight_min'),
            preset.get('weight_max'),
            message,
            preset.get('volume_from'),
            preset.get('volume_to'),
            active_searches,
            preset.get('car_load_type_ids', []),
            preset.get('car_type_ids', []),
            from_radius=preset.get('from_radius'),
            to_radius=preset.get('to_radius'),
            any_direction=preset.get('any_direction', False),
        )
    except asyncio.CancelledError:
        logger.info(f"Поиск по пресету '{preset['name']}' для {user_id} отменён")
    except Exception as e:
        logger.error(f"Ошибка поиска по пресету '{preset['name']}' для {user_id}: {e}", exc_info=True)


# ── Управление направлениями во время поиска ──────────────────────────

@router.callback_query(F.data.startswith("view_direction_"))
async def view_direction(callback: CallbackQuery, state: FSMContext):
    """Показывает детали направления с кнопками действий."""
    task_key = callback.data.replace("view_direction_", "")
    user_id = callback.from_user.id
    user_tasks = tasks.get(user_id, {})
    task_info = user_tasks.get(task_key)

    if not task_info:
        await callback.answer("Направление не найдено", show_alert=True)
        return

    # Получаем информацию о направлении из пресета
    preset_id = task_info.get('preset_id')
    preset = None
    if preset_id:
        preset = get_preset_by_id(preset_id, user_id)

    name = task_info.get('name', task_key)
    is_active = task_info.get('task') and not task_info['task'].done()

    if preset:
        text = _format_preset_info(preset)
        status = "🟢 Активно" if is_active else "🔴 Остановлено"
        text = f"{status}\n\n{text}"
    else:
        status = "🟢 Активно" if is_active else "🔴 Остановлено"
        text = f"{status}\n\n📌 <b>{name}</b>"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_direction_actions_keyboard(task_key)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_active_directions")
async def back_to_active_directions(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку активных направлений."""
    user_id = callback.from_user.id
    search_paused[user_id] = False
    user_tasks = tasks.get(user_id, {})

    if not user_tasks:
        await callback.message.edit_text("Нет активных поисков.", parse_mode="HTML")
        await callback.answer()
        return

    active_count = sum(
        1 for v in user_tasks.values()
        if v.get('task') and not v['task'].done()
    )
    await callback.message.edit_text(
        f"📊 <b>Активные направления ({active_count}):</b>",
        parse_mode="HTML",
        reply_markup=get_active_search_keyboard(user_tasks)
    )
    await callback.answer()


@router.callback_query(F.data == "resume_search")
async def resume_search(callback: CallbackQuery, state: FSMContext):
    """Снимает паузу и закрывает inline-клавиатуру."""
    user_id = callback.from_user.id
    search_paused[user_id] = False
    await callback.message.edit_text("▶️ <b>Поиск продолжен</b>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("edit_direction_"))
async def edit_direction(callback: CallbackQuery, state: FSMContext):
    """Останавливает направление и открывает редактирование пресета."""
    task_key = callback.data.replace("edit_direction_", "")
    user_id = callback.from_user.id
    user_tasks = tasks.get(user_id, {})
    task_info = user_tasks.get(task_key)

    if not task_info:
        await callback.answer("Направление не найдено", show_alert=True)
        return

    # Останавливаем задачу
    task_info = user_tasks.pop(task_key, None)
    if task_info and task_info.get('task') and not task_info['task'].done():
        task_info['task'].cancel()

    if not user_tasks:
        tasks.pop(user_id, None)
        active_searches[user_id] = False

    # Получаем пресет для редактирования
    preset_id = task_info.get('preset_id')
    if not preset_id:
        await callback.answer("Нельзя редактировать это направление", show_alert=True)
        return

    preset = get_preset_by_id(preset_id, user_id)
    if not preset:
        await callback.answer("Пресет не найден", show_alert=True)
        return

    # Загружаем только фильтры пресета в state
    await state.update_data(
        editing_preset_id=preset_id,
        editing_task_key=task_key,
        weight_min=preset.get('weight_min'),
        weight_max=preset.get('weight_max'),
        volume_from=preset.get('volume_from'),
        volume_to=preset.get('volume_to'),
        car_load_type_ids=preset.get('car_load_type_ids', []),
        car_type_ids=preset.get('car_type_ids', []),
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование фильтров</b>\n\n"
        f"📌 {preset['name']}\n\n"
        f"Выберите параметр для изменения:",
        parse_mode="HTML",
        reply_markup=get_filter_setup_keyboard()
    )
    await state.set_state(FilterStates.setting_filters)
    await callback.answer()


@router.callback_query(F.data.startswith("delete_direction_"))
async def delete_direction(callback: CallbackQuery, state: FSMContext):
    """Останавливает и удаляет направление из активных."""
    task_key = callback.data.replace("delete_direction_", "")
    user_id = callback.from_user.id
    user_tasks = tasks.get(user_id, {})
    task_info = user_tasks.pop(task_key, None)

    if not task_info:
        await callback.answer("Направление не найдено", show_alert=True)
        return

    if task_info.get('task') and not task_info['task'].done():
        task_info['task'].cancel()

    name = task_info.get('name', task_key)

    if not user_tasks:
        tasks.pop(user_id, None)
        active_searches[user_id] = False

        has_subscription = subscription_manager.is_subscription_active(user_id)
        time_remaining = None
        if has_subscription:
            time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
        is_admin = (user_id == ADMIN_USER_ID)

        await callback.message.edit_text(
            f"🗑 <b>{name}</b> удалено.\n\nВсе направления остановлены.",
            parse_mode="HTML"
        )
        await callback.message.answer(
            "🏠 <b>Главное меню</b>",
            reply_markup=get_main_menu(has_subscription=has_subscription,
                                       subscription_time_remaining=time_remaining,
                                       is_admin=is_admin)
        )
        await state.clear()
    else:
        tasks[user_id] = user_tasks
        active_count = sum(
            1 for v in user_tasks.values()
            if v.get('task') and not v['task'].done()
        )
        await callback.message.edit_text(
            f"🗑 <b>{name}</b> удалено.",
            parse_mode="HTML"
        )
        await callback.message.answer(
            f"📊 <b>Активные направления ({active_count}):</b>",
            parse_mode="HTML",
            reply_markup=get_active_search_keyboard(user_tasks)
        )

    await callback.answer()


@router.callback_query(F.data.startswith("stop_direction_"))
async def stop_direction(callback: CallbackQuery, state: FSMContext):
    """Останавливает одно направление поиска."""
    task_key = callback.data.replace("stop_direction_", "")
    user_id = callback.from_user.id
    user_tasks = tasks.get(user_id, {})

    task_info = user_tasks.pop(task_key, None)
    if task_info and task_info.get('task') and not task_info['task'].done():
        task_info['task'].cancel()
        await callback.answer(f"⛔ {task_info.get('name', 'Направление')} остановлено")
    else:
        await callback.answer("Задача уже завершена")
        return

    if not user_tasks:
        # Все направления остановлены
        tasks.pop(user_id, None)
        active_searches[user_id] = False

        has_subscription = subscription_manager.is_subscription_active(user_id)
        time_remaining = None
        if has_subscription:
            time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
        is_admin = (user_id == ADMIN_USER_ID)

        await callback.message.edit_text(
            "⛔ <b>Все направления остановлены</b>",
            parse_mode="HTML"
        )
        await callback.message.answer(
            "🏠 <b>Главное меню</b>",
            reply_markup=get_main_menu(has_subscription=has_subscription,
                                       subscription_time_remaining=time_remaining,
                                       is_admin=is_admin)
        )
        await state.clear()
    else:
        tasks[user_id] = user_tasks
        await callback.message.edit_text(
            f"📊 <b>Активные направления ({len(user_tasks)}):</b>",
            parse_mode="HTML",
            reply_markup=get_active_search_keyboard(user_tasks)
        )


@router.callback_query(F.data == "stop_all_directions")
async def stop_all_directions(callback: CallbackQuery, state: FSMContext):
    """Останавливает все направления поиска."""
    user_id = callback.from_user.id
    active_searches[user_id] = False
    user_tasks = tasks.pop(user_id, {})

    for task_info in user_tasks.values():
        if task_info.get('task') and not task_info['task'].done():
            task_info['task'].cancel()

    has_subscription = subscription_manager.is_subscription_active(user_id)
    time_remaining = None
    if has_subscription:
        time_remaining = subscription_manager.get_formatted_time_remaining(user_id)
    is_admin = (user_id == ADMIN_USER_ID)

    await callback.message.edit_text(
        "⛔ <b>Все направления остановлены</b>",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "🏠 <b>Главное меню</b>",
        reply_markup=get_main_menu(has_subscription=has_subscription,
                                   subscription_time_remaining=time_remaining,
                                   is_admin=is_admin)
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "add_direction_during_search")
async def add_direction_during_search(callback: CallbackQuery, state: FSMContext):
    """Показывает список пресетов для добавления нового направления в активный поиск."""
    user_id = callback.from_user.id
    presets = get_user_presets(user_id)

    if not presets:
        await callback.answer("Нет сохранённых фильтров. Сначала создайте хотя бы один.", show_alert=True)
        return

    # Показываем только те пресеты, которые ещё не активны
    user_tasks = tasks.get(user_id, {})
    active_preset_ids = {
        v.get('preset_id') for v in user_tasks.values()
        if v.get('preset_id')
    }
    available = [p for p in presets if p['id'] not in active_preset_ids]

    if not available:
        await callback.answer("Все направления уже активны!", show_alert=True)
        return

    # По умолчанию все доступные пресеты выбраны
    available_ids = [p['id'] for p in available]
    await state.update_data(selected_preset_ids=available_ids)
    await callback.message.edit_text(
        "➕ <b>Добавить направление в поиск:</b>\n\n"
        "Выберите фильтр из сохранённых:",
        parse_mode="HTML",
        reply_markup=get_multi_select_presets_keyboard(available, set(available_ids))
    )
    await state.set_state(PresetStates.selecting_preset)
    await callback.answer()


# ── Выбор пресета — показ действий ───────────────────────────────────

@router.callback_query(F.data.startswith("use_preset_"), StateFilter(PresetStates.selecting_preset))
async def select_preset(callback: CallbackQuery, state: FSMContext):
    """Показывает действия с выбранным пресетом."""
    preset_id = int(callback.data.replace("use_preset_", ""))
    user_id = callback.from_user.id
    preset = get_preset_by_id(preset_id, user_id)

    if not preset:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    await state.update_data(selected_preset_id=preset_id)

    text = _format_preset_info(preset)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_preset_actions_keyboard(preset_id)
    )
    await state.set_state(PresetStates.editing_preset)
    await callback.answer()


# ── Использовать пресет для поиска ───────────────────────────────────

@router.callback_query(F.data.startswith("use_preset_"), StateFilter(PresetStates.editing_preset))
async def use_preset_for_search(callback: CallbackQuery, state: FSMContext):
    """Загружает пресет и запускает поиск."""
    preset_id = int(callback.data.replace("use_preset_", ""))
    user_id = callback.from_user.id
    preset = get_preset_by_id(preset_id, user_id)

    if not preset:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    # Загружаем параметры пресета в state
    await state.update_data(
        routes=[{
            'from_location': preset['from_location'],
            'from_type': preset['from_type'],
            'from_type_name': preset.get('from_type_name', ''),
            'from_radius': preset.get('from_radius'),
            'to_location': preset.get('to_location'),
            'to_type': preset.get('to_type'),
            'to_type_name': preset.get('to_type_name', ''),
            'to_radius': preset.get('to_radius'),
            'any_direction': preset.get('any_direction', False),
            'filters': {
                'weight_min': preset.get('weight_min'),
                'weight_max': preset.get('weight_max'),
                'volume_from': preset.get('volume_from'),
                'volume_to': preset.get('volume_to'),
                'car_load_type_ids': preset.get('car_load_type_ids', []),
                'car_type_ids': preset.get('car_type_ids', []),
            }
        }],
        weight_min=preset.get('weight_min'),
        weight_max=preset.get('weight_max'),
        volume_from=preset.get('volume_from'),
        volume_to=preset.get('volume_to'),
        car_load_type_ids=preset.get('car_load_type_ids', []),
        car_type_ids=preset.get('car_type_ids', []),
    )

    # Формируем текст информации
    to_text = preset.get('to_location') or '🌐 Любое направление'
    routes_text = f"  1. {preset['from_location']} → {to_text}"

    filters_applied = []
    if preset.get('weight_min'):
        filters_applied.append(f"вес от {preset['weight_min']} т")
    if preset.get('weight_max'):
        filters_applied.append(f"до {preset['weight_max']} т")
    if preset.get('volume_from'):
        filters_applied.append(f"объем от {preset['volume_from']} м³")
    if preset.get('volume_to'):
        filters_applied.append(f"объем до {preset['volume_to']} м³")

    search_info = f"🔍 Ищу грузы:\n{routes_text}"
    if filters_applied:
        search_info += f"\n🎯 Фильтры: {', '.join(filters_applied)}"

    user_id = callback.from_user.id
    active_searches[user_id] = True

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
    await callback.answer()

    # Запускаем поиск
    route = (await state.get_data()).get('routes', [{}])[0]
    route_filters = route.get('filters', {})
    task_key = f"preset_{preset_id}"
    user_tasks = tasks.get(user_id, {})
    tasks[user_id] = user_tasks

    async def _run_search():
        try:
            await search_cargo_for_user(
                user_id,
                route['from_location'],
                route['from_type'],
                route.get('to_location'),
                route.get('to_type'),
                route_filters.get('weight_min'),
                route_filters.get('weight_max'),
                callback.message,
                route_filters.get('volume_from'),
                route_filters.get('volume_to'),
                active_searches,
                route_filters.get('car_load_type_ids', []),
                route_filters.get('car_type_ids', []),
                from_radius=route.get('from_radius'),
                to_radius=route.get('to_radius'),
                any_direction=route.get('any_direction', False),
            )
        except asyncio.CancelledError:
            logger.info(f"Поиск по пресету для пользователя {user_id} отменён")
        except Exception as e:
            logger.error(f"Ошибка поиска по пресету для {user_id}: {e}", exc_info=True)

    task = asyncio.create_task(_run_search())
    user_tasks[task_key] = {
        'task': task,
        'name': preset['name'],
        'preset_id': preset_id,
    }


# ── Удалить пресет ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete_preset_"), StateFilter(PresetStates.editing_preset))
async def delete_preset_handler(callback: CallbackQuery, state: FSMContext):
    """Удаляет выбранный пресет."""
    preset_id = int(callback.data.replace("delete_preset_", ""))
    user_id = callback.from_user.id

    deleted = delete_preset(preset_id, user_id)
    if deleted:
        await callback.message.edit_text(
            "✅ <b>Фильтр удалён!</b>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "❌ Фильтр не найден",
            parse_mode="HTML"
        )

    # Возвращаемся к списку пресетов
    presets = get_user_presets(user_id)
    if presets:
        all_ids = [p['id'] for p in presets]
        await callback.message.answer(
            "📂 <b>Ваши сохранённые фильтры:</b>",
            parse_mode="HTML",
            reply_markup=get_multi_select_presets_keyboard(presets, set(all_ids))
        )
        await state.set_state(PresetStates.selecting_preset)
    else:
        await callback.message.answer(
            "📂 Сохранённых фильтров нет.\n\n"
            "Настройте маршрут и фильтры, затем сохраните их кнопкой «💾 Сохранить фильтр».",
            parse_mode="HTML",
            reply_markup=get_add_route_keyboard()
        )
        await state.set_state(SearchStates.adding_route)

    await callback.answer()


# ── Редактировать пресет (перенастройка) ─────────────────────────────

@router.callback_query(F.data.startswith("edit_preset_"), StateFilter(PresetStates.editing_preset))
async def edit_preset_handler(callback: CallbackQuery, state: FSMContext):
    """Загружает пресет в state для редактирования — отправляет пользователя настройать маршрут заново."""
    preset_id = int(callback.data.replace("edit_preset_", ""))
    user_id = callback.from_user.id
    preset = get_preset_by_id(preset_id, user_id)

    if not preset:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    # Удаляем старый пресет — пользователь создаст новый на его основе
    delete_preset(preset_id, user_id)

    # Загружаем данные пресета в state
    await state.update_data(
        editing_preset_id=preset_id,
        from_location=preset['from_location'],
        from_type=preset['from_type'],
        from_type_name=preset.get('from_type_name', ''),
        from_radius=preset.get('from_radius'),
        to_location=preset.get('to_location'),
        to_type=preset.get('to_type'),
        to_type_name=preset.get('to_type_name', ''),
        to_radius=preset.get('to_radius'),
        any_direction=preset.get('any_direction', False),
        weight_min=preset.get('weight_min'),
        weight_max=preset.get('weight_max'),
        volume_from=preset.get('volume_from'),
        volume_to=preset.get('volume_to'),
        car_load_type_ids=preset.get('car_load_type_ids', []),
        car_type_ids=preset.get('car_type_ids', []),
    )

    await callback.message.edit_text(
        "✏️ <b>Редактирование фильтра</b>\n\n"
        "Текущие параметры загружены. Настройте маршрут и фильтры заново.\n"
        "После настройки вы сможете сохранить фильтр с новыми параметрами.",
        parse_mode="HTML"
    )

    # Отправляем на настройку маршрута с предзаполненными данными
    await state.set_state(SearchStates.setting_from_type)
    await callback.message.answer(
        "📍 <b>Шаг 1 из 4:</b> Откуда отправляем груз?\n"
        "Выберите тип географической точки:",
        parse_mode="HTML",
        reply_markup=get_type_keyboard()
    )
    await callback.answer()


# ── Назад к списку пресетов ──────────────────────────────────────────

@router.callback_query(F.data == "back_to_presets", StateFilter(PresetStates.editing_preset))
async def back_to_presets(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку пресетов с мультивыбором."""
    user_id = callback.from_user.id
    presets = get_user_presets(user_id)

    if not presets:
        await callback.message.edit_text(
            "📂 Сохранённых фильтров нет.",
            parse_mode="HTML"
        )
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_add_route_keyboard()
        )
        await state.set_state(SearchStates.adding_route)
    else:
        data = await state.get_data()
        selected = set(data.get("selected_preset_ids", []))
        await callback.message.edit_text(
            "📂 <b>Ваши сохранённые фильтры:</b>\n\n"
            "Отметьте нужные фильтры и нажмите «Искать»:",
            parse_mode="HTML",
            reply_markup=get_multi_select_presets_keyboard(presets, selected)
        )
        await state.set_state(PresetStates.selecting_preset)

    await callback.answer()


# ── Отмена из меню пресетов ──────────────────────────────────────────

@router.callback_query(F.data == "cancel_presets")
async def cancel_presets(callback: CallbackQuery, state: FSMContext):
    """Возврат из меню пресетов."""
    await callback.message.edit_text("❌ Отменено")
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=get_add_route_keyboard()
    )
    await state.set_state(SearchStates.adding_route)
    await callback.answer()


# ── Сохранить текущие фильтры как пресет ─────────────────────────────

def _build_preset_name(route: dict) -> str:
    """Генерирует имя пресета из направления маршрута."""
    from_loc = route.get('from_location', '?')
    to_loc = route.get('to_location')
    if route.get('any_direction') or not to_loc:
        return f"{from_loc} → Любое"
    return f"{from_loc} → {to_loc}"


@router.callback_query(F.data == "save_current_as_preset", StateFilter(SearchStates.adding_route))
async def save_preset_auto(callback: CallbackQuery, state: FSMContext):
    """Сохраняет пресет с автоматическим именем из направлений."""
    user_id = callback.from_user.id
    data = await state.get_data()
    routes = data.get('routes', [])

    if routes:
        saved_names = []
        for route in routes:
            preset_name = _build_preset_name(route)
            filters = route.get('filters', {})
            preset_data = {
                'from_location': route.get('from_location'),
                'from_type': route.get('from_type'),
                'from_type_name': route.get('from_type_name', ''),
                'from_radius': route.get('from_radius'),
                'to_location': route.get('to_location'),
                'to_type': route.get('to_type'),
                'to_type_name': route.get('to_type_name', ''),
                'to_radius': route.get('to_radius'),
                'any_direction': route.get('any_direction', False),
                'weight_min': filters.get('weight_min'),
                'weight_max': filters.get('weight_max'),
                'volume_from': filters.get('volume_from'),
                'volume_to': filters.get('volume_to'),
                'car_load_type_ids': filters.get('car_load_type_ids', []),
                'car_type_ids': filters.get('car_type_ids', []),
            }
            save_filter_preset(user_id, preset_name, preset_data)
            saved_names.append(preset_name)

        names_text = "\n".join(f"  📌 {n}" for n in saved_names)
    else:
        # Нет маршрутов — сохраняем из state
        from_loc = data.get('from_location', '?')
        to_loc = data.get('to_location')
        preset_name = f"{from_loc} → {to_loc or 'Любое'}"

        preset_data = {
            'from_location': data.get('from_location'),
            'from_type': data.get('from_type'),
            'from_type_name': data.get('from_type_name', ''),
            'from_radius': data.get('from_radius'),
            'to_location': data.get('to_location'),
            'to_type': data.get('to_type'),
            'to_type_name': data.get('to_type_name', ''),
            'to_radius': data.get('to_radius'),
            'any_direction': data.get('any_direction', False),
            'weight_min': data.get('weight_min'),
            'weight_max': data.get('weight_max'),
            'volume_from': data.get('volume_from'),
            'volume_to': data.get('volume_to'),
            'car_load_type_ids': data.get('car_load_type_ids', []),
            'car_type_ids': data.get('car_type_ids', []),
        }
        save_filter_preset(user_id, preset_name, preset_data)
        names_text = f"  📌 {preset_name}"

    saved_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Начать поиск", callback_data="start_search_now"),
            InlineKeyboardButton(text="📂 Мои фильтры", callback_data="show_my_presets"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

    await callback.message.edit_text(
        f"✅ <b>Фильтр сохранён!</b>\n\n{names_text}\n\n"
        f"Теперь вы можете быстро загрузить его из меню «📂 Мои фильтры».",
        parse_mode="HTML",
        reply_markup=saved_keyboard
    )
    await callback.answer()
    await state.set_state(SearchStates.adding_route)


# ── Вспомогательные функции ──────────────────────────────────────────

def _format_preset_info(preset: dict) -> str:
    """Форматирует информацию о пресете для отображения."""
    any_dir = preset.get('any_direction', False)
    to_text = preset.get('to_location') or '🌐 Любое направление'
    from_radius = preset.get('from_radius')
    to_radius = preset.get('to_radius')

    text = (
        f"📌 <b>{preset['name']}</b>\n\n"
        f"📍 <b>Откуда:</b> {preset.get('from_type_name', '')} {preset['from_location']}"
        f"{f', радиус {from_radius} км' if from_radius else ''}\n"
        f"🏁 <b>Куда:</b> {preset.get('to_type_name', '')} {to_text}"
        f"{f', радиус {to_radius} км' if to_radius and not any_dir else ''}\n"
    )

    filters = []
    if preset.get('weight_min') or preset.get('weight_max'):
        parts = []
        if preset.get('weight_min'):
            parts.append(f"от {preset['weight_min']} т")
        if preset.get('weight_max'):
            parts.append(f"до {preset['weight_max']} т")
        filters.append(f"⚖️ Вес: {', '.join(parts)}")

    if preset.get('volume_from') or preset.get('volume_to'):
        parts = []
        if preset.get('volume_from'):
            parts.append(f"от {preset['volume_from']} м³")
        if preset.get('volume_to'):
            parts.append(f"до {preset['volume_to']} м³")
        filters.append(f"📦 Объём: {', '.join(parts)}")

    if preset.get('car_load_type_ids'):
        filters.append(f"🚚📦 Тип загрузки: {len(preset['car_load_type_ids'])} шт.")

    if preset.get('car_type_ids'):
        filters.append(f"🚛 Тип кузова: {len(preset['car_type_ids'])} шт.")

    if filters:
        text += "\n" + "\n".join(filters)

    text += "\n\nВыберите действие:"
    return text
