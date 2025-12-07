from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from storage import save_user
from config import ADMIN_USER_ID

router = Router()


@router.message(Command("add_user"))
async def cmd_add_user(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет прав для добавления пользователей")
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("⚠️ Использование: /add_user <user_id>")
        return

    try:
        new_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ user_id должен быть числом")
        return

    save = save_user(new_user_id)
    if save:
        await message.answer(f"✅ Пользователь {new_user_id} успешно добавлен")
    else:
        await message.answer(f"✅ Пользователь {new_user_id} уже существует")
