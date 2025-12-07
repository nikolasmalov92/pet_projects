from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import *
from storage import get_car_loading_types


def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти грузы")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard


def get_type_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏙️ Город"), KeyboardButton(text="🌍 Регион")],
            [KeyboardButton(text="🗺️ Страна")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите тип географической точки..."
    )
    return keyboard


def menu_details(load_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Подробнее", url=f"{loads_url}/loadinfo/{load_id}")]
    ])
    return keyboard


def get_search_controls():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⛔ Остановить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard


def get_confirmation_keyboard(action_data):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, начать поиск", callback_data=f"confirm_{action_data}"),
            InlineKeyboardButton(text="⚙️ Фильтр", callback_data=f"filter_{action_data}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ]
    ])
    return keyboard


def get_filter_setup_keyboard():
    """Клавиатура для настройки фильтров"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚖️ Вес", callback_data="setup_weight"),
            InlineKeyboardButton(text="📦 Объем", callback_data="setup_volume"),
            InlineKeyboardButton(text="🚚📦 Тип загрузки", callback_data="setup_car_load_type")
        ],
        [
            InlineKeyboardButton(text="✅ Завершить настройку", callback_data="finish_filters")
        ]
    ])
    return keyboard


def get_weight_range_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="MIN", callback_data="weight_min"),
            InlineKeyboardButton(text="MAX", callback_data="weight_max")
        ],
        [
            InlineKeyboardButton(text="Пропустить", callback_data="weight_skip")
        ]
    ])
    return keyboard


def get_volume_range_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="MIN", callback_data="volume_min"),
            InlineKeyboardButton(text="MAX", callback_data="volume_max")
        ],
        [
            InlineKeyboardButton(text="Пропустить", callback_data="volume_skip")
        ]
    ])
    return keyboard


def get_car_load_type_keyboard(selected_ids=None):
    """Клавиатура для выбора типа загрузки из БД"""
    if selected_ids is None:
        selected_ids = []

    load_types = get_car_loading_types()

    keyboard = []

    for load_type in load_types:
        is_selected = load_type["Id"] in selected_ids
        emoji = "✔️" if is_selected else "◻️"
        text = f"{emoji} {load_type['Name']}"
        callback_data = f"toggle_load_type_{load_type['Id']}"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton(text="🆗 Применить", callback_data="apply_load_type_selection")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
