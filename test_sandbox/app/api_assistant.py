import requests
import os
from dotenv import load_dotenv
from .redis_cache import RedisCache

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("URL")

cache = RedisCache()


class Assistant:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def get_data(enter_request: str) -> dict:
        return {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты кратко и по делу отвечающий ассистент.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Ответь на вопрос: \"{enter_request}\".\n"
                        "Формат ответа:\n"
                        "- без markdown (не используй ** жирный)\n"
                        "- без сносок и ссылок, без [1][2] и т.п.\n"
                        "- 2–3 коротких абзаца обычного текста.\n"
                    )}
            ],
        }

    def get_response(self, user_id: int, request: str) -> str:
        cached_answer = cache.get(user_id, request)
        if cached_answer:
            return cached_answer

        response = requests.post(API_URL, headers=self.headers, json=self.get_data(request))
        response.raise_for_status()
        res_json = response.json()
        answer = res_json["choices"][0]["message"]["content"]

        cache.set(user_id, request, answer)

        return answer
