import asyncio
import json
import logging
from typing import Optional

import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import base_url, loads_url, headers

logger = logging.getLogger(__name__)

# Настройки retry для синхронных запросов
SYNC_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST", "GET"],
)

# Настройки для асинхронных запросов
ASYNC_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=10)
ASYNC_RETRY_ATTEMPTS = 5
ASYNC_RETRY_DELAY = 3  # секунды


class AtiClient:
    def __init__(self):
        self.base_url = base_url
        self.loads_url = loads_url
        # Сессия с retry для синхронных запросов
        self._sync_session = requests.Session()
        self._sync_session.mount("https://", HTTPAdapter(max_retries=SYNC_RETRY_STRATEGY))
        self._sync_session.mount("http://", HTTPAdapter(max_retries=SYNC_RETRY_STRATEGY))
        # Переиспользуемая асинхронная сессия
        self._async_session: Optional[aiohttp.ClientSession] = None
        # Кэш городов: (name, geo_type) -> city_id (или None если не найден)
        self._city_cache: dict[tuple[str, int], Optional[int]] = {}

    async def _get_async_session(self) -> aiohttp.ClientSession:
        """Возвращает переиспользуемую асинхронную сессию."""
        if self._async_session is None or self._async_session.closed:
            self._async_session = aiohttp.ClientSession(timeout=ASYNC_TIMEOUT)
        return self._async_session

    async def close(self):
        """Закрывает асинхронную сессию."""
        if self._async_session and not self._async_session.closed:
            try:
                await self._async_session.close()
            except Exception:
                pass

    async def _make_async_request(
        self,
        method: str,
        url: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Optional[dict]:
        """Выполняет асинхронный HTTP запрос с retry логикой."""
        for attempt in range(ASYNC_RETRY_ATTEMPTS):
            try:
                session = await self._get_async_session()
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    json=json_data,
                    params=params,
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", ASYNC_RETRY_DELAY))
                        logger.warning(f"Rate limit на {url}, ожидание {retry_after}с")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        text = await response.text()
                        logger.error(f"API error {response.status}: {text}")
                        # 503/504 — транзиентные ошибки, повторяем с backoff
                        if response.status in (503, 504):
                            if attempt < ASYNC_RETRY_ATTEMPTS - 1:
                                delay = ASYNC_RETRY_DELAY * (2 ** attempt)
                                logger.warning(f"Транзиентная ошибка {response.status}, повтор через {delay}с")
                                await asyncio.sleep(delay)
                                continue
                        # 404 — перманентная ошибка, не повторяем
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Timeout на {url} (попытка {attempt + 1}/{ASYNC_RETRY_ATTEMPTS})")
                if attempt < ASYNC_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(ASYNC_RETRY_DELAY * (attempt + 1))
            except aiohttp.ClientError as e:
                logger.error(f"Сетевая ошибка на {url}: {e}")
                if attempt < ASYNC_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(ASYNC_RETRY_DELAY * (attempt + 1))
            except asyncio.CancelledError:
                # Задача отменена - пробрасываем дальше
                raise
            except Exception as e:
                logger.error(f"Неожиданная ошибка при запросе к {url}: {e}", exc_info=True)
                return None
        return None

    @staticmethod
    def _extract_geo(suggestion: dict, geo_type: int) -> tuple[Optional[int], int]:
        """Возвращает (id, cargo_type) из suggestion.
        cargo_type: 0=страна, 1=регион, 2=город (ожидает грузовой API).
        """
        type_keys = {0: 'country', 1: 'region', 2: 'city'}
        # API type → cargo type
        api_to_cargo = {1: 2, 2: 1, 4: 0}
        api_type_to_key = {1: 'city', 2: 'region', 4: 'country'}
        # 1. Точное совпадение по запрошенному типу
        obj = suggestion.get(type_keys.get(geo_type))
        if obj and obj.get('id'):
            return obj['id'], geo_type
        # 2. Из ответа API — маппим API type → cargo type
        api_type = suggestion.get('type')
        if api_type in api_type_to_key:
            obj = suggestion.get(api_type_to_key[api_type])
            if obj and obj.get('id'):
                return obj['id'], api_to_cargo[api_type]
        return None, geo_type

    async def _autocomplete(self, name: str) -> Optional[dict]:
        """Один запрос к автокомплиту."""
        url = f"{self.base_url}/gw/gis-dict/v1/autocomplete/suggestions"
        payload = {
            "prefix": name,
            "suggestion_types": 15,
            "limit": 10,
            "country_id": 1,
        }
        data = await self._make_async_request("POST", url, json_data=payload)
        if data:
            suggestions = data.get('suggestions', [])
            if suggestions:
                first = suggestions[0]
                return first
        return None

    def _autocomplete_sync(self, name: str) -> Optional[dict]:
        """Синхронный вариант _autocomplete."""
        url = f"{self.base_url}/gw/gis-dict/v1/autocomplete/suggestions"
        payload = {
            "prefix": name,
            "suggestion_types": 15,
            "limit": 10,
            "country_id": 1,
        }
        try:
            response = self._sync_session.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                data = response.json()
                suggestions = data.get('suggestions', [])
                if suggestions:
                    return suggestions[0]
            else:
                logger.warning(f"[autocomplete] '{name}' → HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка автокомплита '{name}': {e}")
        return None

    def get_city_id(self, name: str, geo_type: int = 2) -> tuple[Optional[int], int]:
        """Возвращает (id, geo_type) (синхронный)."""
        suggestion = self._autocomplete_sync(name)
        if suggestion:
            return self._extract_geo(suggestion, geo_type)
        return None, geo_type

    async def get_city_id_async(self, name: str, geo_type: int = 2) -> tuple[Optional[int], int]:
        """Возвращает (id, geo_type) с кэшированием."""
        cache_key = (name.lower().strip(), geo_type)
        if cache_key in self._city_cache:
            cached = self._city_cache[cache_key]
            return cached

        suggestion = await self._autocomplete(name)
        result = (None, geo_type)
        if suggestion:
            result = self._extract_geo(suggestion, geo_type)
        self._city_cache[cache_key] = result
        return result

    def get_cargo(
        self,
        from_id: int,
        from_type: int,
        to_id: Optional[int],
        to_type: Optional[int],
        weight_min: Optional[float] = None,
        weight_max: Optional[float] = None,
        volume_from: Optional[float] = None,
        volume_to: Optional[float] = None,
        car_load_type_ids: Optional[list] = None,
        car_type_ids: Optional[list] = None,
        from_radius: Optional[int] = None,
        to_radius: Optional[int] = None,
        any_direction: bool = False,
    ) -> dict:
        """Возвращает список новых грузов (синхронный метод с retry)."""
        url = f"{self.loads_url}/webapi/v1.0/loads/search"
        payload = self._build_cargo_payload(
            from_id, from_type, to_id, to_type,
            weight_min, weight_max, volume_from, volume_to,
            car_load_type_ids, car_type_ids,
            from_radius, to_radius, any_direction,
        )
        try:
            response = self._sync_session.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении грузов: {e}")
        return {"totalItems": 0, "loads": []}

    async def get_cargo_async(
        self,
        from_id: int,
        from_type: int,
        to_id: Optional[int],
        to_type: Optional[int],
        weight_min: Optional[float] = None,
        weight_max: Optional[float] = None,
        volume_from: Optional[float] = None,
        volume_to: Optional[float] = None,
        car_load_type_ids: Optional[list] = None,
        car_type_ids: Optional[list] = None,
        from_radius: Optional[int] = None,
        to_radius: Optional[int] = None,
        any_direction: bool = False,
    ) -> dict:
        """Асинхронный вариант get_cargo."""
        url = f"{self.loads_url}/webapi/v1.0/loads/search"
        payload = self._build_cargo_payload(
            from_id, from_type, to_id, to_type,
            weight_min, weight_max, volume_from, volume_to,
            car_load_type_ids, car_type_ids,
            from_radius, to_radius, any_direction,
        )
        data = await self._make_async_request("POST", url, json_data=payload)
        return data if data else {"totalItems": 0, "loads": []}

    @staticmethod
    def _build_cargo_payload(
        from_id: int,
        from_type: int,
        to_id: Optional[int],
        to_type: Optional[int],
        weight_min: Optional[float],
        weight_max: Optional[float],
        volume_from: Optional[float],
        volume_to: Optional[float],
        car_load_type_ids: Optional[list],
        car_type_ids: Optional[list],
        from_radius: Optional[int],
        to_radius: Optional[int],
        any_direction: bool,
    ) -> dict:
        """Формирует payload для поиска грузов."""
        from_filter = {"id": from_id, "type": from_type, "exact_only": True}
        if from_radius and from_radius > 0:
            from_filter["fromRadius"] = from_radius

        to_filter = None
        if not any_direction and to_id:
            to_filter = {"id": to_id, "type": to_type, "exact_only": True}
            if to_radius and to_radius > 0:
                to_filter["toRadius"] = to_radius

        payload = {
            "exclude_geo_dicts": True,
            "page": 1,
            "items_per_page": 10,
            "filter": {
                "from": from_filter,
                "dates": {"date_option": "today-plus"},
                "exclude_tenders": False,
                "extra_params": 0,
                "sorting_type": 2,
            },
        }

        if to_filter:
            payload["filter"]["to"] = to_filter

        if weight_min is not None or weight_max is not None:
            payload["filter"]["weight"] = {}
            if weight_min is not None:
                payload["filter"]["weight"]["min"] = weight_min
            if weight_max is not None:
                payload["filter"]["weight"]["max"] = weight_max

        if volume_from is not None or volume_to is not None:
            payload["filter"]["volume"] = {}
            if volume_from is not None:
                payload["filter"]["volume"]["min"] = volume_from
            if volume_to is not None:
                payload["filter"]["volume"]["max"] = volume_to

        if car_load_type_ids:
            loading_type_mask = 0
            for type_id in car_load_type_ids:
                loading_type_mask |= type_id
            payload["filter"]["loading_type"] = str(loading_type_mask)

        if car_type_ids:
            car_type_mask = 0
            for type_id in car_type_ids:
                car_type_mask |= type_id
            payload["filter"]["truck_type"] = str(car_type_mask)

        return payload

    def carTypes(self) -> list:
        url = f"{self.base_url}/v1.0/dictionaries/carTypes"
        try:
            response = self._sync_session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                with open("api_car_types.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении типов транспорта: {e}")
        return []

    def get_all_cities(self) -> list:
        city = []
        url = f"https://api.ati.su/v1.0/dictionaries/cities"
        try:
            response = self._sync_session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    city.append({"CityName": item.get("CityName")})
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении списка городов: {e}")
        return city

    def loadingTypes(self) -> list:
        url = f"https://api.ati.su/v1.0/dictionaries/loadingTypes"
        try:
            response = self._sync_session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                with open("api_loading_types.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении типов загрузки: {e}")
        return []

    def currencyTypes(self) -> list:
        url = f"https://api.ati.su/v1.0/dictionaries/currencyTypes"
        try:
            response = self._sync_session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                with open("api_currency_types.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении типов валют: {e}")
        return []
