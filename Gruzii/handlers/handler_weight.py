from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from menu import (get_filter_setup_keyboard, get_weight_range_keyboard)
from states import (FilterStates, WeightStates)

router = Router()


@router.callback_query(StateFilter(WeightStates.setting_weight))
async def handle_weight_range(callback: CallbackQuery, state: FSMContext):
    await process_weight_input(callback, state, callback.data)


@router.message(StateFilter(WeightStates.setting_weight_min, WeightStates.setting_weight_max))
async def handle_weight_value(message: Message, state: FSMContext):
    await process_weight_value(message, state)


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
        await state.update_data(weight_min=None, weight_max=None)
        await state.set_state(WeightStates.setting_weight)
        await callback.message.edit_text(
            "📦 <b>Задайте вес или пропустите фильтр</b>",
            parse_mode="HTML",
            reply_markup=get_weight_range_keyboard()
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
            await state.update_data(weight_min=value)
        elif current_state == WeightStates.setting_weight_max:
            if value < 0:
                raise ValueError("Максимальный вес не может быть отрицательный")
            weight_min = data.get('weight_min')
            if weight_min is not None and value < weight_min:
                raise ValueError("Максимальный вес не может быть меньше минимального")
            await state.update_data(weight_max=value)

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
