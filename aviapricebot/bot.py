import asyncio
import os
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from dotenv import load_dotenv

from avia_search import AviaSearch
from menu import menu_buy_ticket, create_calendar
from models.search_state import SearchState
from redis_client import get_user_data, set_user_data, update_user_data

logger = logging.getLogger(__name__)

load_dotenv()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
search = AviaSearch()
search_semaphore = asyncio.Semaphore(25)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    first_name = message.from_user.first_name or "Пользователь"
    await message.answer(
        f"🚀 <b>Взлетаем, {first_name}!</b>\n\n"
        f"Ваш умный помощник для поиска перелётов готов к работе! 🧠\n"
        f"Найдём билеты, которые не ударят по бюджету!\n\n"
        f"📍 <b>Чтобы начать поиск, введите:</b>\n"
        f"<code>Город отправления Город назначения</code>\n\n"
        f"<i>Например:</i>\n"
        f"<code>Москва Санкт-Петербург</code>\n",
        parse_mode="HTML")


@dp.message(F.text)
async def input_cities(message: Message):
    text = message.text.strip()

    if text.startswith('/'):
        return

    if ' - ' in text:
        cities = text.split(' - ', 1)
    else:
        cities = text.split(' ', 1)

    if len(cities) < 2:
        await message.answer("❌ Пожалуйста, укажите оба города через пробел или дефис")
        return

    user_id = message.from_user.id
    state = SearchState(
        from_city=cities[0].strip(),
        where_city=cities[1].strip(),
        selected_dates=[]
    )
    await set_user_data(user_id, state)

    markup = create_calendar(selected_dates=[])
    await message.answer("Выберите две даты (вылет и обратный прилёт):", reply_markup=markup)


@dp.callback_query(F.data.startswith("nav_"))
async def process_navigation(callback: CallbackQuery):
    """Обработка навигации по месяцам"""
    _, year, month = callback.data.split('_')
    year, month = int(year), int(month)

    user_id = callback.from_user.id
    data = await get_user_data(user_id)
    if data is None:
        await callback.answer("Начните сначала: отправьте города", show_alert=True)
        return

    selected_dates = data.selected_dates

    markup = create_calendar(year, month, selected_dates)
    await callback.message.edit_reply_markup(reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("date_"))
async def process_date_selection(callback: CallbackQuery):
    """Обработка выбора даты"""
    selected_date = callback.data.replace("date_", "")
    user_id = callback.from_user.id

    data = await get_user_data(user_id)
    if data is None:
        await callback.answer("Ошибка: данные не найдены. Начните заново.", show_alert=True)
        return

    dates = data.selected_dates.copy()

    if selected_date in dates:
        dates.remove(selected_date)
        await callback.answer(f'❌ Дата {selected_date} удалена')

    else:
        if len(dates) < 2:
            dates.append(selected_date)
            await callback.answer(f"✅ Выбрана дата: {selected_date}")
        else:
            removed_date = dates[0]
            dates = dates[1:] + [selected_date]
            await callback.answer(f"✅ Заменена дата {removed_date} на {selected_date}")

    dates.sort(key=lambda x: datetime.strptime(x, "%d.%m.%Y"))
    await update_user_data(user_id, selected_dates=dates)

    markup = create_calendar(selected_dates=dates)
    await callback.message.edit_reply_markup(reply_markup=markup)

    if len(dates) == 2:
        from_city = data.from_city
        where_city = data.where_city
        start_date = dates[0]
        end_date = dates[1]

        await callback.message.edit_text(
            f"✅ <b>Параметры поиска:</b>\n\n"
            f"📍 Откуда: <b>{from_city}</b>\n"
            f"🎯 Куда: <b>{where_city}</b>\n"
            f"📅 Вылет: <b>{start_date}</b>\n"
            f"📅 Обратно: <b>{end_date}</b>\n\n"
            f"⏳ Ищем лучшие предложения...",
            parse_mode="HTML"
        )
        await search_ticket(callback.message, from_city, where_city, user_id)


async def search_ticket(message: Message, from_city: str, where_city: str, user_id: int):
    async with search_semaphore:
        try:
            code_there, code_back = await asyncio.gather(
                search.get_city_code(from_city),
                search.get_city_code(where_city)
            )
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await message.answer(
                "❌ Ошибка при поиске городов. Попробуйте позже."
            )
            return

        data = await get_user_data(user_id)
        if data is None or len(data.selected_dates) < 2:
            await message.answer("❌ Ошибка: не выбраны даты. Начните сначала.")
            return

        start_date = data.selected_dates[0]
        end_date = data.selected_dates[1]

        url_there = search.get_calendar(code_there, code_back, start_date)
        url_back = search.get_calendar(code_back, code_there, end_date)

        data_there, data_back = await asyncio.gather(
            search.get_data(url_there),
            search.get_data(url_back)
        )

        if data_there and data_back:
            tickets_there, tickets_back = search.get_tickets_near_dates(data_there, data_back, start_date, end_date)

            if tickets_there and tickets_back:
                combinations_shown = 0
                for i, ticket_there in enumerate(tickets_there[:3]):
                    for j, ticket_back in enumerate(tickets_back[:3]):
                        if combinations_shown >= 3:
                            break

                        date_there_formatted = format_date(ticket_there[0])
                        date_back_formatted = format_date(ticket_back[0])
                        total_price = ticket_there[1] + ticket_back[1]
                        date_there_url = ticket_there[0][8:10] + ticket_there[0][5:7]
                        date_back_url = ticket_back[0][8:10] + ticket_back[0][5:7]
                        buy_ticket = (f"{os.getenv('API_FLIGHT_SEARCH')}{code_there}{date_there_url}"
                                      f"{code_back}{date_back_url}1")

                        keyboard = menu_buy_ticket(buy_ticket)

                        message_text = (
                            f"🎫 <b>Вариант {combinations_shown + 1}:</b>\n\n"
                            f"✈️ Туда: {date_there_formatted}\n"
                            f"💵 Цена: {ticket_there[1]} руб.\n\n"
                            f"✈️ Обратно: {date_back_formatted}\n"
                            f"💵 Цена: {ticket_back[1]} руб.\n\n"
                            f"💰 <b>Общая стоимость: {total_price} руб.</b>"
                        )

                        await message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)
                        combinations_shown += 1
                        await asyncio.sleep(3)

            else:
                await message.answer("❌ Не удалось найти билеты в выбранном диапазоне дат. Попробуйте другие даты.")
        else:
            await message.answer("❌ Ошибка при получении данных о перелетах")


def format_date(date_str):
    if '-' in date_str:
        year, month, day = date_str.split('-')
        return f"{day}.{month}.{year}"
    return date_str
