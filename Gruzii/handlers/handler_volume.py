from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from Gruzii.menu import (get_filter_setup_keyboard, get_volume_range_keyboard)
from Gruzii.states import (FilterStates, VolumeStates)

router = Router()


@router.callback_query(StateFilter(VolumeStates.setting_volume))
async def handle_volume_range(callback: CallbackQuery, state: FSMContext):
    await process_volume_input(callback, state, callback.data)


@router.message(StateFilter(VolumeStates.setting_volume_min, VolumeStates.setting_volume_max))
async def handle_volume_value(message: Message, state: FSMContext):
    await process_volume_value(message, state)


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
        await state.update_data(volume_from=None, volume_to=None)
        await state.set_state(VolumeStates.setting_volume)
        await callback.message.edit_text(
            "📦 <b>Задайте диапазон объема или пропустите фильтр</b>",
            parse_mode="HTML",
            reply_markup=get_volume_range_keyboard()
        )
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
