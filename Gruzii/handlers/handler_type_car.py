from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from Gruzii.menu import (get_filter_setup_keyboard, get_car_type_keyboard)
from Gruzii.states import CarTypeStates, FilterStates

router = Router()


@router.callback_query(StateFilter(CarTypeStates.setting_car_type))
async def handle_car_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа кузова"""
    await process_car_type_selection(callback, state)


async def process_car_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа кузова из БД"""
    await callback.answer()
    data = await state.get_data()
    selected_ids = data.get('car_type_ids', [])
    if callback.data.startswith("toggle_type_"):
        try:
            type_id = int(callback.data.replace("toggle_type_", ""))

            if type_id in selected_ids:
                selected_ids.remove(type_id)
            else:
                selected_ids.append(type_id)

            await state.update_data(car_type_ids=selected_ids)

            await callback.message.edit_text(
                "🚚📦 <b>Настройка фильтра по типу кузова</b>\n\n"
                "Выберите нужный тип кузова (можно выбрать несколько):",
                parse_mode="HTML",
                reply_markup=get_car_type_keyboard(selected_ids)
            )

        except ValueError as e:
            print(f"Ошибка обработки типа кузова: {e}")
            await callback.answer("❌ Ошибка выбора типа")

    elif callback.data == "apply_type_selection":
        await state.set_state(FilterStates.setting_filters)
        await callback.message.edit_text(
            "⚙️ <b>Настройка фильтров</b>\n\n"
            "Выберите параметры для фильтрации:",
            parse_mode="HTML",
            reply_markup=get_filter_setup_keyboard()
        )

    await callback.answer()
