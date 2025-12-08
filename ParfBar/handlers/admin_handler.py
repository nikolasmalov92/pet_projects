import json
import os

from aiogram import Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from dotenv import load_dotenv
from aiogram import Bot

from menu.admin_menu import admin_menu_kb
from menu.main_menu import main_menu
from database.db import add_product, get_all_products, delete_product

MEDIA_DIR = "media/products"
os.makedirs(MEDIA_DIR, exist_ok=True)

load_dotenv()
ADMIN_ID = json.loads(os.getenv('ADMIN_ID', '[]'))
router = Router()


class AdminStates(StatesGroup):
    add_name = State()
    add_description = State()
    add_price = State()
    add_photo = State()
    delete_id = State()


@router.message(F.text == "⚙️ Админка")
async def admin_entry(message: Message):
    if message.from_user.id not in ADMIN_ID:
        return

    await message.answer("Админ‑панель. Выберите действие:", reply_markup=admin_menu_kb())


@router.message(F.text == "➕ Добавить товар")
async def add_product_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return
    await state.set_state(AdminStates.add_name)
    await message.answer("Введите название товара:")


@router.message(AdminStates.add_name)
async def add_product_name(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return
    await state.update_data(name=message.text)
    await state.set_state(AdminStates.add_description)
    await message.answer("Введите описание товара:")


@router.message(AdminStates.add_description)
async def add_product_description(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return
    await state.update_data(description=message.text)
    await state.set_state(AdminStates.add_price)
    await message.answer("Введите цену (число):")


@router.message(AdminStates.add_price)
async def add_product_price(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    price = float(message.text.replace(",", "."))

    await state.update_data(price=price)
    await state.set_state(AdminStates.add_photo)
    await message.answer("Отправьте фото товара одним сообщением:")


@router.message(AdminStates.add_photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_ID:
        return

    data = await state.get_data()
    name = data["name"]
    description = data["description"]
    price = data["price"]

    file_name = f"product_{name}_{message.photo[-1].file_unique_id}.jpg"
    file_path = os.path.join(MEDIA_DIR, file_name)
    await bot.download(message.photo[-1], destination=file_path)

    add_product(name=name, description=description, price=price, image_path=file_path)
    await state.clear()
    await message.answer(
        f"Товар {name} добавлен.\n"
        f"Цена: {price} ₽",
        reply_markup=admin_menu_kb()
    )


@router.message(F.text == "🗑 Удалить товар")
async def delete_product_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    products = get_all_products()
    if not products:
        await message.answer("Список товаров пуст, удалять нечего.")

    rows = get_all_products()
    if not rows:
        return "Товаров пока нет."

    lines = [f"№{row['id']}: {row['name']} — {row['price']} ₽" for row in rows]
    await state.set_state(AdminStates.delete_id)

    await message.answer("Для удаления введи порядковый номер из списка")
    await message.answer("Список товаров:\n" + "\n".join(lines))


@router.message(AdminStates.delete_id)
async def delete_product_confirm(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    pid = int(message.text)

    products = {row["id"]: row for row in get_all_products()}
    row = products.get(pid)
    if row is None:
        await message.answer("Товара с таким ID нет. Введите другой ID или нажмите \"<-- Назад\".")
        return

    name = {row['name']}
    image_path = row['image_path']

    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
            await message.answer(f"Файл удалён: {image_path}")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")

    delete_product(pid)
    await state.clear()
    await message.answer(
        f"Товар №{pid} «{name}» удалён.",
        reply_markup=admin_menu_kb()
    )


@router.message(F.text == "👈 Назад")
async def admin_back_to_main(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu(is_admin=True)
    )
