import json
from pathlib import Path
from datetime import datetime
from config import *
import sqlite3

carTypes_file = Path("car_types.json")
processed_file = Path("processed.json")
DB_NAME = Path("database.db")


def init_db():
    """Инициализация базы данных и создание таблиц"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS Users (id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()


def load_users() -> list[int]:
    """Загружает список пользователей из таблицы User"""
    if not Path(DB_NAME).exists():
        init_db()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Users ORDER BY id")
    users = [row[0] for row in cursor.fetchall()]
    return users


def save_user(user_id: int):
    """Добавляет пользователя в таблицу User"""
    if not Path(DB_NAME).exists():
        init_db()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO Users (id) VALUES (?)", (user_id,))
    conn.commit()
    if cursor.rowcount > 0:
        return True

    else:
        return False


def load_processed(user_id):
    if os.path.exists(processed_file):
        with open(processed_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for user_data in data:
                if user_data.get('user_id') == str(user_id):
                    return user_data.get('processed_cargos', [])
    else:
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


def load_car_types():
    if not Path(DB_NAME).exists():
        init_db()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT Id, Name FROM CarTypes")
    data = []
    for row in cursor.fetchall():
        data.append({
            "Id": row[0],
            "Name": row[1]
        })

    conn.close()
    return data


def get_car_loading_types():
    if not Path(DB_NAME).exists():
        init_db()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT Id, Name FROM CarLoadingTypes")
    data = []
    for row in cursor.fetchall():
        data.append({
            "Id": row[0],
            "Name": row[1]
        })

    conn.close()
    return data


def save_data_cargo(data):
    with open("data_cargo.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_car_types_name(ids):
    data = load_car_types()
    id_list = [x.strip() for x in ids.split(",")]

    names = [i.get("Name") for i in data if str(i.get("Id")) in id_list]
    return ", ".join(names) if names else "Не найдено"


def formatted_date(date_str):
    """Форматирование даты"""
    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    formatted = dt.strftime('%d.%m.%Y')
    return formatted


def get_type_id(geo_type_name):
    """Получить ID типа гео-пункта по названию"""
    return geo_types.get(geo_type_name, 2)


def get_car_loading_type_name_by_id(car_loading_type_id):
    if not Path(DB_NAME).exists():
        init_db()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT Name FROM CarLoadingTypes WHERE Id = ?", (car_loading_type_id,))

    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
