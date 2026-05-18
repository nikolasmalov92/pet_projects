import json
import logging
import requests

from Gruzii.config import base_url, loads_url, headers

logging.basicConfig(level=logging.INFO)


class AtiClient:
    def __init__(self):
        self.base_url = base_url
        self.loads_url = loads_url

    def get_city_id(self, name, geo_type=2):
        """
        Возвращает id города
        - suggestion_types(населённый пункт: 1 - город, 2 - регион, 4 - страна, 8 - направление))

        :return: id
        """
        ati_type_map = {0: 4, 1: 2, 2: 1}
        url = f"{self.base_url}/gw/gis-dict/v1/autocomplete/suggestions"
        payload = {
            "prefix": name,
            "suggestion_types": ati_type_map.get(geo_type, 1),
            "limit": 10
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            if data.get('suggestions'):
                if geo_type == 0:
                    return data['suggestions'][0].get('country', {}).get('id')
                elif geo_type == 1:
                    return data['suggestions'][0].get('region', {}).get('id')
                else:
                    return data['suggestions'][0].get('city', {}).get('id')
        return None

    def get_cargo(self, from_id, from_type, to_id, to_type,
                  weight_min=None, weight_max=None,
                  volume_from=None, volume_to=None,
                  car_load_type_ids=None,
                  car_type_ids=None,
                  from_radius=None, to_radius=None, any_direction=False):
        """
        Возвращает список новых грузов с фильтрацией по весу, объёму и радиусу.

        :param from_id: ID начальной точки
        :param from_type: Тип начальной точки
        :param to_id: ID конечной точки
        :param to_type: Тип конечной точки
        :param weight_min: Минимальный вес (опционально)
        :param weight_max: Максимальный вес (опционально)
        :param volume_from: Минимальный объём (опционально)
        :param volume_to: Максимальный объём (опционально)
        :param car_load_type_ids: Список ID типов загрузки (опционально)
        :param car_type_ids: Список ID типов кузова (опционально)
        :param from_radius: Радиус от точки отправления в км (опционально)
        :param to_radius: Радиус от точки назначения в км (опционально)
        :param any_direction: Искать без ограничения направления (опционально)
        :return: dict
        """
        url = f"{self.loads_url}/webapi/v1.0/loads/search"

        # Формируем фильтр для точки отправления
        from_filter = {"id": from_id, "type": from_type, "exact_only": False}
        if from_radius and from_radius > 0:
            from_filter["fromRadius"] = from_radius

        # Формируем фильтр для точки назначения (только если не режим "любое направление")
        to_filter = None
        if not any_direction and to_id:
            to_filter = {"id": to_id, "type": to_type, "exact_only": False}
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
                "change_date": "today",
                "sorting_type": 2,  # сортировка: 'добавлен сегодня'
            }
        }

        # Добавляем точку назначения только если есть
        if to_filter:
            payload["filter"]["to"] = to_filter

        # Фильтр по весу
        if weight_min is not None or weight_max is not None:
            payload["filter"]["weight"] = {}
            if weight_min is not None:
                payload["filter"]["weight"]["min"] = weight_min
            if weight_max is not None:
                payload["filter"]["weight"]["max"] = weight_max

        # Фильтр по объёму
        if volume_from is not None or volume_to is not None:
            payload["filter"]["volume"] = {}
            if volume_from is not None:
                payload["filter"]["volume"]["min"] = volume_from
            if volume_to is not None:
                payload["filter"]["volume"]["max"] = volume_to

        # Фильтр по типу загрузки
        if car_load_type_ids:
            loading_type_mask = 0
            for type_id in car_load_type_ids:
                loading_type_mask |= type_id
            payload["filter"]["loading_type"] = str(loading_type_mask)

        # Фильтр по типу кузова
        if car_type_ids:
            car_type_mask = 0
            for type_id in car_type_ids:
                car_type_mask |= type_id
            payload["filter"]["truck_type"] = str(car_type_mask)

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logging.error(f'-- API error: {response.status_code} - {response.text}')
            return {'totalItems': 0, 'loads': []}

    def carTypes(self):
        url = f"{self.base_url}/v1.0/dictionaries/carTypes"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            with open("api_car_types.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return []

    @staticmethod
    def get_all_cities():
        city = []
        url = f"https://api.ati.su/v1.0/dictionaries/cities"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                city.append({"CityName": item.get("CityName")})
        return city

    @staticmethod
    def loadingTypes():
        url = f"https://api.ati.su/v1.0/dictionaries/loadingTypes"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            with open("api_loading_types.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return []

    @staticmethod
    def currencyTypes():
        url = f"https://api.ati.su/v1.0/dictionaries/currencyTypes"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            with open("api_currency_types.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return []
