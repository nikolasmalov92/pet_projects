from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(is_admin: bool):
    kb = [[KeyboardButton(text="🛍 Каталог")]]
    if is_admin:
        kb.append([KeyboardButton(text="⚙️ Админка")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def back_to_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Вернуться в каталог", callback_data="catalog_0")]
    ])

    return keyboard
