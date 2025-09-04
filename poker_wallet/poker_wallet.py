import json
import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
adm_ids_str = os.getenv("ADMIN_IDS")
admin_ids = [int(id.strip()) for id in adm_ids_str.split(',') if id.strip()]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_data = {}
pending_admin_actions = {}


def load_data():
    global user_data
    if os.path.exists("user_data.json"):
        with open("user_data.json", "r", encoding='utf-8') as f:
            loaded = json.load(f)
            user_data = {int(k): v for k, v in loaded.items()}
    else:
        user_data = {}


def save_data():
    to_save = {str(k): v for k, v in user_data.items()}
    with open("user_data.json", "w", encoding='utf-8') as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🔄 Сброс")],
                  [KeyboardButton(text="📋 Список пользователей")]],
        resize_keyboard=True,
        persistent=True
    )


@dp.message(lambda m: m.text == "📋 Список пользователей")
async def handle_user_list_button(message: Message):
    if message.from_user.id not in admin_ids:
        await message.answer("⛔ Эта кнопка доступна только администраторам.")
        return
    await admin_menu(message)


@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Неизвестный"

    if user_id not in user_data:
        user_data[user_id] = {"name": first_name, "balance": 0}
        save_data()

    await message.answer(
        f"🎰 Привет, {first_name}!\n"
        "Добро пожаловать в покерный кошелёк 💼\n\n"
        "➕ +100 → добавит выигрыш\n"
        "➖ -50 → запишет проигрыш\n\n"
        "👇 Управляй балансом с помощью кнопок ниже!",
        reply_markup=get_main_keyboard()
    )


@dp.message(lambda m: m.text == "💰 Баланс")
async def balance(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Неизвестный"

    if user_id not in user_data:
        user_data[user_id] = {"name": first_name, "balance": 0}
        save_data()

    balance = user_data[user_id]["balance"]
    emoji = "📈" if balance > 0 else "📉" if balance < 0 else "⚖️"
    await message.answer(f"💰 {first_name}, ваш баланс: {balance:+.1f} {emoji}")


@dp.message(lambda m: m.text == "🔄 Сброс")
async def reset(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Неизвестный"

    user_data[user_id]["balance"] = 0
    save_data()
    await message.answer(f"🔄 {first_name}, баланс сброшен до 0!")


@dp.message(Command("admin_menu"))
async def admin_menu(message: Message):
    if message.from_user.id not in admin_ids:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    if not user_data:
        await message.answer("📭 Нет зарегистрированных пользователей.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=data["name"], callback_data=f"choose_{uid}")]
            for uid, data in user_data.items()
        ]
    )
    await message.answer("👤 Выберите пользователя:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith("choose_"))
async def choose_user(callback: CallbackQuery):
    admin_id = callback.from_user.id
    target_id = int(callback.data.split("_")[1])
    pending_admin_actions[admin_id] = target_id

    name = user_data[target_id]["name"]
    await callback.answer()
    await callback.message.answer(f"💸 Введите сумму для пользователя {name}:")


@dp.message()
async def handle_amount(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Неизвестный"
    text = message.text.strip()

    if user_id in pending_admin_actions:
        try:
            amount = float(text)
            target_id = pending_admin_actions.pop(user_id)

            if target_id not in user_data:
                user_data[target_id] = {"name": "Неизвестный", "balance": 0}

            user_data[target_id]["balance"] += amount
            save_data()

            name = user_data[target_id]["name"]
            new_balance = user_data[target_id]["balance"]
            await message.answer(
                f"✅ {amount:+.1f} добавлено пользователю {name}.\n"
                f"💰 Новый баланс: {new_balance:+.1f}"
            )
        except ValueError:
            await message.answer("❌ Введите корректную сумму, например: 150 или -50")
        return

    if user_id not in user_data:
        user_data[user_id] = {"name": first_name, "balance": 0}

    try:
        amount = float(text)
        user_data[user_id]["balance"] += amount
        save_data()
        new_balance = user_data[user_id]["balance"]

        if amount > 0:
            await message.answer(
                f"✅ Записал выигрыш: +{amount}\n"
                f"💰 {first_name}, текущий баланс: {new_balance:+.1f}"
            )
        else:
            await message.answer(
                f"✅ Записал проигрыш: {amount}\n"
                f"💰 {first_name}, текущий баланс: {new_balance:+.1f}"
            )
    except ValueError:
        await message.answer(
            f"❌ {first_name}, неверный формат!\n"
            "Отправьте число: +100, -50 или 75"
        )


@dp.message(Command("балансы"))
async def show_balances(message: Message):
    if message.from_user.id not in admin_ids:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    if not user_data:
        await message.answer("📭 Нет данных о пользователях.")
        return

    lines = []
    for uid, data in user_data.items():
        name = data["name"]
        balance = data["balance"]
        emoji = "📈" if balance > 0 else "📉" if balance < 0 else "⚖️"
        lines.append(f"{name}: {balance:+.1f} {emoji}")

    await message.answer("📋 Балансы участников:\n\n" + "\n".join(lines))


async def main():
    load_data()
    logging.basicConfig(level=logging.INFO)
    logging.info("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
