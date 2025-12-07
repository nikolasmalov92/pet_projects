from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def admin_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар")],
            [KeyboardButton(text="🗑 Удалить товар")],
            [KeyboardButton(text="👈 Назад")],
        ],
        resize_keyboard=True
    )
