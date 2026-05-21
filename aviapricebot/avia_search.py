import asyncio

import aiohttp
import logging
import os

from dotenv import load_dotenv
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

load_dotenv()


class AviaSearch:
    def __init__(self):
        self.api_city_code = os.getenv('API_CITY_CODE')
        self.api_calendar = os.getenv('API_CALENDAR')
        self.api_flight_search = os.getenv('API_FLIGHT_SEARCH')
        self.success_code = 200
        self.types = ['city', 'airport', 'country']
        self.locale = 'ru_RU'
        self._session: aiohttp.ClientSession | None = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_city_code(self, city_name: str) -> dict:
        url = f"{self.api_city_code}/v2/places.json"
        params = {
            'locale': self.locale,
            'max': 100,
            'term': city_name,
            'types[]': self.types
        }
        try:
            session = await self.get_session()
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if not data:
                    raise ValueError(f'Город {city_name} не найден')
                code = data[0].get("code")
                return code

        except asyncio.TimeoutError:
            logger.error(f"Таймаут при поиске города: {city_name}")
            raise ValueError(f"Сервер не ответил вовремя для города '{city_name}'")

    def get_calendar(self, origin, destination, input_month):
        codes = [origin, destination]
        month = datetime.strptime(input_month, "%d.%m.%Y").strftime("%Y-%m-01")
        url = (f'{self.api_calendar}/v5/calendar.json?'
               'brand=AS&'
               'currency=rub&'
               f'depart_months={month}&'
               f'destination_iata={codes[1]}&'
               'destination_type=CITY&'
               'locale=ru_RU&'
               'one_way=true&'
               f'origin_iata={codes[0]}&'
               'origin_type=CITY&'
               'trip_class=Y')

        return url

    async def get_data(self, url):
        try:
            session = await self.get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == self.success_code:
                    data = await response.json()
                    return data

                logger.error(f"Соединение с сервером не установлено: {response.status}")
                return None
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при запросе: {url}")
            return None

    def get_tickets_near_dates(self, data_there, data_back, start_date, end_date, days_range=3):
        """Находит билеты в диапазоне ±days_range дней от выбранных дат"""
        if not data_there or 'prices' not in data_there or not data_back or 'prices' not in data_back:
            return [], []

        # Преобразуем выбранные даты в формат YYYY-MM-DD
        start_date_formatted = f"{start_date.split('.')[2]}-{start_date.split('.')[1]}-{start_date.split('.')[0]}"
        end_date_formatted = f"{end_date.split('.')[2]}-{end_date.split('.')[1]}-{end_date.split('.')[0]}"

        # Получаем список дат в диапазоне ±3 дня для ОБЕИХ направлений
        start_dates_range = self._get_date_range(start_date_formatted, days_range)
        end_dates_range = self._get_date_range(end_date_formatted, days_range)

        # Ищем билеты "туда" в диапазоне дат (вылет из города отправления)
        tickets_there = []
        for item in data_there['prices']:
            if item.get('price', 0) > 0 and item.get('depart_date') in start_dates_range:
                tickets_there.append((item['depart_date'], item['price']))

        # Ищем билеты "обратно" в диапазоне дат (вылет из города назначения)
        tickets_back = []
        for item in data_back['prices']:
            if item.get('price', 0) > 0 and item.get('depart_date') in end_dates_range:
                tickets_back.append((item['depart_date'], item['price']))

        # Сортируем по цене (от дешевых к дорогим) и берем до 3 вариантов
        tickets_there.sort(key=lambda x: x[1])
        tickets_back.sort(key=lambda x: x[1])

        return tickets_there[:3], tickets_back[:3]

    def _get_date_range(self, base_date, days_range):
        """Генерирует список дат в диапазоне ±days_range дней от базовой даты"""
        base = datetime.strptime(base_date, "%Y-%m-%d")
        date_range = []

        for i in range(-days_range, days_range + 1):
            new_date = base + timedelta(days=i)
            date_range.append(new_date.strftime("%Y-%m-%d"))

        return date_range
