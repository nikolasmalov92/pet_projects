import asyncio
import logging
from ati_client import AtiClient
from parser_cargo import parsing_data
from menu import menu_details, get_search_controls


async def search_cargo_for_user(user_id, from_name, from_type, to_name, to_type,
                                weight_from, weight_to, message,
                                volume_from, volume_to,
                                active_searches, car_load_type_ids):
    """
    Асинхронно выполняет поиск грузов для пользователя и отправляет результаты.
    :param car_load_type_ids:
    :param active_searches: Словарь для управления состоянием поиска
    :param volume_to: Максимальный объём (опционально)
    :param volume_from: Минимальный объём (опционально)
    :param user_id: ID пользователя
    :param from_name: Название пункта отправления
    :param from_type: Тип географической точки отправления
    :param to_name: Название пункта назначения
    :param to_type: Тип географической точки назначения
    :param weight_from: Минимальный вес груза
    :param weight_to: Максимальный вес груза
    :param message: Сообщение для отправки результатов
    """
    search_count = 0
    found_count = 0

    while active_searches.get(user_id, False):
        try:
            ati_client = AtiClient()
            from_id = ati_client.get_city_id(from_name, from_type)
            to_id = ati_client.get_city_id(to_name, to_type)
            if from_id and to_id:
                search_count += 1
                cargo_data = ati_client.get_cargo(from_id, from_type, to_id, to_type,
                                                  weight_from, weight_to,
                                                  volume_from, volume_to, car_load_type_ids)
                new_msgs = parsing_data(cargo_data, user_id)
                if new_msgs:
                    found_count += len(new_msgs)
                    for load_id, msg_text in new_msgs:
                        if not active_searches.get(user_id, False):
                            break
                        keyboard = menu_details(load_id)
                        await message.answer(
                            f"\n{msg_text}",
                            reply_markup=keyboard,
                            parse_mode="HTML",
                        )
                        await asyncio.sleep(1)
                else:
                    if search_count % 3 == 0:
                        await message.answer(
                            f"🔍 Поиск продолжается...\nНайдено: {len(new_msgs)} грузов",
                            reply_markup=get_search_controls()
                        )
            else:
                logging.warning(f"Не удалось определить гео-точки: {from_name} ({from_type}) → {to_name} ({to_type})")
                await message.answer(
                    f"❌ Не удалось определить маршрут: <b>{from_name} → {to_name}</b>\n"
                    f"Проверьте правильность названий.",
                    parse_mode="HTML"
                )
                break
        except Exception as e:
            logging.error(f"Ошибка поиска: {e}")
            await message.answer(
                "⚠️ <b>Временная ошибка поиска</b>\n\n"
                "Повторная попытка через 1 минуту...",
                parse_mode="HTML",
                reply_markup=get_search_controls()
            )
            await asyncio.sleep(60)
            continue
        await asyncio.sleep(3 * 60)
    logging.info(f"Поиск для пользователя {user_id} завершен")