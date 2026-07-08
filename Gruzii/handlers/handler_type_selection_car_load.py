import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from menu import (get_filter_setup_keyboard, get_car_load_type_keyboard)
from states import CarLoadTypeStates, FilterStates

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(StateFilter(CarLoadTypeStates.selecting_car_load_type))
async def handle_car_load_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа загрузки"""
    await process_car_load_type_selection(callback, state)


async def process_car_load_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа загрузки из БД"""
    await callback.answer()
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
            logger.error(f"Ошибка обработки типа загрузки: {e}")
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
