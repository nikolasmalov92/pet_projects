from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import calendar
from datetime import datetime


def menu_buy_ticket(ticket_url):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подробнее", url=ticket_url)]
    ])
    return keyboard


def create_calendar(year=None, month=None, selected_dates=None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    selected_dates = selected_dates or []

    calendar.setfirstweekday(calendar.MONDAY)
    buttons = [
        [
            InlineKeyboardButton(text="◀",
                                 callback_data=f"nav_{year if month > 1 else year - 1}_{month - 1 if month > 1 else 12}"),
            InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="ignore"),
            InlineKeyboardButton(text="▶",
                                 callback_data=f"nav_{year if month < 12 else year + 1}_{month + 1 if month < 12 else 1}")
        ],
        [InlineKeyboardButton(text=day, callback_data="ignore") for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]]
    ]

    for week in calendar.monthcalendar(year, month):
        buttons.append([
            InlineKeyboardButton(
                text=f"✅{day}" if day and f"{day:02d}.{month:02d}.{year}" in selected_dates else str(
                    day) if day else " ",
                callback_data=f"date_{day:02d}.{month:02d}.{year}" if day else "ignore"
            ) for day in week
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
