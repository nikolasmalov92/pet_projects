from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def back_to_catalog():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в каталог",
                              callback_data="catalog_0")]
    ])

    return keyboard


def cancel_order():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data="cancel_order")]
    ])

    return keyboard


def pay_order():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Перевод", callback_data="pay_cash")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")]
    ])

    return keyboard


def payment_done():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Я перевел(а)", callback_data="payment_done"),
            InlineKeyboardButton(text="❌ Отменить заказ", callback_data="cancel_order")
        ]
    ])

    return keyboard


def confirm_payment_keyboard(payment_code: str, user_id: int):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ Подтвердить оплату {payment_code}",
                callback_data=f"admin_confirm_{payment_code}_{user_id}"
            )
        ]
    ])

    return keyboard
