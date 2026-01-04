import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from .api_assistant import Assistant
import logging

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

assistant = Assistant()


@dp.message(Command("start"))
async def start_command(message: types.Message):
    """Команда /start"""
    await message.answer(
        "🤖 <b>Привет! Я AI-ассистент</b>\n\n"
        "Просто напиши вопрос - я отвечу!\n\n"
        "<i>Команды:</i>\n"
        "/help - помощь\n"
    )


@dp.message(Command("help"))
async def help_command(message: types.Message):
    """Команда /help"""
    await message.answer(
        "❓ <b>Как использовать:</b>\n\n"
        "1. Напиши любой вопрос\n"
        "2. Я отвечу через 10-20 секунд\n"
        "3. Повторные вопросы быстрее\n\n"
        "<i>Примеры:</i>\n"
        "• Что такое ИИ?\n"
        "• Объясни теорию относительности\n"
        "• Как работает нейросеть?"
    )


@dp.message()
async def handle_question(message: types.Message):
    """Обработка всех сообщений"""
    if not message.text or len(message.text.strip()) == 0:
        return

    if len(message.text) > 2000:
        await message.answer("❌ Слишком длинный вопрос (макс. 2000 символов)")
        return

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        answer = assistant.get_response(message.from_user.id, message.text)

        await message.answer(answer)

    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке запроса, \n {e}")