from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from storage import get_car_loading_types
from menu import (get_confirmation_keyboard, get_volume_range_keyboard,
                  get_filter_setup_keyboard, get_weight_range_keyboard, get_car_load_type_keyboard)
from states import WeightStates, VolumeStates, SearchStates, FilterStates, CarLoadTypeStates


async def start_filter_setup(callback: CallbackQuery, state: FSMContext):
    """Начинает настройку фильтров после нажатия кнопки '⚙️ Фильтр'"""
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

    elif callback.data == "finish_filters":
        await show_search_confirmation(callback.message, state)

    await callback.answer()


async def show_search_confirmation(message: Message, state: FSMContext):
    """
    Показывает подтверждение параметров поиска с учетом фильтров.
    """
    data = await state.get_data()
    summary = (
        "📋 <b>Параметры поиска:</b>\n\n"
        f"📍 <b>Откуда:</b> {data['from_location']} ({data['from_type_name']})\n"
        f"🏁 <b>Куда:</b> {data['to_location']} ({data['to_type_name']})\n"
    )

    weight_from = data.get('weight_from')
    weight_to = data.get('weight_to')
    volume_from = data.get('volume_from')
    volume_to = data.get('volume_to')

    if weight_from or weight_to:
        filters = []
        if weight_from:
            filters.append(f"от {weight_from} т")
        if weight_to:
            filters.append(f"до {weight_to} т")
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

    if not (weight_from or weight_to or volume_from or volume_to or car_load_type_ids):
        summary += "⚙️ <b>Фильтры:</b> не установлены\n"

    summary += "\n🤔 Всё правильно? Начинаем поиск?"

    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=get_confirmation_keyboard("search_start")
    )
    await state.set_state(SearchStates.confirming_search)


async def process_weight_input(callback: CallbackQuery, state: FSMContext, callback_data: str):
    """
    Обрабатывает ввод веса от пользователя и сохраняет данные в состояние.
    """
    if callback_data == "weight_min":
        await state.set_state(WeightStates.setting_weight_min)
        await callback.message.edit_text(
            "⚖️ <b>Введите минимальный вес (в тоннах, только целые числа):</b>",
            parse_mode="HTML"
        )
        await callback.answer()
        return False
    elif callback_data == "weight_max":
        await state.set_state(WeightStates.setting_weight_max)
        await callback.message.edit_text(
            "⚖️ <b>Введите максимальный вес (в тоннах, только целые числа):</b>",
            parse_mode="HTML"
        )
        await callback.answer()
        return False
    elif callback_data == "weight_skip":
        await state.update_data(weight_from=None, weight_to=None)
        await state.set_state(VolumeStates.setting_volume)
        await callback.message.edit_text(
            "📦 <b>Задайте диапазон объема или пропустите фильтр</b>",
            parse_mode="HTML",
            reply_markup=get_volume_range_keyboard()
        )
        await callback.answer()
        return False
    return False


async def process_weight_value(message: Message, state: FSMContext):
    """
    Обрабатывает введенное значение веса.
    """
    try:
        value = message.text.strip()
        if not value.isdigit():
            raise ValueError("Вводите только целые числа")
        value = int(value)

        data = await state.get_data()
        current_state = await state.get_state()
        if current_state == WeightStates.setting_weight_min:
            if value < 0:
                raise ValueError("Минимальный вес не может быть отрицательным")
            await state.update_data(weight_from=value)
        elif current_state == WeightStates.setting_weight_max:
            if value < 0:
                raise ValueError("Максимальный вес не может быть отрицательный")
            weight_from = data.get('weight_from')
            if weight_from is not None and value < weight_from:
                raise ValueError("Максимальный вес не может быть меньше минимального")
            await state.update_data(weight_to=value)

        await state.set_state(FilterStates.setting_filters)
        await message.answer(
            "⚙️ <b>Настройка фильтров</b>\n\n"
            "Выберите параметры для фильтрации:",
            parse_mode="HTML",
            reply_markup=get_filter_setup_keyboard()
        )
        return True
    except ValueError as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {str(e)}\n\nВведите корректное значение:",
            parse_mode="HTML"
        )
        return False


