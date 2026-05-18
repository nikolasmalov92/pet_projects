import requests


class Pogoda:
    def __init__(self):
        self.url = "https://mobile-weather.api.2gis.ru/api/1.0/forecast"
        self.lat = 55.801713
        self.lon = 49.112377
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " "AppleWebKit/537.36 (KHTML, like Gecko) " "Chrome/143.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*", "Origin": "https://2gis.ru",
            "Referer": "https://2gis.ru/kazan", }

    def get_weather(self):
        params = {"lon": self.lon, "lat": self.lat, "locale": "ru_RU"}
        r = requests.get(self.url, headers=self.headers, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            current = data["current"]
            return (
                f'Температура: {int(current["temperature"]["air"])}°C (ощущается как {int(current["temperature"]["feels"])}°C)\n'
                f'Облачность: {current.get("weather_description", "").strip()}\n'
                f'Ветер: {current["wind"]["speed"]} м/с\n'
                f'{current.get("hint", "").strip()}')

