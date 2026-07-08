import asyncio
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, Optional

from config import geo_types, DB_NAME, processed_file, api_car_types, api_loading_types

logger = logging.getLogger(__name__)

# Глобальное состояние
tasks: Dict[int, asyncio.Task] = {}
active_searches: Dict[int, bool] = {}

# Кэши
_car_loading_types_cache: Optional[list] = None
_car_types_cache: Optional[list] = None


@contextmanager
def get_db_connection():
    """Контекстный менеджер для соединения с БД."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Инициализация базы данных и создание таблиц."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Subscriptions (
                user_id INTEGER PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                subscription_type TEXT NOT NULL DEFAULT 'trial',
                trial_used BOOLEAN DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS CarTypes (
                Id INTEGER PRIMARY KEY,
                Name TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS CarLoadingTypes (
                Id INTEGER PRIMARY KEY,
                Name TEXT NOT NULL
            )
        ''')

        conn.commit()


def load_users() -> list[int]:
    """Загружает список пользователей из таблицы Subscriptions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT user_id FROM Subscriptions ORDER BY user_id")
        return [row[0] for row in cursor.fetchall()]


def save_user(user_id: int) -> bool:
    """Добавляет пользователя в таблицу Subscriptions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM Subscriptions WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            return False

        now = datetime.now()
        cursor.execute('''
            INSERT INTO Subscriptions (user_id, start_time, end_time, is_active, subscription_type, trial_used)
            VALUES (?, ?, ?, 0, 'trial', 0)
        ''', (user_id, now, now - timedelta(days=1)))
        conn.commit()
        return True


def load_processed(user_id: int) -> list:
    """Загружает список обработанных грузов для пользователя."""
    try:
        if not os.path.exists(processed_file):
            return []

        with open(processed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        for user_data in data:
            if isinstance(user_data, dict) and user_data.get('user_id') == str(user_id):
                processed = user_data.get('processed_cargos')
                return processed if isinstance(processed, list) else []

        return []
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Ошибка загрузки processed для user_id {user_id}: {e}")
        return []


def save_processed(user_id: int, processed_cargos: list):
    """Сохраняет список обработанных грузов."""
    data = []
    if os.path.exists(processed_file):
        try:
            with open(processed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        except (json.JSONDecodeError, IOError):
            data = []

    user_found = False
    for user_data in data:
        if user_data.get('user_id') == str(user_id):
            user_data['processed_cargos'] = processed_cargos
            user_found = True
            break

    if not user_found:
        data.append({
            'user_id': str(user_id),
            'processed_cargos': processed_cargos,
        })

    try:
        with open(processed_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=None)
    except IOError as e:
        logger.error(f"Ошибка сохранения processed: {e}")


def delete_processed():
    """Удаляет файл processed.json."""
    if os.path.exists(processed_file):
        os.remove(processed_file)


def added_car_types():
    """Загружает типы транспорта из JSON файла в БД."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM CarTypes")
        if cursor.fetchone()[0] > 0:
            return

        with open(api_car_types, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data if isinstance(data, list) else data.get('data', [])
        for item in items:
            id = item.get('Id')
            name = item.get('Name')
            if id and name:
                cursor.execute("INSERT INTO CarTypes (Id, Name) VALUES (?, ?)", (id, name))

        conn.commit()


def added_loading_types():
    """Загружает типы загрузки из JSON файла в БД."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM CarLoadingTypes")
        if cursor.fetchone()[0] > 0:
            return

        with open(api_loading_types, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data if isinstance(data, list) else data.get('data', [])
        for item in items:
            id = item.get('Id')
            name = item.get('Name')
            if id and name:
                cursor.execute("INSERT INTO CarLoadingTypes (Id, Name) VALUES (?, ?)", (id, name))

        conn.commit()


def get_car_loading_types(force_refresh: bool = False) -> list:
    """Загружает типы загрузки из БД с кэшированием."""
    global _car_loading_types_cache
    if force_refresh or _car_loading_types_cache is None:
        if not DB_NAME.exists():
            init_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Id, Name FROM CarLoadingTypes")
            _car_loading_types_cache = [{"Id": row[0], "Name": row[1]} for row in cursor.fetchall()]
    return _car_loading_types_cache


def get_car_types(force_refresh: bool = False) -> list:
    """Загружает типы кузова из БД с кэшированием."""
    global _car_types_cache
    if force_refresh or _car_types_cache is None:
        if not DB_NAME.exists():
            init_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Id, Name FROM CarTypes")
            _car_types_cache = [{"Id": row[0], "Name": row[1]} for row in cursor.fetchall()]
    return _car_types_cache


def save_data_cargo(data):
    """Сохраняет данные о грузах в JSON файл."""
    with open("data_cargo.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_car_types_name(ids) -> str:
    """Получает названия типов транспорта по их ID."""
    added_car_types()

    if isinstance(ids, list):
        id_list = [str(x) for x in ids]
    elif isinstance(ids, str):
        if not ids:
            return "Не указан"
        id_list = [x.strip() for x in ids.split(",")]
    else:
        return "Не указан"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        names = []
        for id_str in id_list:
            try:
                id_int = int(id_str)
                cursor.execute('SELECT Name FROM CarTypes WHERE Id = ?', (id_int,))
                result = cursor.fetchone()
                names.append(result[0] if result else f"Тип {id_int}")
            except ValueError:
                names.append(id_str)

    return ", ".join(names) if names else "Не указан"


def formatted_date(date_str: str) -> str:
    """Форматирование даты."""
    if not date_str:
        return "Нет данных"
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d.%m.%Y')
    except (ValueError, AttributeError) as e:
        logger.warning(f"Ошибка форматирования даты '{date_str}': {e}")
        return "Нет данных"


def get_type_id(geo_type_name: str) -> int:
    """Получить ID типа гео-пункта по названию."""
    return geo_types.get(geo_type_name, 2)


def get_car_loading_type_name_by_id(car_loading_type_id: str) -> Optional[str]:
    """Получает название типа загрузки по ID."""
    added_loading_types()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT Name FROM CarLoadingTypes WHERE Id = ?", (car_loading_type_id,))
        result = cursor.fetchone()
        return result[0] if result else None
