import requests
from storage import *


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
            if geo_type == 0:
                return data['suggestions'][0].get('country', {}).get('id')
            elif geo_type == 1:
                return data['suggestions'][0].get('region', {}).get('id')
            else:
                return data['suggestions'][0].get('city', {}).get('id')

    def get_cargo(self, from_id, from_type, to_id, to_type,
                  weight_from=None, weight_to=None,
                  volume_from=None, volume_to=None,
                  car_load_type_ids=None):
        """
        Возвращает список новых грузов с фильтрацией по весу.
        :param car_load_type_ids: Список ID типов загрузки (опционально)
        :param volume_from: Минимальный объём (опционально)
        :param volume_to: Максимальный объём (опционально)
        :param from_id: ID начальной точки
        :param from_type: Тип начальной точки
        :param to_id: ID конечной точки
        :param to_type: Тип конечной точки
        :param weight_from: Минимальный вес (опционально)
        :param weight_to: Максимальный вес (опционально)
        :return: list
        """
        global loading_type
        url = f"{self.loads_url}/webapi/v1.0/loads/search"
        payload = {
            "exclude_geo_dicts": True,
            "page": 1,
            "items_per_page": 10,
            "filter": {
                "from": {"id": from_id, "type": from_type, "exact_only": False},
                "to": {"id": to_id, "type": to_type, "exact_only": False},
                "dates": {"date_option": "today-plus"},
                "exclude_tenders": False,
                "change_date": 3,
                "extra_params": 0,
                "sorting_type": 2  # сортировка: 'добавлен сегодня'
            }
        }

        if weight_from is not None or weight_to is not None:
            payload["filter"]["weight"] = {}
            if weight_from is not None:
                payload["filter"]["weight"]["min"] = weight_from
            if weight_to is not None:
                payload["filter"]["weight"]["max"] = weight_to

        if volume_from is not None or volume_to is not None:
            payload["filter"]["volume"] = {}
            if weight_from is not None:
                payload["filter"]["volume"]["min"] = volume_from
            if weight_to is not None:
                payload["filter"]["volume"]["max"] = volume_to

        if car_load_type_ids:
            if len(car_load_type_ids) == 1:
                loading_type = str(car_load_type_ids[0])
            else:
                loading_type = str(sum(car_load_type_ids))

            payload["filter"]["loading_type"] = loading_type

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            return []

    def carTypes(self):
        url = f"{self.base_url}/v1.0/dictionaries/carTypes"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()

    @staticmethod
    def get_all_cities():
        city = []
        url = f"https://api.ati.su/v1.0/dictionaries/cities"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                city.append({"CityName": item.get("CityName")})

    @staticmethod
    def loadingTypes():
        url = f"https://api.ati.su/v1.0/dictionaries/loadingTypes"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
