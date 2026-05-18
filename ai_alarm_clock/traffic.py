import requests
import re


class Traffic:
    def __init__(self):
        self.jam_url = "https://jam.api.2gis.com/scores"
        self.jam_params = {
            "view": "49.112377,55.801713,49.112377,55.801713",
            "z": 11
        }
        self.jam_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/143.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://2gis.ru/kazan?traffic",
            "Origin": "https://2gis.ru",
        }

        self.directions_url = ("https://2gis.ru/kazan/directions/points/49.080694%2C55.824037%3B2956122910632202%7C49"
                               ".106758%2C55.764897%3B2956122910632998?m=49.09404%2C55.795304%2F12.81")
        self.directions_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/143.0.0.0 Safari/537.36"
        }

    def get_traffic_score(self):
        r = requests.get(self.jam_url, params=self.jam_params, headers=self.jam_headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data['projects'][0]['score']

    def get_direction(self):
        r = requests.get(self.directions_url, headers=self.directions_headers, timeout=10)
        if r.status_code == 200:
            data = r.text
            m = re.search(r'"ui_total_duration"\s*:\s*"([^"]+)"', data)
            return m.group(1)
