import json
import redis.asyncio as aioredis
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

redis: aioredis.Redis = None


async def get_redis() -> aioredis.Redis:
    """ Создаём одно соединение на всё приложение """
    global redis
    if redis is None:
        redis = await aioredis.from_url(
            os.environ.get('REDIS_URL', 'redis://localhost:6379'),
            encoding='utf-8',
            decode_responses=True
        )
    return redis


async def set_user_data(user_id: int, data: dict, ttl: int = 3600):
    """ Сохраняем данные пользователя. """
    try:
        r = await get_redis()
        await r.setex(f"search:{user_id}", ttl, json.dumps(data))
    except Exception as e:
        logger.error(f"Redis set error for user {user_id}: {e}")


async def get_user_data(user_id: int) -> dict:
    """ Читаем двнные пользователя """
    try:
        r = await get_redis()
        raw_data = await r.get(f"search:{user_id}")
        if raw_data is None:
            return {}
        return json.loads(raw_data)
    except Exception as e:
        logger.error(f"Redis get error for user {user_id}: {e}")
        return {}


async def update_user_data(user_id: int, **kwargs):
    """ Обновляем отдельные поля — не перезаписываем всё целиком. """
    try:
        data = await get_user_data(user_id)
        data.update(kwargs)
        await set_user_data(user_id, data)
    except Exception as e:
        logger.error(f"Redis update error for user {user_id}: {e}")