async def process_volume_input(callback: CallbackQuery, state: FSMContext, callback_data: str):
    """
    Обрабатывает выбор объема через кнопки и ввод значений.
    """
    if callback_data == "volume_min":
        await state.set_state(VolumeStates.setting_volume_min)
        await callback.message.edit_text(
            "📦 <b>Введите минимальный объем (в м³, можно дробные числа, например 5.5):</b>",
            parse_mode="HTML"
        )
        await callback.answer()
        return False
    elif callback_data == "volume_max":
        await state.set_state(VolumeStates.setting_volume_max)
        await callback.message.edit_text(
            "📦 <b>Введите максимальный объем (в м³, можно дробные числа, например 10.0):</b>",
            parse_mode="HTML"
        )
        await callback.answer()
        return False
    elif callback_data == "volume_skip":
        await show_weight_confirmation(callback.message, state, SearchStates.confirming_search)
        await callback.answer()
        return False
    return False


async def process_volume_value(message: Message, state: FSMContext):
    """
    Обрабатывает введенное значение объема.
    """
    try:
        value = message.text.strip()
        value = float(value)

        data = await state.get_data()
        current_state = await state.get_state()
        if current_state == VolumeStates.setting_volume_min:
            if value < 0:
                raise ValueError("Минимальный объем не может быть отрицательным")
            await state.update_data(volume_from=value)
        elif current_state == VolumeStates.setting_volume_max:
            if value < 0:
                raise ValueError("Максимальный объем не может быть отрицательным")
            volume_from = data.get('volume_from')
            if volume_from is not None and value < volume_from:
                raise ValueError("Максимальный объем не может быть меньше минимального")
            await state.update_data(volume_to=value)

        # Возвращаемся к настройке фильтров
        await state.set_state(FilterStates.setting_filters)
        await message.answer(
            "⚙️ <b>Настройка фильтров</b>\n\n"
            "Выберите параметры для фильтрации:",
            parse_mode="HTML",
            reply_markup=get_filter_setup_keyboard()
        )
        return True
    except ValueError as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {str(e)}\n\nВведите корректное значение (например, 5.5):",
            parse_mode="HTML"
        )
        return False


async def show_weight_confirmation(message: Message, state: FSMContext, next_state):
    """
    Показывает подтверждение параметров поиска с учетом веса.
    :param next_state: Состояние, в которое нужно перейти после подтверждения.
    """
    data = await state.get_data()
    summary = (
        "📋 <b>Параметры поиска:</b>\n\n"
        f"📍 <b>Откуда:</b> {data['from_location']} ({data['from_type_name']})\n"
        f"🏁 <b>Куда:</b> {data['to_location']} ({data['to_type_name']})\n"
    )
    weight_from = data.get('weight_from')
    weight_to = data.get('weight_to')
    volume_from = data.get('volume_from')
    volume_to = data.get('volume_to')
    if weight_from or weight_to:
        filters = []
        if weight_from:
            filters.append(f"от {weight_from} т")
        if weight_to:
            filters.append(f"до {weight_to} т")
        summary += f"\n⚖️ <b>Вес:</b> {', '.join(filters)}\n"
    if volume_from or volume_to:
        filters = []
        if volume_from:
            filters.append(f"объем от {volume_from} м³")
        if volume_to:
            filters.append(f"объем до {volume_to} м³")
        summary += f"\n📦 <b>Объем:</b> {', '.join(filters)}\n"
    summary += "\n🤔 Всё правильно? Начинаем поиск?"
    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=get_confirmation_keyboard("search_start")
    )
    await state.set_state(next_state)


async def process_car_load_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа загрузки из БД"""
    data = await state.get_data()
    selected_ids = data.get('car_load_type_ids', [])

    if callback.data.startswith("toggle_load_type_"):
        try:
            type_id = int(callback.data.replace("toggle_load_type_", ""))

            if type_id in selected_ids:
                selected_ids.remove(type_id)
            else:
                selected_ids.append(type_id)

            await state.update_data(car_load_type_ids=selected_ids)

            await callback.message.edit_text(
                "🚚📦 <b>Настройка фильтра по типу загрузки</b>\n\n"
                "Выберите нужные типы загрузки (можно выбрать несколько):",
                parse_mode="HTML",
                reply_markup=get_car_load_type_keyboard(selected_ids)
            )

        except ValueError as e:
            print(f"Ошибка обработки типа загрузки: {e}")
            await callback.answer("❌ Ошибка выбора типа")

    elif callback.data == "apply_load_type_selection":
        await state.set_state(FilterStates.setting_filters)
        await callback.message.edit_text(
            "⚙️ <b>Настройка фильтров</b>\n\n"
            "Выберите параметры для фильтрации:",
            parse_mode="HTML",
            reply_markup=get_filter_setup_keyboard()
        )

    await callback.answer()