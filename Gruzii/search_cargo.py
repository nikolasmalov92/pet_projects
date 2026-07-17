import asyncio
import logging
from typing import Optional

from aiogram.exceptions import TelegramRetryAfter, TelegramNetworkError, TelegramBadRequest

from ati_client import AtiClient
from parser_cargo import parsing_data
from menu import menu_details
from storage import search_paused

logger = logging.getLogger(__name__)

# Rate limiting: минимальная задержка между сообщениями (секунды)
MESSAGE_DELAY = 1.0
# Задержка при flood control (секунды)
FLOOD_CONTROL_DELAY = 5
# Максимальное количество попыток при сетевых ошибках
MAX_RETRIES = 3
# Базовая задержка для exponential backoff (секунды)
RETRY_BASE_DELAY = 10
# Максимальное количество последовательных ошибок перед паузой
MAX_CONSECUTIVE_ERRORS = 5
# Длинная пауза после множественных ошибок (секунды)
LONG_ERROR_PAUSE = 300  # 5 минут
# Максимальное количество одновременных Telegram-запросов (защита от flood control)
TG_SEND_SEMAPHORE = asyncio.Semaphore(3)


async def send_message_safe(message, text: str, reply_markup=None, parse_mode="HTML") -> bool:
    """Отправка сообщения с обработкой flood control и сетевых ошибок."""
    async with TG_SEND_SEMAPHORE:
        for attempt in range(MAX_RETRIES):
            try:
                await message.answer(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                return True
            except TelegramRetryAfter as e:
                wait_time = e.retry_after + FLOOD_CONTROL_DELAY
                logger.warning(f"Flood control: ожидание {wait_time} секунд")
                await asyncio.sleep(wait_time)
            except TelegramNetworkError as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Сетевая ошибка (попытка {attempt + 1}/{MAX_RETRIES}): {e}. Повтор через {delay}с")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Не удалось отправить сообщение после {MAX_RETRIES} попыток: {e}")
                    return False
            except TelegramBadRequest as e:
                # Ошибки валидации (невалидный HTML и т.д.) - не повторяем
                logger.error(f"Ошибка валидации сообщения: {e}")
                return False
            except Exception as e:
                logger.error(f"Неожиданная ошибка при отправке сообщения: {e}", exc_info=True)
                return False
        return False


async def search_cargo_for_user(
    user_id: int,
    from_name: str,
    from_type: int,
    to_name: Optional[str],
    to_type: Optional[int],
    weight_min: Optional[float],
    weight_max: Optional[float],
    message,
    volume_from: Optional[float],
    volume_to: Optional[float],
    active_searches: dict,
    car_load_type_ids: Optional[list],
    car_type_ids: Optional[list],
    from_radius: Optional[int] = None,
    to_radius: Optional[int] = None,
    any_direction: bool = False,
):
    """
    Асинхронно выполняет поиск грузов для пользователя и отправляет результаты.
    """
    search_count = 0
    found_count = 0
    last_sent_loads: set = set()
    consecutive_errors = 0
    ati_client = AtiClient()

    try:
        await _search_loop(
            ati_client, user_id, from_name, from_type, to_name, to_type,
            weight_min, weight_max, message, volume_from, volume_to,
            active_searches, car_load_type_ids, car_type_ids,
            from_radius, to_radius, any_direction,
            search_count, found_count, last_sent_loads, consecutive_errors,
        )
    finally:
        await ati_client.close()


