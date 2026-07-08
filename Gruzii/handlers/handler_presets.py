import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from states import SearchStates, PresetStates
from storage import (
    save_filter_preset, get_user_presets, get_preset_by_id,
    delete_preset, update_filter_preset, active_searches, tasks,
)
from menu import (
    get_presets_keyboard, get_preset_actions_keyboard,
    get_add_route_keyboard, get_search_controls,
    get_type_keyboard,
)
from search_cargo import search_cargo_for_user

logger = logging.getLogger(__name__)
router = Router()


# ── Показать список пресетов ─────────────────────────────────────────

@router.callback_query(F.data == "show_my_presets", StateFilter(SearchStates.adding_route))
async def show_my_presets(callback: CallbackQuery, state: FSMContext):
    """Показывает список сохранённых фильтров пользователя."""
    user_id = callback.from_user.id
    presets = get_user_presets(user_id)

    if not presets:
        await callback.answer("У вас нет сохранённых фильтров", show_alert=True)
        return

    await callback.message.edit_text(
        "📂 <b>Ваши сохранённые фильтры:</b>\n\n"
        "Выберите фильтр для использования:",
        parse_mode="HTML",
        reply_markup=get_presets_keyboard(presets)
    )
    await state.set_state(PresetStates.selecting_preset)
    await callback.answer()


# ── Удалить пресет прямо из списка ────────────────────────────────────

@router.callback_query(F.data.startswith("del_preset_"), StateFilter(PresetStates.selecting_preset))
async def delete_preset_from_list(callback: CallbackQuery, state: FSMContext):
    """Удаляет пресет из списка и обновляет клавиатуру."""
    preset_id = int(callback.data.replace("del_preset_", ""))
    user_id = callback.from_user.id

    deleted = delete_preset(preset_id, user_id)
    if deleted:
        await callback.answer("Фильтр удалён")
    else:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    presets = get_user_presets(user_id)
    if presets:
        await callback.message.edit_text(
            "📂 <b>Ваши сохранённые фильтры:</b>\n\n"
            "Выберите фильтр для использования:",
            parse_mode="HTML",
            reply_markup=get_presets_keyboard(presets)
        )
    else:
        await callback.message.edit_text(
            "📂 Сохранённых фильтров нет.\n\n"
            "Настройте маршрут и фильтры, затем сохраните их кнопкой «💾 Сохранить фильтр».",
            parse_mode="HTML",
            reply_markup=get_add_route_keyboard()
        )
        await state.set_state(SearchStates.adding_route)


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
    tasks[user_id] = task


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
        await callback.message.answer(
            "📂 <b>Ваши сохранённые фильтры:</b>",
            parse_mode="HTML",
            reply_markup=get_presets_keyboard(presets)
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
    """Возврат к списку пресетов."""
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
        await callback.message.edit_text(
            "📂 <b>Ваши сохранённые фильтры:</b>",
            parse_mode="HTML",
            reply_markup=get_presets_keyboard(presets)
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

@router.callback_query(F.data == "save_current_as_preset", StateFilter(SearchStates.adding_route))
async def ask_preset_name(callback: CallbackQuery, state: FSMContext):
    """Запрашивает имя для сохранения пресета."""
    await callback.message.edit_text(
        "💾 <b>Сохранение фильтра</b>\n\n"
        "Введите название для фильтра (например, «Москва-Сочи 10т»):",
        parse_mode="HTML"
    )
    await state.set_state(PresetStates.naming_preset)
    await callback.answer()


@router.message(StateFilter(PresetStates.naming_preset))
async def save_preset_with_name(message: Message, state: FSMContext):
    """Сохраняет пресет с указанным именем."""
    name = message.text.strip()
    if not name or len(name) > 100:
        await message.answer("❌ Название должно быть от 1 до 100 символов. Попробуйте ещё раз:")
        return

    user_id = message.from_user.id
    data = await state.get_data()
    routes = data.get('routes', [])

    if routes:
        # Сохраняем каждый маршрут как отдельный пресет
        saved_count = 0
        for i, route in enumerate(routes):
            suffix = f" ({i + 1})" if len(routes) > 1 else ""
            preset_name = f"{name}{suffix}"
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
            saved_count += 1

        if saved_count > 1:
            name = f"{name} (×{saved_count})"
    else:
        # Нет маршрутов — сохраняем только фильтры из state
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
        save_filter_preset(user_id, name, preset_data)

    saved_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Начать поиск", callback_data="start_search_now"),
            InlineKeyboardButton(text="📂 Мои фильтры", callback_data="show_my_presets"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

    await message.answer(
        f"✅ <b>Фильтр «{name}» сохранён!</b>\n\n"
        f"Теперь вы можете быстро загрузить его из меню «📂 Мои фильтры».",
        parse_mode="HTML",
        reply_markup=saved_keyboard
    )
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
