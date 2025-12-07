import json
import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.filters import Command

from ParfBar.CallbackData.states import OrderStates
from ParfBar.handlers.catalog_handler import build_catalog_simple
from ParfBar.menu.catalog_menu import cancel_order, pay_order
from ParfBar.menu.main_menu import main_menu
from ParfBar.database.db import get_all_products
from dotenv import load_dotenv
import os

load_dotenv()
ADMIN_ID = json.loads(os.getenv('ADMIN_ID', '[]'))

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    is_admin = (message.from_user.id in ADMIN_ID)
    await message.answer(
        "Добро пожаловать в Parf Bar — ваш персональный гид по миру ароматов.\n\n"
        "Я помогу найти аромат, который подчеркнёт ваш характер и настроение.\n"
        "Найдите нужный аромат в каталоге и нажмите '🛒 Купить' для оформления заказа.\n\n"
        "Доступно прямо сейчас:\n"
        "— Каталог: эксклюзивные ароматы\n"
        "— Консультация: помощь в выборе\n"
        "— Доставка: по всей России\n"
        "— Оплата: перевод\n\n"
        "Выберите действие:",
        reply_markup=main_menu(is_admin),
        parse_mode='HTML'
    )


@router.message(F.text == "🛍 Каталог")
async def show_catalog(message: Message):
    products = get_all_products()
    if not products:
        await message.answer("📭 Каталог временно пуст. Загляните позже!")
        return

    await message.answer("⏳ Загружаю каталог...")
    media, keyboard = build_catalog_simple(products, page=0)

    if media and keyboard:
        await message.answer_photo(
            photo=media.media,
            caption=media.caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    else:
        await message.answer("❌ Не удалось загрузить каталог. Пожалуйста, попробуйте позже.")


@router.message(OrderStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()

    if len(name) < 2:
        await message.answer("❌ Пожалуйста, введите корректное ФИО (минимум 2 символа)")
        return

    await state.update_data(customer_name=name)

    text = """📱 Введите ваш <b>номер телефона</b>:
    Формат: +7 (999) 123-45-67"""

    keyboard = cancel_order()

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_phone)


@router.message(OrderStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    phone_digits = re.sub(r'\D', '', phone)
    if len(phone_digits) < 10:
        await message.answer("❌ Пожалуйста, введите корректный номер телефона")
        return

    await state.update_data(customer_phone=phone)

    text = """📦 Введите <b>адрес доставки</b>:

    Укажите: город, улицу, дом, квартиру
    Например: Москва, ул. Ленина, д. 10, кв. 25"""

    keyboard = cancel_order()

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_address)


@router.message(OrderStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()

    if len(address) < 10:
        await message.answer("❌ Пожалуйста, введите полный адрес доставки")
        return

    await state.update_data(customer_address=address)

    data = await state.get_data()

    order_summary = f"""✅ <b>Подтверждение заказа</b>

    📦 Товар: <b>{data['product_name']}</b>
    💰 Цена: <b>{data['price']}</b>
    
    👤 ФИО: {data['customer_name']}
    📱 Телефон: {data['customer_phone']}
    📍 Адрес: {data['customer_address']}
    
    Выберите способ оплаты:"""

    keyboard = pay_order()

    await message.answer(order_summary, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_payment)


@router.message(OrderStates.waiting_for_payment_confirmation)
async def process_payment_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()

    if message.from_user.id in ADMIN_ID:
        payment_code = data.get('payment_code', '')
        order_code = data.get('order_code', '')

        confirm_phrases = [
            f"оплата по коду {payment_code} подтверждена",
            f"код {payment_code} подтвержден",
            f"перевод по коду {payment_code} получен",
            f"✅ оплата подтверждена",
            "оплата подтверждена"
        ]

        message_lower = message.text.lower()

        for phrase in confirm_phrases:
            if phrase in message_lower:
                user_text = f"""✅ <b>Оплата подтверждена!</b>

                            🆔 Код заказа: <code>{order_code}</code>
                            🔑 Код оплаты: <code>{payment_code}</code>
                            
                            📦 Товар: <b>{data['product_name']}</b>
                            💰 Сумма: <b>{data['price']}</b>
                            
                            ✅ Ваш заказ передан в доставку.
                            📦 Ожидайте посылку по адресу: {data['customer_address']}
                            
                            📱 По вопросам доставки: @slmlkmmmm
                            🔄 Отслеживание: доступно по запросу"""

                try:
                    await message.bot.send_message(
                        chat_id=data['user_id'],
                        text=user_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    await message.answer(f"Ошибка отправки пользователю: {e}")

                admin_success = f"""✅ <b>Оплата успешно подтверждена</b>

                                🆔 Код заказа: <code>{order_code}</code>
                                🔑 Код оплаты: <code>{payment_code}</code>
                                
                                👤 Покупатель: {data['customer_name']}
                                📦 Товар: {data['product_name']}
                                💰 Сумма: {data['price']}
                                
                                ✅ Пользователь уведомлен о подтверждении оплаты
                                📦 Заказ передан в доставку"""

                await message.answer(admin_success, parse_mode="HTML")
                await state.clear()
                return

    if message.from_user.id not in ADMIN_ID:
        text = """⏳ <b>Ожидайте подтверждения оплаты</b>

                Мы проверим поступление средств по указанному коду и подтвердим оплату.
                Обычно это занимает до 15 минут.
                
                Как только администратор подтвердит оплату, вы получите уведомление."""

        await message.answer(text, parse_mode="HTML")