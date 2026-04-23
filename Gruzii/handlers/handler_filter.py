from aiogram import F
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter

from Gruzii.states import (FilterStates, WeightStates, VolumeStates,
                           CarLoadTypeStates, CarTypeStates, SearchStates)
from Gruzii.menu import (get_filter_setup_keyboard, get_car_load_type_keyboard,
                         get_weight_range_keyboard, get_volume_range_keyboard,
                         get_add_route_keyboard, get_car_type_keyboard, get_car_types)
from Gruzii.storage import get_car_loading_types

router = Router()


@router.callback_query(F.data.startswith("filter_"))
async def handle_filter_button(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки '⚙️ Фильтр'"""
    await start_filter_setup(callback, state)


async def start_filter_setup(callback: CallbackQuery, state: FSMContext):
    """Начинает настройку фильтров после нажатия кнопки '⚙️ Фильтр'"""
    await callback.answer()
    await state.set_state(FilterStates.setting_filters)
    await callback.message.edit_text(
        "⚙️ <b>Настройка фильтров</b>\n\n"
        "Выберите параметры для фильтрации:",
        parse_mode="HTML",
        reply_markup=get_filter_setup_keyboard()
    )
    await callback.answer()


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
    from_line = f"📍 <b>Откуда:</b> {data['from_type_name']} {data['from_location']} {from_radius_str}\n"

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
