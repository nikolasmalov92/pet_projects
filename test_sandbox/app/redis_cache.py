import os

import redis
import hashlib
from dotenv import load_dotenv

load_dotenv()
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))


class RedisCache:
    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True,
            socket_connect_timeout=5
        )

        try:
            self.client.ping()
            print("✅ Redis подключен")
        except redis.exceptions.ConnectionError:
            print("❌ Не удалось подключиться к Redis")
            self.client = None

    def clear_all(self):
        """Очистить весь кэш"""
        if not self.client:
            return "Redis не подключен"

        try:
            pattern = "ai:*"
            keys = self.client.keys(pattern)

            if keys:
                deleted = self.client.delete(*keys)
                return f"✅ Очищено {deleted} записей"
            else:
                return "📭 Кэш уже пуст"

        except Exception as e:
            return f"❌ Ошибка: {str(e)}"

    def clear_user_cache(self, user_id: int):
        """Очистить кэш конкретного пользователя"""
        if not self.client:
            return "Redis не подключен"

        try:
            pattern = f"ai:user:{user_id}:*"
            keys = self.client.keys(pattern)

            if keys:
                deleted = self.client.delete(*keys)
                return f"✅ Очищено {deleted} ваших записей"
            else:
                return "📭 Ваш кэш пуст"

        except Exception as e:
            return f"❌ Ошибка: {str(e)}"

    def get(self, user_id: int, question: str):
        """Получить ответ из кэша для пользователя"""
        if not self.client:
            return None

        try:
            key = self._make_key(user_id, question)
            return self.client.get(key)
        except:
            return None

    def set(self, user_id: int, question: str, answer: str, ttl: int = 3600):
        """Сохранить ответ в кэш для пользователя"""
        if not self.client:
            return

        try:
            key = self._make_key(user_id, question)
            self.client.setex(key, ttl, answer)
        except:
            pass

    def _make_key(self, user_id: int, question: str) -> str:
        """Создать ключ из user_id и вопроса"""
        normalized = question.strip().lower()
        question_hash = hashlib.md5(normalized.encode()).hexdigest()
        return f"ai:user:{user_id}:{question_hash}"