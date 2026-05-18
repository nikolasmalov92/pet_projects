import asyncio
import logging
import traceback
from Gruzii.ati_client import AtiClient
from Gruzii.parser_cargo import parsing_data
from Gruzii.menu import menu_details, get_search_controls

logging.basicConfig(level=logging.INFO)


async def search_cargo_for_user(user_id, from_name, from_type, to_name, to_type,
                                weight_min, weight_max, message,
                                volume_from, volume_to,
                                active_searches, car_load_type_ids, car_type_ids,
                                from_radius=None, to_radius=None,
                                any_direction=False):
    """
    Асинхронно выполняет поиск грузов для пользователя и отправляет результаты.

    :param car_load_type_ids: Список ID типов загрузки
    :param active_searches: Словарь для управления состоянием поиска
    :param volume_to: Максимальный объём (опционально)
    :param volume_from: Минимальный объём (опционально)
    :param user_id: ID пользователя
    :param from_name: Название пункта отправления
    :param from_type: Тип географической точки отправления
    :param to_name: Название пункта назначения (None при any_direction=True)
    :param to_type: Тип географической точки назначения (None при any_direction=True)
    :param weight_min: Минимальный вес груза
    :param weight_max: Максимальный вес груза
    :param message: Сообщение для отправки результатов
    :param from_radius: Радиус поиска от пункта отправления, км (опционально)
    :param to_radius: Радиус поиска у пункта назначения, км (опционально)
    :param any_direction: True — искать без ограничения пункта назначения
    """
    search_count = 0
    found_count = 0
    last_sent_loads = set()

    while active_searches.get(user_id, False):
        try:
            ati_client = AtiClient()
            from_id = ati_client.get_city_id(from_name, from_type)

            if any_direction:
                to_id = None
            else:
                to_id = ati_client.get_city_id(to_name, to_type) if to_name else None

            if from_id and (any_direction or to_id):
                search_count += 1
                cargo_data = ati_client.get_cargo(
                    from_id, from_type,
                    to_id, to_type,
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
                    for load_id, msg_text in unique_msgs:
                        if not active_searches.get(user_id, False):
                            break
                        last_sent_loads.add(load_id)
                        keyboard = menu_details(load_id)
                        await message.answer(
                            f"\n{msg_text}",
                            reply_markup=keyboard,
                            parse_mode="HTML",
                        )
                        await asyncio.sleep(0.5)
            else:
                logging.warning(
                    f"Не удалось определить гео-точки: {from_name} ({from_type}) → "
                    f"{'любое' if any_direction else f'{to_name} ({to_type})'}"
                )
                await message.answer(
                    f"❌ Не удалось определить маршрут: <b>{from_name} → "
                    f"{'любое направление' if any_direction else to_name}</b>\n"
                    f"Проверьте правильность названий.",
                    parse_mode="HTML"
                )
                break
        except Exception as e:
            logging.error(f"Ошибка поиска: {e}")
            logging.error(traceback.format_exc())
            await message.answer(
                "⚠️ <b>Временная ошибка поиска</b>\n\n"
                "Повторная попытка через 1 минуту...",
                parse_mode="HTML",
                reply_markup=get_search_controls()
            )
            await asyncio.sleep(60)
            continue
        await asyncio.sleep(3 * 60)
