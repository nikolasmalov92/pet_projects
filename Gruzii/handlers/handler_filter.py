import asyncio
import logging

from aiogram import F
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter

from states import (FilterStates, WeightStates, VolumeStates,
                    CarLoadTypeStates, CarTypeStates, SearchStates)
from menu import (get_filter_setup_keyboard, get_car_load_type_keyboard,
                  get_weight_range_keyboard, get_volume_range_keyboard,
                  get_add_route_keyboard, get_car_type_keyboard, get_car_types,
                  get_active_search_keyboard, get_search_controls)
from storage import get_car_loading_types, update_filter_preset, get_preset_by_id, tasks, active_searches
from search_cargo import search_cargo_for_user

router = Router()


@router.callback_query(F.data.startswith("filter_"))
async def handle_filter_button(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки '⚙️ Фильтр'"""
    await start_filter_setup(callback, state)


async def start_filter_setup(callback: CallbackQuery, state: FSMContext):
    """Начинает настройку фильтров"""
    await callback.answer()

    data = await state.get_data()
    route_index = data.get('filter_route_index')

    if route_index is not None:
        routes = data.get('routes', [])
        if route_index < len(routes):
            route = routes[route_index]
            existing_filters = route.get('filters', {})
            await state.update_data(
                weight_min=existing_filters.get('weight_min'),
                weight_max=existing_filters.get('weight_max'),
                volume_from=existing_filters.get('volume_from'),
                volume_to=existing_filters.get('volume_to'),
                car_load_type_ids=existing_filters.get('car_load_type_ids', []),
                car_type_ids=existing_filters.get('car_type_ids', [])
            )
            await callback.message.edit_text(
                f"⚙️ <b>Настройка фильтров для маршрута:</b>\n"
                f"📍 {route['from_location']} → {route.get('to_location', 'любое')}\n\n"
                f"Выберите параметры:",
                parse_mode="HTML",
                reply_markup=get_filter_setup_keyboard()
            )
            await state.update_data(filtering_route_index=route_index)
            await state.set_state(FilterStates.setting_filters)
            return

    await state.set_state(FilterStates.setting_filters)
    await callback.message.edit_text(
        "⚙️ <b>Настройка фильтров</b>\n\n"
        "Выберите параметры для фильтрации:",
        parse_mode="HTML",
        reply_markup=get_filter_setup_keyboard()
    )


async def process_filter_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа фильтра"""
    await callback.answer()
    if callback.data == "setup_weight":
        await state.set_state(WeightStates.setting_weight)
        await callback.message.edit_text(
            "⚖️ <b>Настройка фильтра по весу</b>\n\n"
            "Задайте диапазон веса (в тоннах):",
            parse_mode="HTML",
            reply_markup=get_weight_range_keyboard()
        )
    elif callback.data == "setup_volume":
        await state.set_state(VolumeStates.setting_volume)
        await callback.message.edit_text(
            "📦 <b>Настройка фильтра по объему</b>\n\n"
            "Задайте диапазон объема (в м³):",
            parse_mode="HTML",
            reply_markup=get_volume_range_keyboard()
        )

    elif callback.data == "setup_car_load_type":
        await state.set_state(CarLoadTypeStates.selecting_car_load_type)
        data = await state.get_data()
        selected_ids = data.get('car_load_type_ids', [])
        await callback.message.edit_text(
            "🚚📦 <b>Настройка фильтра по типу загрузки</b>\n\n"
            "Выберите нужные типы загрузки (можно выбрать несколько):",
            parse_mode="HTML",
            reply_markup=get_car_load_type_keyboard(selected_ids)
        )

    elif callback.data == "setup_car_type":
        await state.set_state(CarTypeStates.setting_car_type)
        data = await state.get_data()
        selected_ids = data.get('car_type_ids', [])
        await callback.message.edit_text(
            "🚚📦 <b>Настройка фильтра по типу кузова</b>\n\n"
            "Выберите нужный тип кузова (можно выбрать несколько):",
            parse_mode="HTML",
            reply_markup=get_car_type_keyboard(selected_ids)
        )

    elif callback.data == "finish_filters":
        data = await state.get_data()

        # Редактирование фильтров активного направления
        editing_preset_id = data.get('editing_preset_id')
        editing_task_key = data.get('editing_task_key')
        if editing_preset_id and editing_task_key:
            user_id = callback.from_user.id
            preset = get_preset_by_id(editing_preset_id, user_id)

            if preset:
                # Обновляем фильтры в пресете (передаём полные данные)
                updated_data = {
                    'from_location': preset['from_location'],
                    'from_type': preset['from_type'],
                    'from_type_name': preset.get('from_type_name', ''),
                    'from_radius': preset.get('from_radius'),
                    'to_location': preset.get('to_location'),
                    'to_type': preset.get('to_type'),
                    'to_type_name': preset.get('to_type_name', ''),
                    'to_radius': preset.get('to_radius'),
                    'any_direction': preset.get('any_direction', False),
                    'weight_min': data.get('weight_min'),
                    'weight_max': data.get('weight_max'),
                    'volume_from': data.get('volume_from'),
                    'volume_to': data.get('volume_to'),
                    'car_load_type_ids': data.get('car_load_type_ids', []),
                    'car_type_ids': data.get('car_type_ids', []),
                }
                update_filter_preset(editing_preset_id, user_id, updated_data)

                # Обновлённый пресет
                preset = get_preset_by_id(editing_preset_id, user_id)

                # Запускаем поиск по обновлённому пресету
                user_tasks = tasks.get(user_id, {})
                tasks[user_id] = user_tasks

                async def _run_search():
                    try:
                        await search_cargo_for_user(
                            user_id,
                            preset['from_location'],
                            preset['from_type'],
                            preset.get('to_location'),
                            preset.get('to_type'),
                            preset.get('weight_min'),
                            preset.get('weight_max'),
                            callback.message,
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
                        pass
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Ошибка поиска: {e}", exc_info=True)

                task = asyncio.create_task(_run_search())
                user_tasks[editing_task_key] = {
                    'task': task,
                    'name': preset['name'],
                    'preset_id': editing_preset_id,
                }

                active_searches[user_id] = True

                await callback.message.edit_text(
                    f"✅ <b>Фильтры обновлены!</b>\n\n"
                    f"📌 {preset['name']}\n"
                    f"Поиск перезапущен с новыми параметрами.",
                    parse_mode="HTML"
                )
                await callback.message.answer(
                    reply_markup=get_search_controls()
                )

            # Очищаем временные данные
            await state.update_data(
                editing_preset_id=None,
                editing_task_key=None,
                weight_min=None, weight_max=None,
                volume_from=None, volume_to=None,
                car_load_type_ids=[], car_type_ids=[],
            )
            await state.set_state(SearchStates.searching)
            await callback.answer()
            return

        route_index = data.get('filtering_route_index')
        if route_index is not None:
            # Сохраняем фильтры в маршрут
            routes = data.get('routes', [])
            if route_index < len(routes):
                routes[route_index]['filters'] = {
                    'weight_min': data.get('weight_min'),
                    'weight_max': data.get('weight_max'),
                    'volume_from': data.get('volume_from'),
                    'volume_to': data.get('volume_to'),
                    'car_load_type_ids': data.get('car_load_type_ids', []),
                    'car_type_ids': data.get('car_type_ids', []),
                }

                await state.update_data(routes=routes)

            # Очищаем временные данные
            await state.update_data(filtering_route_index=None,
                                    filter_route_index=None,
                                    weight_min=None,
                                    weight_max=None,
                                    volume_from=None,
                                    volume_to=None,
                                    car_load_type_ids=[],
                                    car_type_ids=[])

            # Показываем список маршрутов
            routes_list = routes if route_index < len(routes) else data.get('routes', [])
            routes_text = "\n".join(f"  {i + 1}. {r['from_location']} → {r.get('to_location')
                                                                         or '🌐 Любое'}"
                                    for i, r in enumerate(routes_list))

            await callback.message.edit_text(f"✅ Маршруты добавлены!\n\n"
                                             f"📋 <b>Текущие маршруты:</b>\n{routes_text}\n\n"
                                             "Выберите действие:", parse_mode="HTML",
                                             reply_markup=get_add_route_keyboard())

            await state.set_state(SearchStates.adding_route)

        else:
            await show_search_confirmation(callback.message, state)

    else:
        await show_search_confirmation(callback.message, state)

    await callback.answer()


@router.callback_query(StateFilter(FilterStates.setting_filters))
async def handle_filter_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор фильтров в состоянии настройки"""
    await process_filter_selection(callback, state)


async def show_search_confirmation(message: Message, state: FSMContext):
    """
    Показывает подтверждение параметров поиска с учетом фильтров и радиуса.
    """
    data = await state.get_data()
    from_radius = data.get('from_radius')
    from_radius_str = f", радиус {from_radius} км" if from_radius else ""
    from_line = f"📍 <b>Откуда:</b> {data.get('from_type_name', '—')} {data.get('from_location', '—')} {from_radius_str}\n"

    any_direction = data.get('any_direction', False)
    if any_direction:
        to_line = "🌐 <b>Куда:</b> Любое направление\n"
    else:
        to_radius = data.get('to_radius')
        to_radius_str = f", радиус {to_radius} км" if to_radius else ""
        to_line = f"🏁 <b>Куда:</b> {data.get('to_type_name', '—')} {data.get('to_location', '—')} {to_radius_str}\n"

    summary = "📋 <b>Параметры поиска:</b>\n\n" + from_line + to_line

    weight_min = data.get('weight_min')
    weight_max = data.get('weight_max')
    volume_from = data.get('volume_from')
    volume_to = data.get('volume_to')

    if weight_min or weight_max:
        filters = []
        if weight_min:
            filters.append(f"от {weight_min} т")
        if weight_max:
            filters.append(f"до {weight_max} т")
        summary += f"⚖️ <b>Вес:</b> {', '.join(filters)}\n"

    if volume_from or volume_to:
        filters = []
        if volume_from:
            filters.append(f"от {volume_from} м³")
        if volume_to:
            filters.append(f"до {volume_to} м³")
        summary += f"📦 <b>Объем:</b> {', '.join(filters)}\n"

    car_load_type_ids = data.get('car_load_type_ids', [])
    if car_load_type_ids:
        all_types = get_car_loading_types()
        type_id_to_name = {type_obj["Id"]: type_obj["Name"] for type_obj in all_types}
        selected_names = [type_id_to_name.get(type_id, f"Тип {type_id}") for type_id in car_load_type_ids]
        summary += f"🚚📦 <b>Тип загрузки:</b> {', '.join(selected_names)}\n"

    car_type_ids = data.get('car_type_ids', [])
    if car_type_ids:
        all_car_types = get_car_types()
        type_id_to_name = {t["Id"]: t["Name"] for t in all_car_types}
        selected_car_type_names = [type_id_to_name.get(t_id, f"Тип {t_id}") for t_id in car_type_ids]
        summary += f"🚛 <b>Тип кузова:</b> {', '.join(selected_car_type_names)}\n"

    if not (weight_min or weight_max or volume_from or volume_to or car_load_type_ids or car_type_ids):
        summary += "⚙️ <b>Фильтры:</b> не установлены\n"

    summary += "\n🤔 Всё правильно? Начинаем поиск?"

    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=get_add_route_keyboard()
    )
    await state.set_state(SearchStates.adding_route)
