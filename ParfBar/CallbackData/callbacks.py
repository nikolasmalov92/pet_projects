import json
import os

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from handlers.catalog_handler import build_catalog_simple, get_price_catalog, generate_order_code, \
    generate_payment_code
from menu.catalog_menu import back_to_catalog, cancel_order, payment_done, confirm_payment_keyboard
from database.db import get_all_products
from CallbackData.states import OrderStates

from dotenv import load_dotenv

from menu.main_menu import back_to_main_menu

load_dotenv()
ADMIN_ID = json.loads(os.getenv('ADMIN_ID', '[]'))

router = Router()


@router.callback_query(F.data.startswith("catalog_"))
async def catalog_paginate(callback: CallbackQuery):
    try:
        data_parts = callback.data.split("_")
        if len(data_parts) == 2 and data_parts[1].isdigit():
            page = int(data_parts[1])
        else:
            page = 0

        products = get_all_products()

        if not products:
            await callback.answer("Каталог пуст", show_alert=True)
            return

        media, keyboard = build_catalog_simple(products, page=page)

        if not media or not keyboard:
            await callback.answer("Товар не найден", show_alert=True)
            return

        await callback.message.edit_media(
            media=media,
            reply_markup=keyboard
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"Произошла ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "consult")
async def consultation_callback_handler(callback: CallbackQuery):
    text = """<b>Консультация по выбору аромата</b>

    Наш эксперт поможет вам:
    • Подобрать аромат по типу кожи и предпочтениям
    • Выбрать подарок для близких
    • Найти аналог любимого парфюма
    • Ответить на вопросы о составе и носке

    📞 <b>Свяжитесь с нашим консультантом:</b>
    @slmlkmmmm; 
    @Bulat_Timerbaev"""

    keyboard = back_to_catalog()

    await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("add_"))
async def add_to_cart_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        prod_id = int(callback.data.split("_")[1])
        products = get_all_products()

        product = None
        for p in products:
            if p[0] == prod_id:
                product = p
                break

        if not product:
            await callback.answer("Товар не найден", show_alert=True)
            return

        prod_name = product[1]
        price_value = get_price_catalog(product[3])

        await state.update_data(
            product_id=prod_id,
            product_name=prod_name,
            price=price_value,
            user_id=callback.from_user.id,
            username=callback.from_user.username or "Не указан"
        )

        text = f"""🛒 <b>Оформление заказа</b>

        Товар: <b>{prod_name}</b>
        💰 Цена: <b>{price_value}</b>

        Введите ваше <b>ФИО</b> для доставки:"""

        keyboard = cancel_order()

        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        await state.set_state(OrderStates.waiting_for_name)
        await callback.answer()

    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "cancel_order", OrderStates.waiting_for_payment_confirmation)
async def cancel_order_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    admin_text = f"""❌ <b>Заказ отменен пользователем</b>

                    🆔 Код заказа: <code>{data.get('order_code', 'не указан')}</code>
                    🔑 Код оплаты: <code>{data.get('payment_code', 'не указан')}</code>
                    
                    👤 Покупатель: {data.get('customer_name', 'не указан')}
                    🆔 ID: {data.get('user_id', 'не указан')}
                    📦 Товар: {data.get('product_name', 'не указан')}"""

    for admin_id in ADMIN_ID:
        try:
            await callback.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="HTML"
            )
        except Exception as e:
            pass

    await state.clear()
    await callback.message.answer("❌ Заказ отменён. Код оплаты аннулирован.")
    await callback.answer()


