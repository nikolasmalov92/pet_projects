import requests
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("URL")


class Assistant:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def get_data(now, now_weather, now_traffic, time_direction, topic_news):
        return {"model": "sonar-pro",
                "messages": [{"role": "user", "content": (
                                 f"Сформируй короткий утренний отчёт Текущее время: {now}\n на основе переданных "
                                 f"данных.\n"
                                 f"Данные:\n"
                                 f"- Погода: {now_weather}\n" 
                                 f"- Пробки: {now_traffic} баллов\n" 
                                 f"- Время в пути до работы: {time_direction}\n" 
                                 f"- Новости: {topic_news}\n\n" 
                                 "Требования к ответу:\n" 
                                 "- В начале ответа придумай короткое, живое приветствие. "
                                 "Каждый раз новое, без шаблонов.\n" "- Пиши живо, но по делу.\n" 
                                 "- 2–3 коротких абзаца обычного текста.\n" 
                                 "- Без markdown, без жирного текста, без ссылок и сносок.\n" 
                                 "- Не придумывай данные — используй только те, что переданы.\n" 
                                 "- Новости перечисляй кратко, в одном предложении каждая.")}]}

    def get_response(self, now, now_weather, now_traffic, time_direction, topic_news):
        response = requests.post(API_URL, headers=self.headers, json=self.get_data(now, now_weather, now_traffic,
                                                                                   time_direction, topic_news))
        response.raise_for_status()
        res_json = response.json()
        answer = res_json["choices"][0]["message"]["content"]

        return answer
