import random
import re
import string
from datetime import datetime
from pathlib import Path

from aiogram.types import (
    InputMediaPhoto,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)

ITEMS_PER_PAGE = 6

PHOTOS_DIR = Path(__file__).parent.parent / "media" / "products"


def clean_filename(filename: str) -> str:
    if not filename:
        return "no_photo.jpg"

    filename = filename.replace('\\', '/')

    if '/' in filename:
        filename = filename.split('/')[-1]
    filename = filename.strip()

    filename = filename.replace(' ', '_')

    filename = re.sub(r'[^\w\.\-]', '', filename)

    return filename


def get_photo_file(photo_filename: str):
    search_names = []

    search_names.append(photo_filename.strip())

    if '\\' in photo_filename:
        search_names.append(photo_filename.split('\\')[-1].strip())
    if '/' in photo_filename:
        search_names.append(photo_filename.split('/')[-1].strip())

    if ' ' in photo_filename:
        search_names.append(photo_filename.replace(' ', '_'))

    for name in search_names[:]:
        if name.startswith('product_'):
            search_names.append(name.replace('product_', '', 1))

    search_names = list(set(search_names))

    for search_name in search_names:
        file_path = PHOTOS_DIR / search_name

        if file_path.exists():
            return FSInputFile(file_path)


def get_price_catalog(price):
    if price is not None:
        if isinstance(price, (int, float)):
            price_num = float(price)
            price_text = f"{int(price_num):,}₽".replace(',', ' ')
        elif isinstance(price, str):
            price_match = re.search(r'[\d\s.,]+', price)
            if price_match:
                price_str = price_match.group().replace(' ', '').replace(',', '.')
                try:
                    price_num = float(price_str)
                    price_text = f"{int(price_num):,}₽".replace(',', ' ')
                except ValueError:
                    price_text = price.strip()
            else:
                price_text = price.strip()
        else:
            price_text = str(price)
    else:
        price_text = "Цена по запросу"

    return price_text


def get_description(description):
    if description is not None:
        if isinstance(description, str):
            description_text = description.strip()
            for prefix in ["Описание:", "description:", "Description:"]:
                if description_text.startswith(prefix):
                    description_text = description_text[len(prefix):].strip()
                    break
        else:
            description_text = str(description)
    else:
        description_text = ""

    return description_text


def build_catalog_simple(products: list, page: int = 0):
    if not products:
        return None, None

    if page >= len(products):
        page = len(products) - 1
    if page < 0:
        page = 0

    product = products[page]

    if len(product) >= 5:
        prod_id, name, description, price, photo_filename = product[:5]
    else:
        return None, None

    result_price = get_price_catalog(price)
    result_description = get_description(description)

    try:
        photo = get_photo_file(photo_filename)
    except Exception as e:
        print(f"Error getting photo: {e}")
        photo = get_photo_file("no_photo.jpg")

    lines = []

    # Название
    lines.append(f"<b>{name}</b>")
    lines.append("")

    # Описание
    if result_description and result_description.strip():
        desc = result_description.strip()
        if len(desc) > 250:
            desc = desc[:250] + "..."
        lines.append(f"📝 <b>Описание:</b>")
        lines.append(f" {desc}")

    # Цена
    lines.append("")
    lines.append(f"💰 <b>Цена:</b> {result_price}")
    lines.append("")
    lines.append(f"<i>Товар {page + 1} из {len(products)}</i>")

    caption = "\n".join(lines)

    media = InputMediaPhoto(
        media=photo,
        caption=caption,
        parse_mode="HTML"
    )
    buttons = []

    buttons.append([
        InlineKeyboardButton(text="🛒 Купить", callback_data=f"add_{prod_id}"),
    ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"catalog_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(
        text=f"{page + 1}/{len(products)}",
        callback_data="catalog_info"
    ))

    if page < len(products) - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"catalog_{page + 1}"))

    buttons.append(nav_buttons)

    buttons.append([
        InlineKeyboardButton(text="💬 Консультация", callback_data="consult")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    return media, keyboard


def generate_order_code(user_id: int) -> str:
    timestamp = datetime.now().strftime("%d%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"ORD{user_id % 1000:03d}{timestamp}{random_part}"


def generate_payment_code() -> str:
    return f"PB{random.randint(1000, 9999)}"
