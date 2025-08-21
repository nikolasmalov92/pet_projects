import asyncio
import logging
from contextlib import suppress
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.types import Message
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

BOT_TOKEN = "8072620097:AAHz-6w2Q7xMaQqZPk55bFLb1M0_GtFcQdc"
OPENAI_API_KEY = "ak_lkI_kUlk-IT8nmyDg5s9yy7bClgHSbWEChXdePpoW7Y"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(
    base_url="https://api.polza.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

user_contexts = {}


async def typing_indicator_loop(chat_id: int, stop: asyncio.Event) -> None:
    """Поддерживает индикатор 'печатает' у пользователя.
    Telegram скрывает индикатор через ~5с, поэтому слать его нужно периодически.
    """
    try:
        while not stop.is_set():
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=4.0)

    except Exception as e:
        logging.warning(f"typing_indicator_loop: {e}")


async def send_long_text(dst_message: Message, text: str) -> None:
    """Отправка длинных сообщений с разбиением по лимиту Telegram (4096)."""
    parse_mode = ParseMode.MARKDOWN

    if not text:
        return

    limit = 4000
    if len(text) <= limit:
        await dst_message.answer(text, parse_mode=parse_mode)
        return

    for i in range(0, len(text), limit):
        chunk = text[i: i + limit]
        await dst_message.answer(chunk, parse_mode=parse_mode)


@dp.message(Command("start"))
async def start_handler(message: Message):
    logging.info(f"user_name: {message.from_user.username}")
    await message.answer(
        "👋 Привет! Я AI-бот на базе T-pro-it-2.0.\n\n"
        "Просто отправь мне любой вопрос — отвечу!\n\n"
        "Команды:\n"
        "/help — помощь",
        parse_mode=ParseMode.MARKDOWN
    )


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "🤖 Как пользоваться ботом:\n\n"
        "1) Напиши любой вопрос\n"
        "2) Я обрабатываю его моделью T-pro-it-2.0\n"
        "3) Верну подробный ответ\n\n"
        "Примеры:\n"
        "• Объясни, что такое машинное обучение\n"
        "• Как написать функцию на Python?\n"
        "• Расскажи анекдот"
    )


@dp.message(F.text)
async def ai_response_handler(message: Message):
    """Основной обработчик: показывает статусы 'бот думает…'."""
    status_msg = None
    typing_stop = asyncio.Event()
    typing_task = None
    user_id = message.from_user.id
    if user_id not in user_contexts:
        user_contexts[user_id] = []
    try:
        user_contexts[user_id].append({"role": "user", "content": message.text})
        status_msg = await message.answer("🤔 Обрабатываю твой запрос...")
        typing_task = asyncio.create_task(typing_indicator_loop(message.chat.id, typing_stop))
        completion = client.chat.completions.create(
            model="t-tech/T-pro-it-2.0-FP8",
            messages=user_contexts[user_id],
            temperature=0.7,
        )
        ai_response = completion.choices[0].message.content or ""
        user_contexts[user_id].append({"role": "assistant", "content": ai_response})
        typing_stop.set()
        if typing_task:
            with suppress(Exception):
                await typing_task

        await send_long_text(message, ai_response)

        if status_msg:
            with suppress(Exception):
                await status_msg.delete()

    except Exception as e:
        logging.exception("Ошибка при обработке запроса: %s", e)

        typing_stop.set()
        if typing_task:
            with suppress(Exception):
                await typing_task

        if status_msg:
            with suppress(Exception):
                await status_msg.edit_text(
                    "😔 Извините, произошла ошибка при обработке запроса.\nПопробуйте ещё раз позже."
                )
        else:
            await message.answer(
                "😔 Извините, произошла ошибка при обработке запроса.\nПопробуйте ещё раз позже."
            )


@dp.message()
async def unknown_handler(message: Message):
    await message.answer("🤔 Я понимаю только текстовые сообщения.")


async def main():
    logging.info("Запуск бота…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
