import asyncio
import logging
import os
import re
import pandas as pd
from aiogram import Bot, Dispatcher
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from message import *

executor = ThreadPoolExecutor(max_workers=5)
user_bots: dict[int, MessageBot] = {}

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@dp.message(Command("start"))
async def start(message: Message):
    first_name = message.from_user.first_name or "Неизвестный"

    await message.answer(f"Привет, {first_name}!\n"
                         "Введите номер телефона в формате +7XXXXXXXXXX\n\n")


def authenticate_user(user_id: int, phone: str) -> dict:
    bot = user_bots.get(user_id)
    if bot is None or bot.driver is None:
        bot = MessageBot(user_id)
        user_bots[user_id] = bot
    try:
        result = bot.authenticate(phone)
        return result
    except Exception as e:
        logging.error(f"Ошибка авторизации для {user_id}: {e}")
        return {
            "authenticated": False,
            "code": None,
            "error": str(e),
            "message": "Ошибка подключения"
        }


def send_messages_sync(user_id: int) -> str:
    bot = user_bots.get(user_id)
    if bot is None:
        return "Ошибка: бот не найден"
    try:
        if not bot.is_authenticated:
            return "Ошибка: не авторизован"

        success, message = bot.send_messages()
        return message
    except Exception as e:
        logging.error(f"Ошибка отправки для {user_id}: {e}")
        return f"Ошибка: {str(e)}"


@dp.message(F.text)
async def process_phone_number(message: Message):
    user_id = message.from_user.id
    phone_text = message.text.strip()
    phone_pattern = r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'

    if re.match(phone_pattern, phone_text):
        cleaned_phone = re.sub(r'[^\d]', '', phone_text)
        if cleaned_phone.startswith('8'):
            cleaned_phone = '7' + cleaned_phone[1:]
        elif len(cleaned_phone) == 10:
            cleaned_phone = '7' + cleaned_phone
        elif len(cleaned_phone) == 11 and cleaned_phone.startswith('7'):
            cleaned_phone = cleaned_phone

        formatted_phone = f"+{cleaned_phone}"
        await message.answer(f"✅ Номер принят: {formatted_phone}\n"
                             "Обрабатываю...")

        try:
            auth_result = await asyncio.get_event_loop().run_in_executor(
                executor,
                authenticate_user,
                user_id,
                formatted_phone
            )
            if auth_result["authenticated"]:
                if auth_result["code"]:
                    await message.answer(f"🔐 Введите этот код в WhatsApp:")
                    clean_code = auth_result['code'].replace(',', '').replace(' ', '')
                    await message.answer(clean_code)

                else:
                    await message.answer("✅ Вы уже авторизованы!")
                    await message.answer("📂 Пришлите файл с базой номеров (Excel или CSV) в чат.")
            else:
                await message.answer(f"❌ Ошибка авторизации: {auth_result.get('error', 'Неизвестная ошибка')}")

        except Exception as e:
            logging.error(f"Ошибка обработки: {e}")
            await message.answer(f"❌ Произошла ошибка: {str(e)}")

    else:
        await message.answer("❌ Неверный формат номера.\n"
                             "Пожалуйста, введите номер в формате:\n"
                             "+7XXXXXXXXXX или 8XXXXXXXXXX")


@dp.message(F.document)
async def handle_document(message: Message):
    user_id = message.from_user.id

    document = message.document
    file_name = document.file_name

    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
    await message.bot.download(document, destination=file_path)
    await message.answer(f"✅ Файл получен и сохранён!\n")

    try:
        numbers = parse_numbers(file_path)
        if user_id in user_bots:
            user_bots[user_id].data = numbers
        else:
            bot_instance = MessageBot(user_id)
            bot_instance.data = numbers
            user_bots[user_id] = bot_instance

        await message.answer(f"📊 Загружено {len(numbers)} номеров для рассылки.")
        send_result = await asyncio.get_event_loop().run_in_executor(executor, send_messages_sync, user_id)
        await message.answer(f"✅ {send_result}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке файла: {e}")


def parse_numbers(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".xls", ".xlsx"]:
        df = pd.read_excel(file_path)
    elif ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise ValueError("Неподдерживаемый формат файла")

    for col in df.columns:
        if "phone" in col.lower() or "номер" in col.lower():
            return [(str(x), str(x)) for x in df[col].dropna().tolist()]

    return [(str(x), str(x)) for x in df.iloc[:, 0].dropna().tolist()]


async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
