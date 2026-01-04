import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from aiogram.types import Update
import uvicorn
from app.bot import dp, bot

load_dotenv()

SECRET_TOKEN = os.getenv("SECRET_TOKEN")
DOMAIN_NAME = os.getenv("DOMAIN_NAME")
WEBHOOK_URL = f"https://{DOMAIN_NAME}/webhook"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом"""
    logger.info("🚀 Запуск бота...")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=SECRET_TOKEN,
            drop_pending_updates=True
        )
        logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

    yield

    logger.info("🛑 Остановка бота...")
    await bot.session.close()


app = FastAPI(title="Telegram Bot", lifespan=lifespan)


@app.post("/webhook")
async def webhook_handler(request: Request):
    """Обработчик вебхука"""
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")

    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        update_data = await request.json()
        update = Update(**update_data)

        await dp.feed_update(bot=bot, update=update)

        return JSONResponse(content={"ok": True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(content={"ok": False, "error": str(e)}, status_code=500)


if __name__ == "__main__":
    port = int(os.getenv("PORT"))
    uvicorn.run(app, host="0.0.0.0", port=port)