async def _search_loop(
    ati_client, user_id, from_name, from_type, to_name, to_type,
    weight_min, weight_max, message, volume_from, volume_to,
    active_searches, car_load_type_ids, car_type_ids,
    from_radius, to_radius, any_direction,
    search_count, found_count, last_sent_loads, consecutive_errors,
):
    while active_searches.get(user_id, False):
        try:
            # Пауза при открытии меню — ждём пока пользователь не закроет
            while search_paused.get(user_id, False) and active_searches.get(user_id, False):
                await asyncio.sleep(1)

            if not active_searches.get(user_id, False):
                break

            # Получаем ID городов с retry логикой
            from_id, resolved_from_type = await ati_client.get_city_id_async(from_name, from_type)

            if any_direction:
                to_id = None
                resolved_to_type = None
            else:
                to_id, resolved_to_type = await ati_client.get_city_id_async(to_name, to_type) if to_name else (None, None)

            if not from_id or (not any_direction and not to_id):
                logger.warning(
                    f"Не удалось определить гео-точки: {from_name} ({from_type}) → "
                    f"{'любое' if any_direction else f'{to_name} ({to_type})'}"
                )
                break

            search_count += 1

            # Пауза перед API-запросом
            while search_paused.get(user_id, False) and active_searches.get(user_id, False):
                await asyncio.sleep(1)
            if not active_searches.get(user_id, False):
                break

            # Получаем грузы с retry логикой
            cargo_data = await ati_client.get_cargo_async(
                from_id, resolved_from_type,
                to_id, resolved_to_type,
                weight_min, weight_max,
                volume_from, volume_to,
                car_load_type_ids,
                car_type_ids,
                from_radius=from_radius,
                to_radius=to_radius,
                any_direction=any_direction,
            )

            loads = []
            if isinstance(cargo_data, dict):
                temp_loads = cargo_data.get('loads')
                if isinstance(temp_loads, list):
                    loads = temp_loads

            valid_loads = [l for l in loads if isinstance(l, dict)]
            if valid_loads:
                valid_loads.sort(key=lambda x: x.get('price', 0), reverse=True)
                loads = valid_loads
            else:
                loads = []

            # Парсим грузы в текст
            new_msgs = parsing_data(loads, user_id) if loads else []

            # Фильтруем уже отправленные грузы
            unique_msgs = [(lid, msg) for lid, msg in new_msgs if lid not in last_sent_loads]

            if unique_msgs:
                found_count += len(unique_msgs)
                send_failed = False
                for load_id, msg_text in unique_msgs:
                    if not active_searches.get(user_id, False):
                        break
                    # Пауза — ждём перед отправкой каждого сообщения
                    while search_paused.get(user_id, False) and active_searches.get(user_id, False):
                        await asyncio.sleep(1)
                    if not active_searches.get(user_id, False):
                        break
                    last_sent_loads.add(load_id)
                    keyboard = menu_details(load_id)

                    success = await send_message_safe(
                        message,
                        f"\n{msg_text}",
                        reply_markup=keyboard,
                    )

                    if not success:
                        logger.warning(f"Не удалось отправить груз {load_id} пользователю {user_id}")
                        send_failed = True
                        break

                    # Rate limiting между сообщениями
                    await asyncio.sleep(MESSAGE_DELAY)

                if send_failed:
                    consecutive_errors += 1
            else:
                # Сброс счетчика ошибок при успешном поиске
                consecutive_errors = 0

        except asyncio.CancelledError:
            # Задача была отменена - выходим из цикла
            logger.info(f"Поиск для пользователя {user_id} отменен")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Ошибка поиска для пользователя {user_id} (ошибка #{consecutive_errors}): {e}", exc_info=True)

            # Если слишком много ошибок подряд - делаем длинную паузу
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.warning(
                    f"Слишком много ошибок подряд ({consecutive_errors}). "
                    f"Пауза {LONG_ERROR_PAUSE} секунд."
                )
                if active_searches.get(user_id, False):
                    await send_message_safe(
                        message,
                        "⚠️ <b>Множественные ошибки</b>\n\n"
                        f"Повторная попытка через {LONG_ERROR_PAUSE // 60} минут...",
                    )
                for _ in range(LONG_ERROR_PAUSE):
                    if not active_searches.get(user_id, False):
                        break
                    while search_paused.get(user_id, False) and active_searches.get(user_id, False):
                        await asyncio.sleep(1)
                    await asyncio.sleep(1)
                consecutive_errors = 0  # Сброс после длинной паузы
            else:
                if active_searches.get(user_id, False):
                    await send_message_safe(
                        message,
                        "⚠️ <b>Временная ошибка поиска</b>\n\n"
                        "Повторная попытка через 1 минуту...",
                    )
                for _ in range(60):
                    if not active_searches.get(user_id, False):
                        break
                    while search_paused.get(user_id, False) and active_searches.get(user_id, False):
                        await asyncio.sleep(1)
                    await asyncio.sleep(1)
            continue

        # Сброс счетчика ошибок при успешной итерации
        consecutive_errors = 0

        # Пауза между циклами поиска (с проверкой паузы каждую секунду)
        for _ in range(3 * 60):
            if not active_searches.get(user_id, False):
                break
            while search_paused.get(user_id, False) and active_searches.get(user_id, False):
                await asyncio.sleep(1)
            await asyncio.sleep(1)