@router.callback_query(F.data == "pay_cash", OrderStates.waiting_for_payment)
async def process_cash_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    order_code = generate_order_code(data['user_id'])
    payment_code = generate_payment_code()
    await state.update_data(
        order_code=order_code,
        payment_code=payment_code
    )

    data = await state.get_data()
    user_text = f"""✅ <b>Заказ успешно оформлен!</b>

    📦 Товар: <b>{data['product_name']}</b>
    💰 Сумма: <b>{data['price']}</b>
    🆔 Код заказа: <code>{order_code}</code>

    💵 <b>Инструкция по оплате:</b>

        1️⃣ <b>Реквизиты для перевода:</b>
            📱 Номер: <b>+79872998843</b>
            💳 СБП: Тинькофф/Сбербанк
    
        2️⃣ <b>ВАЖНО:</b> При переводе укажите в комментарии:
            🔑 Код для перевода: <code>{payment_code}</code>
    
        3️⃣ После перевода нажмите кнопку "✅ Я перевел(а)"
    
        4️⃣ Мы проверим перевод по коду <code>{payment_code}</code> и подтвердим оплату
    
        5️⃣ После подтверждения заказ будет передан в доставку
    
        ⚠️ <b>Без кода {payment_code} мы не сможем идентифицировать ваш перевод!</b>"""

    keyboard = payment_done()
    await callback.message.answer(user_text, parse_mode="HTML", reply_markup=keyboard)

    admin_text = f"""🔔 <b>Новый заказ! (Ожидает оплаты)</b>

    🆔 Код заказа: <code>{order_code}</code>
    🔑 Код для перевода: <code>{payment_code}</code>

    📦 Товар: {data['product_name']}
    💰 Цена: {data['price']}

    👤 Покупатель: {data['customer_name']}
    📱 Телефон: {data['customer_phone']}
    📍 Адрес: {data['customer_address']}

    💵 Способ оплаты: Перевод
    ⏳ Статус: Ожидает оплаты

    <b>Инструкция для администратора:</b>
    1. Дождитесь уведомления "✅ Я перевел(а)" от пользователя
    2. Проверьте перевод по коду <code>{payment_code}</code>
    3. Если перевод поступил, отправьте пользователю:
    ✅ Оплата по коду {payment_code} подтверждена
    4. Заказ автоматически перейдет в статус "В доставке" """

    for admin_id in ADMIN_ID:
        try:
            await callback.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="HTML"
            )
        except Exception as e:
            await callback.message.answer(f"Ошибка отправки админу {admin_id}: {e}")

    await state.set_state(OrderStates.waiting_for_payment_confirmation)
    await callback.answer("Заказ оформлен!")


@router.callback_query(F.data == "cancel_order")
async def cancel_order_state(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    keyboard = back_to_main_menu()

    await callback.message.answer("❌ Заказ отменён", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "payment_done")
async def payment_done_handler(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал 'Я перевел(а)'"""

    # Получаем данные из состояния
    data = await state.get_data()
    payment_code = data.get('payment_code', 'неизвестный код')

    # Проверяем, что пользователь находится в правильном состоянии
    current_state = await state.get_state()
    if current_state != OrderStates.waiting_for_payment_confirmation.state:
        await callback.answer("❌ Сначала оформите заказ", show_alert=True)
        return

    text = f"""✅ <b>Спасибо за уведомление!</b>

Мы получили информацию о вашем переводе.

Как только перевод будет подтвержден, вы получите уведомление о подтверждении оплаты.

После этого заказ будет передан в доставку."""

    await callback.message.answer(text, parse_mode="HTML")

    user_id = callback.from_user.id
    username = callback.from_user.username or "без username"

    admin_notify = f"""🔄 <b>Пользователь сообщил о переводе</b>

                        🔑 Код для проверки: <code>{payment_code}</code>
                        👤 Пользователь: @{username}
                        🆔 ID: {user_id}
                        
                        📦 Товар: {data.get('product_name', 'не указан')}
                        💰 Сумма: {data.get('price', 'не указана')}

                        <b>После проверки перевода нажмите кнопку подтверждения:</b>"""

    for admin_id in ADMIN_ID:
        try:
            await callback.bot.send_message(
                chat_id=admin_id,
                text=admin_notify,
                parse_mode="HTML",
                reply_markup=confirm_payment_keyboard(payment_code, user_id)
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

    await callback.answer("✅ Уведомление отправлено администраторам")


@router.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm_payment(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_ID:
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        payment_code = parts[2]  # Код оплаты
        user_id = int(parts[3])  # ID пользователя

        user_confirmation = f"""✅ <b>Оплата подтверждена!</b>

                            🔑 Код оплаты: <code>{payment_code}</code>
                            
                            ✅ Ваш заказ передан в доставку.
                            📦 Ожидайте посылку по указанному адресу.
                            🔄 Отслеживание: доступно по запросу
                            
                            📱 По вопросам доставки: @slmlkmmmm"""

        try:
            await callback.bot.send_message(
                chat_id=user_id,
                text=user_confirmation,
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )

            new_admin_text = f"""✅ <b>Оплата подтверждена!</b>            
            ✅ Пользователь уведомлен о подтверждении оплаты.
            📦 Заказ передан в доставку."""

            await callback.message.edit_text(
                new_admin_text,
                parse_mode="HTML",
                reply_markup=None
            )
            await callback.answer("✅ Оплата подтверждена, пользователь уведомлен!")

        except Exception as e:
            await callback.answer(f"Ошибка отправки пользователю: {e}", show_alert=True)

    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
