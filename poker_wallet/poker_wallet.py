import json

from dotenv import load_dotenv
import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_balances = {}


def load_data():
    global user_data
    if os.path.exists("user_data.json"):
        with open("user_data.json", "r", encoding='utf-8') as f:
            loaded_data = json.load(f)
            user_data = {int(k): v for k, v in loaded_data.items()}
    else:
        user_data = {}


def save_data():
    to_save = {str(k): v for k, v in user_data.items()}
    with open("user_data.json", "w", encoding='utf-8') as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🔄 Сброс")]],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard


@dp.message(Command('start'))
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Неизвестный"
    first_name = message.from_user.first_name or username
    if user_id not in user_balances:
        user_balances[user_id] = 0

    await message.answer(
        f"🎰 Привет, {first_name}!"
        " Добро пожаловать в покерный кошелек 💼\n\n"
        "Здесь можно быстро отмечать выигрыши и проигрыши:  \n"
        "➕ +100 → добавит выигрыш\n"
        "➖ -50 → запишет проигрыш \n\n"
        "👇 Управляй балансом с помощью кнопок ниже!",
        reply_markup=get_main_keyboard()
    )


@dp.message(lambda message: message.text == "💰 Баланс")
async def balance(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Неизвестный"
    first_name = message.from_user.first_name or username
    if user_id not in user_balances:
        user_balances[user_id] = 0

    current_balance = user_balances[user_id]
    if current_balance > 0:
        await message.answer(f"💰 {first_name}, ваш баланс: +{current_balance} 📈")
    elif current_balance < 0:
        await message.answer(f"💰 {first_name}, ваш баланс: {current_balance} 📉")
    else:
        await message.answer(f"💰 {first_name}, ваш баланс: {current_balance} ⚖️")


@dp.message(lambda message: message.text == "🔄 Сброс")
async def reset(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Неизвестный"
    first_name = message.from_user.first_name or username
    user_balances[user_id] = 0
    await message.answer(f"🔄 {first_name}, баланс сброшен до 0!")


@dp.message()
async def amount(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Неизвестный"
    first_name = message.from_user.first_name or username
    text = message.text.strip()

    if user_id not in user_balances:
        user_balances[user_id] = 0

    amount = float(text)
    user_balances[user_id] += amount
    new_balance = user_balances[user_id]
    try:
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
            "❌  {username}, неверный формат!\n"
            "Отправьте число: +100, -50 или 75"
        )


async def main():
    load_data()
    logging.info(f"Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
