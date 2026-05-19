import asyncio
import os
import logging
import json
import sqlite3

from datetime import datetime, timedelta

from typing import Dict
from config import geo_types
from config import DB_NAME, processed_file, api_car_types, api_loading_types
logging.basicConfig(level=logging.INFO)


tasks: Dict[int, asyncio.Task] = {}
active_searches: Dict[int, bool] = {}

_car_loading_types_cache = None
_car_types_cache = None


def init_db():
    """Инициализация базы данных и создание таблиц"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица подписок
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

    # Таблица типов транспорта
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS CarTypes (
            Id INTEGER PRIMARY KEY,
            Name TEXT NOT NULL
        )
    ''')

    # Таблица типов загрузки
    cursor.execute('''
                CREATE TABLE IF NOT EXISTS CarLoadingTypes (
                    Id INTEGER PRIMARY KEY,
                    Name TEXT NOT NULL
                )
            ''')

    conn.commit()
    conn.close()


def load_users() -> list[int]:
    """Загружает список пользователей из таблицы Subscriptions"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM Subscriptions ORDER BY user_id")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


def save_user(user_id: int):
    """Добавляет пользователя в таблицу Subscriptions"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM Subscriptions WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    if not exists:
        now = datetime.now()
        cursor.execute('''
                INSERT INTO Subscriptions (user_id, start_time, end_time, is_active, subscription_type, trial_used)
                VALUES (?, ?, ?, 0, 'trial', 0)
            ''', (user_id, now, now - timedelta(days=1)))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False


def load_processed(user_id):
    """Загружает список обработанных грузов для пользователя"""
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
                if processed is None:
                    return []
                if isinstance(processed, list):
                    return processed
                else:
                    return []
        return []
    except Exception as e:
        logging.error(f"Ошибка загрузки processed для user_id {user_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return []


def save_processed(user_id, processed_cargos):
    if os.path.exists(processed_file):
        with open(processed_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
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
            'processed_cargos': processed_cargos
        })

    with open(processed_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=None)


def delete_processed():
    if os.path.exists(processed_file):
        os.remove(processed_file)


def added_car_types():
    """Загружает типы транспорта из JSON файла в БД"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM CarTypes")
    count = cursor.fetchone()[0]

    if count > 0:
        conn.close()
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
    conn.close()


def added_loading_types():
    """Загружает типы загрузки из JSON файла в БД"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM CarLoadingTypes")
    count = cursor.fetchone()[0]

    if count > 0:
        conn.close()
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
    conn.close()


def get_car_loading_types(force_refresh=False):
    """Загружает типы загрузки из БД с кэшированием"""
    global _car_loading_types_cache
    if force_refresh or _car_loading_types_cache is None:
        if not DB_NAME.exists():
            init_db()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT Id, Name FROM CarLoadingTypes")
        _car_loading_types_cache = [{"Id": row[0], "Name": row[1]} for row in cursor.fetchall()]
        conn.close()
    return _car_loading_types_cache


def get_car_types(force_refresh=False):
    """Загружает типы кузова из БД с кэшированием"""
    global _car_types_cache
    if force_refresh or _car_types_cache is None:
        if not DB_NAME.exists():
            init_db()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT Id, Name FROM CarTypes")
        _car_types_cache = [{"Id": row[0], "Name": row[1]} for row in cursor.fetchall()]
        conn.close()
    return _car_types_cache


def save_data_cargo(data):
    with open("data_cargo.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_car_types_name(ids):
    """
    Получает названия типов транспорта по их ID.
    """
    added_car_types()

    # Если ids - это список
    if isinstance(ids, list):
        id_list = [str(x) for x in ids]
    # Если ids - это строка
    elif isinstance(ids, str):
        if not ids:
            return "Не указан"
        id_list = [x.strip() for x in ids.split(",")]
    else:
        return "Не указан"

    # Получаем названия из базы данных
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    names = []
    for id_str in id_list:
        try:
            id_int = int(id_str)
            cursor.execute('SELECT Name FROM CarTypes WHERE Id = ?', (id_int,))
            result = cursor.fetchone()
            if result:
                names.append(result[0])
            else:
                names.append(f"Тип {id_int}")
        except ValueError:
            names.append(id_str)

    conn.close()
    return ", ".join(names) if names else "Не указан"


def formatted_date(date_str):
    """Форматирование даты"""
    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    formatted = dt.strftime('%d.%m.%Y')
    return formatted


def get_type_id(geo_type_name):
    """Получить ID типа гео-пункта по названию"""
    return geo_types.get(geo_type_name, 2)


def get_car_loading_type_name_by_id(car_loading_type_id):
    added_loading_types()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT Name FROM CarLoadingTypes WHERE Id = ?", (car_loading_type_id,))

    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
