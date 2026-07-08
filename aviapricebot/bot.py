import asyncio
import os
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from dotenv import load_dotenv

from avia_search import AviaSearch
from menu import menu_buy_ticket, create_calendar, get_main_menu, get_stop_keyboard
from models.search_state import SearchState
from redis_client import get_user_data, set_user_data, update_user_data, get_redis, set_last_price, get_last_price

logger = logging.getLogger(__name__)

load_dotenv()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
search = AviaSearch()
search_semaphore = asyncio.Semaphore(25)

search_tasks = {}


@dp.message(Command("start"))
async def cmd_start(message: Message):
    first_name = message.from_user.first_name or "Пользователь"
    await message.answer(
        f"🚀 <b>Взлетаем, {first_name}!</b>\n\n"
        f"Ваш умный помощник для поиска перелётов готов к работе! 🧠\n"
        f"Найдём билеты, которые не ударят по бюджету!\n\n"
        f"📍 <b>Чтобы начать поиск, нажмите на кнопку </b>\n",
        parse_mode="HTML",
        reply_markup=get_main_menu())


@dp.message(F.text == "🔍 Новый поиск")
async def new_search(message: Message):
    user_id = message.from_user.id
    r = await get_redis()
    await r.delete(f"search:{user_id}")
    await message.answer(
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

    if text.startswith('⛔ Остановить'):
        user_id = message.from_user.id
        task = search_tasks.get(user_id)
        if task and not task.done():
            task.cancel()
            await message.answer("⏸️ Поиск остановлен.")
            await message.answer(
                "Чтобы начать новый поиск, нажмите «🔍 Новый поиск» или введите города.",
                reply_markup=get_main_menu()
            )
        else:
            await message.answer("Активный поиск не найден.")

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
            f"📅 Обратно: <b>{end_date}</b>\n\n",
            parse_mode="HTML"
        )
        task = asyncio.create_task(
            search_ticket(callback.message, from_city, where_city, user_id)
        )
        search_tasks[user_id] = task


async def search_ticket(message: Message, from_city: str, where_city: str, user_id: int):
    stop_msg = await message.answer(
        f"⏳ Ищем лучшие предложения...",
        reply_markup=get_stop_keyboard()
    )
    try:
        async with search_semaphore:
            try:
                code_there, code_back = await asyncio.gather(
                    search.get_city_code(from_city),
                    search.get_city_code(where_city)
                )
            except Exception as e:
                logger.error(f"Ошибка при получении кодов городов: {e}")
                await message.answer("❌ Ошибка при поиске городов. Попробуйте позже.")
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
                    min_total = tickets_there[0][1] + tickets_back[0][1]
                    await set_last_price(user_id, min_total)
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

    except asyncio.CancelledError:
        raise
    finally:
        try:
            await stop_msg.delete()
        except Exception:
            pass
        search_tasks.pop(user_id, None)


async def price_monitor():
    """Фоновый мониторинг цен каждые 30 минут."""
    while True:
        await asyncio.sleep(60)  # 30 минут
        logger.info("Запуск проверки цен...")
        try:
            r = await get_redis()
            keys = await r.keys("search:*")
            user_ids = set()
            for key in keys:
                if not key.startswith("search:price:"):
                    try:
                        user_id = int(key.split(":")[1])
                        user_ids.add(user_id)
                    except:
                        pass

            for user_id in user_ids:
                data = await get_user_data(user_id)
                if not data or len(data.selected_dates) < 2:
                    continue
                last_price = await get_last_price(user_id)
                if last_price is None:
                    continue

                from_city = data.from_city
                where_city = data.where_city
                start_date = data.selected_dates[0]
                end_date = data.selected_dates[1]

                try:
                    code_there = await search.get_city_code(from_city)
                    code_back = await search.get_city_code(where_city)
                    current_price = await search.get_min_price_for_dates(
                        code_there, code_back, start_date, end_date
                    )
                except Exception as e:
                    logger.error(f"Ошибка проверки цены для user {user_id}: {e}")
                    continue

                if current_price is None:
                    continue

                if current_price < last_price:
                    await bot.send_message(
                        user_id,
                        f"📉 <b>Цена снизилась!</b>\n\n"
                        f"Рейс {from_city} → {where_city}\n"
                        f"📅 {start_date} – {end_date}\n"
                        f"Было: {last_price} руб.\n"
                        f"Стало: {current_price} руб.\n"
                        f"Экономия: {last_price - current_price} руб.\n\n"
                        f"Для нового поиска нажмите «🔍 Новый поиск».",
                        parse_mode="HTML"
                    )
                    await set_last_price(user_id, current_price)
                elif current_price > last_price:
                    await set_last_price(user_id, current_price)
        except Exception as e:
            logger.error(f"Ошибка в price_monitor: {e}")
            await asyncio.sleep(60)


def format_date(date_str):
    if '-' in date_str:
        year, month, day = date_str.split('-')
        return f"{day}.{month}.{year}"
    return date_str
