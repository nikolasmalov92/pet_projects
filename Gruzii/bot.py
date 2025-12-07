import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage

from filter import *
from menu import *
from search_cargo import search_cargo_for_user
from storage import *
from handler_add_user import router

logging.basicConfig(level=logging.INFO)

bot = Bot(token=telegram_token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
active_searches = {}

dp.include_router(router)


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    allowed_users = await asyncio.to_thread(load_users)
    await asyncio.create_task(asyncio.to_thread(delete_processed))

    if user_id in allowed_users or user_id == ADMIN_USER_ID:
        first_name = message.from_user.first_name or "Пользователь"
        await message.answer(
            f"🚚 <b>Добро пожаловать, {first_name}!</b>\n\n"
            "🔍 Я помогу найти лучшие грузы для ваших перевозок\n"
            "⚡ Нажмите 'Найти грузы', чтобы начать!",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            "❌ <b>Доступ ограничен</b>\n\n"
            "Для использования бота обратитесь к администратору",
            parse_mode="HTML"
        )


@dp.message(F.text == "🔍 Найти грузы")
async def start_search(message: Message, state: FSMContext):
    await state.set_state(SearchStates.setting_from_type)
    await message.answer(
        "🎯 <b>Настройка поиска грузов</b>\n\n"
        "📍 <b>Шаг 1 из 4:</b> Откуда отправляем груз?\n"
        "Выберите тип географической точки:",
        parse_mode="HTML",
        reply_markup=get_type_keyboard()
    )


@dp.message(StateFilter(SearchStates.setting_from_type))
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
        await message.answer(
            "🏠 <b>Главное меню</b>\n\nВыберите действие:",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
        await state.clear()
    else:
        await message.answer(
            "❌ Пожалуйста, используйте кнопки для выбора",
            reply_markup=get_type_keyboard()
        )


@dp.message(StateFilter(SearchStates.setting_from_location))
async def set_from_location(message: Message, state: FSMContext):
    location = message.text.strip().title()
    await state.update_data(from_location=location)
    await state.set_state(SearchStates.setting_to_type)
    await message.answer(
        f"✅ Пункт отправления: <b>{location}</b>\n\n"
        "📍 <b>Шаг 2 из 4:</b> Куда доставляем?\n"
        "Выберите тип географической точки назначения:",
        parse_mode="HTML",
        reply_markup=get_type_keyboard()
    )


@dp.message(StateFilter(SearchStates.setting_to_type))
async def set_to_type(message: Message, state: FSMContext):
    text = message.text.replace("🏙️ ", "").replace("🌍 ", "").replace("🗺️ ", "")
    if text in ["Город", "Регион", "Страна"]:
        await state.update_data(to_type=get_type_id(text), to_type_name=text)
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
            parse_mode="HTML"
        )


@dp.message(StateFilter(SearchStates.setting_to_location))
async def set_to_location(message: Message, state: FSMContext):
    location = message.text.strip().title()
    await state.update_data(to_location=location)
    from filter import show_search_confirmation
    await show_search_confirmation(message, state)


@dp.callback_query(StateFilter(WeightStates.setting_weight))
async def handle_weight_range(callback: CallbackQuery, state: FSMContext):
    await process_weight_input(callback, state, callback.data)


@dp.message(StateFilter(WeightStates.setting_weight_min, WeightStates.setting_weight_max))
async def handle_weight_value(message: Message, state: FSMContext):
    await process_weight_value(message, state)


@dp.callback_query(StateFilter(VolumeStates.setting_volume))
async def handle_volume_range(callback: CallbackQuery, state: FSMContext):
    await process_volume_input(callback, state, callback.data)


@dp.message(StateFilter(VolumeStates.setting_volume_min, VolumeStates.setting_volume_max))
async def handle_volume_value(message: Message, state: FSMContext):
    await process_volume_value(message, state)


@dp.callback_query(F.data.startswith("filter_"))
async def handle_filter_button(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки '⚙️ Фильтр'"""
    await start_filter_setup(callback, state)


@dp.callback_query(StateFilter(FilterStates.setting_filters))
async def handle_filter_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор фильтров в состоянии настройки"""
    await process_filter_selection(callback, state)


@dp.callback_query(StateFilter(CarLoadTypeStates.selecting_car_load_type))
async def handle_car_load_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа загрузки"""
    await process_car_load_type_selection(callback, state)


@dp.callback_query(F.data == "confirm_search_start", StateFilter(SearchStates.confirming_search))
async def confirm_search(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    active_searches[user_id] = True
    search_info = f"🔍 Ищу грузы: {data['from_location']} → {data['to_location']}"
    filters_applied = []
    if data.get('weight_from'):
        filters_applied.append(f"вес от {data['weight_from']} т")
    if data.get('weight_to'):
        filters_applied.append(f"до {data['weight_to']} т")
    if data.get('volume_from'):
        filters_applied.append(f"объем от {data['volume_from']} м³")
    if data.get('volume_to'):
        filters_applied.append(f"объем до {data['volume_to']} м³")
    if filters_applied:
        search_info += f"\n🎯 Фильтры: {', '.join(filters_applied)}"
    await callback.message.edit_text(
        f"🚀 <b>Поиск запущен!</b>\n\n{search_info}\n"
        "⏳ Первые результаты появятся через несколько секунд...",
        parse_mode="HTML"
    )
    await state.set_state(SearchStates.searching)
    await callback.message.answer(
        "🎛️ <b>Управление поиском:</b>",
        parse_mode="HTML",
        reply_markup=get_search_controls()
    )
    logging.info(f"Поиск для user_id={user_id}: from={data['from_location']}, to={data['to_location']}, "
                 f"weight_from={data.get('weight_from')}, weight_to={data.get('weight_to')}, "
                 f"volume_from={data.get('volume_from')}, volume_to={data.get('volume_to')}")
    await asyncio.create_task(search_cargo_for_user(
        user_id,
        data['from_location'],
        data['from_type'],
        data['to_location'],
        data['to_type'],
        data.get('weight_from'),
        data.get('weight_to'),
        callback.message,
        data.get('volume_from'),
        data.get('volume_to'),
        active_searches,
        data.get('car_load_type_ids')
    ))


@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    active_searches[user_id] = False
    await callback.message.edit_text(
        "❌ <b>Действие отменено</b>\n\n"
        "Вернулись в главное меню",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "Что хотели бы сделать?",
        reply_markup=get_main_menu()
    )
    await state.clear()


@dp.message(F.text == "⛔ Остановить")
async def stop_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    active_searches[user_id] = False
    await state.clear()
    await message.answer(
        "⛔ <b>Поиск остановлен</b>\n\n"
        "Спасибо за использование! 😊",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )


@dp.message(F.text == "🔙 Главное меню")
async def back_to_main(message: Message, state: FSMContext):
    user_id = message.from_user.id
    active_searches[user_id] = False
    await state.clear()
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )


@dp.callback_query(F.data == "stop_search")
async def inline_stop_search(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    active_searches[user_id] = False
    await state.clear()
    await callback.message.edit_text(
        "⛔ <b>Поиск остановлен</b>\n\nСпасибо за использование! 😊",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "🏠 <b>Главное меню</b>",
        reply_markup=get_main_menu()
    )


async def main():
    logging.info("🚀 Запуск бота")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("⛔ Бот остановлен пользователем")
