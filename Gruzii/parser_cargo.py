import re
from datetime import datetime, timezone

from storage import *
import logging

logger = logging.getLogger(__name__)


def _extract_cargo_snapshot(load: dict) -> dict:
    """Извлекает ключевые поля груза для сравнения изменений."""
    rate_data = load.get('rate', {})
    price_no_nds = rate_data.get('priceNoNds', '') if rate_data else ''
    price_nds = rate_data.get('priceNds', '') if rate_data else ''
    price = rate_data.get('price', '') if rate_data else ''
    if not price_no_nds and not price_nds:
        price_no_nds = price

    load_info = load.get('load', {})

    return {
        'price_no_nds': str(price_no_nds),
        'price_nds': str(price_nds),
        'weight': str(load_info.get('weight', '')),
        'volume': str(load_info.get('volume', '')),
        'note': str(load.get('note', '')),
        'change_date': str(load.get('changeDate', '')),
    }


def _diff_snapshots(old: dict, new: dict) -> list[str]:
    """Сравнивает два снимка груза и возвращает список изменений."""
    changes = []
    if not old:
        return changes

    labels = {
        'price_no_nds': 'Ставка (без НДС)',
        'price_nds': 'Ставка (с НДС)',
        'weight': 'Вес',
        'volume': 'Объём',
        'note': 'Примечание',
    }

    for key, label in labels.items():
        old_val = old.get(key, '')
        new_val = new.get(key, '')
        if old_val != new_val and (old_val or new_val):
            changes.append(f"{label}: {old_val or '—'} → {new_val or '—'}")

    return changes


def parsing_data(data, user_id):
    """
    Парсит данные о грузах и возвращает список с ID и текстом сообщения.

    :param data: Список грузов (loads) или словарь с ключом 'loads'
    :param user_id: ID пользователя
    :return: list of tuples [(load_id, message_text), ...]
    """
    items = []
    if not data or not isinstance(data, list):
        return []

    if isinstance(data, dict):
        loads = data.get('loads', [])
    elif isinstance(data, list):
        loads = data
    else:
        logger.error(f"Неожиданный тип данных в parsing_data: {type(data)}")
        return items

    if not loads:
        return items

    processed = load_processed(user_id)
    if not isinstance(processed, dict):
        processed = {}

    for load in loads:
        try:
            load_num = load.get('loadNumber', '')
            if not load_num:
                continue

            direction = format_direction(load)
            transport = format_transport(load)
            weight_volume = format_weight_volume(load)
            route = format_route(load)
            rate_no_nds, rate_nds = format_rates(load)

            note = get_note(load)
            firm = get_firm(load)
            dateAdd = get_date_add(load)
            load_id = get_load_id(load)
            loading_types = get_loading_types(load)
            per_km_nds, per_km_no_nds = calculate_rate_per_km(route, rate_no_nds, rate_nds)

            km_nds = 'Нет данных ' if per_km_nds == 0 else per_km_nds
            km_no_nds = 'Нет данных ' if per_km_no_nds == 0 else per_km_no_nds

            no_nds = rate_no_nds if rate_no_nds else 'Нет данных'
            nds = rate_nds if rate_nds else 'Нет данных'
            sizes = get_sizes(load) or ''

            snapshot = _extract_cargo_snapshot(load)
            old_snapshot = processed.get(load_num)

            if load_num in processed:
                # Груз уже видели — проверяем изменения
                changes = _diff_snapshots(old_snapshot, snapshot)
                if not changes:
                    continue  # Нет изменений — пропускаем

                changes_text = "\n".join(f"  • {c}" for c in changes)
                msg = (
                    f"🔄 <b>Обновлённый груз #{load_num}</b>\n"
                    f"<b>Что изменилось:</b>\n{changes_text}\n\n"
                    f"<b>Дата:</b> {dateAdd}\n"
                    f"<b>Направление:</b> {direction}\n"
                    f"<b>Транспорт:</b> {transport}\n"
                    f"<b>Тип загрузки:</b> {loading_types if loading_types else ''}\n"
                    f"<b>Вес/Объём/Груз:</b> {weight_volume}\n"
                    f"<b>Габариты (ДxШxВ,м):</b> {sizes}\n"
                    f"<b>Расстояние:</b> {route}\n"
                    f"<b>Ставка:</b> {nds if nds else ''} | {no_nds if no_nds else ''}\n"
                    f"<b>Ставка за км:</b> {km_nds if km_nds else ''} руб. | {km_no_nds if km_no_nds else ''} руб.\n"
                    f"{'<b>Примечание:</b> ' + note if note else ''}\n"
                    f"{'<b>Компания:</b> ' + firm if firm else ''}"
                )
            else:
                # Новый груз
                msg = (
                    f"🆕 <b>Новый груз #{load_num}</b>\n"
                    f"<b>Дата:</b> {dateAdd}\n"
                    f"<b>Направление:</b> {direction}\n"
                    f"<b>Транспорт:</b> {transport}\n"
                    f"<b>Тип загрузки:</b> {loading_types if loading_types else ''}\n"
                    f"<b>Вес/Объём/Груз:</b> {weight_volume}\n"
                    f"<b>Габариты (ДxШxВ,м):</b> {sizes}\n"
                    f"<b>Расстояние:</b> {route}\n"
                    f"<b>Ставка:</b> {nds if nds else ''} | {no_nds if no_nds else ''}\n"
                    f"<b>Ставка за км:</b> {km_nds if km_nds else ''} руб. | {km_no_nds if km_no_nds else ''} руб.\n"
                    f"{'<b>Примечание:</b> ' + note if note else ''}\n"
                    f"{'<b>Компания:</b> ' + firm if firm else ''}"
                )

            items.append((load_id, msg))
            processed[load_num] = snapshot
        except Exception as e:
            logger.error(f"Ошибка при парсинге груза {load.get('loadNumber', '?')}: {e}", exc_info=True)
            continue

    save_processed(user_id, processed)
    return items


def format_direction(load):
    """Форматирует направление перевозки"""
    loading = load.get('loading', {})
    unloading = load.get('unloading', {})

    from_city = loading.get('location', {}).get('city', '')
    to_city = unloading.get('location', {}).get('city', '')

    if not from_city or not to_city:
        route = load.get('route', {})
        from_city = route.get('from', {}).get('name', from_city)
        to_city = route.get('to', {}).get('name', to_city)

    return f"{from_city} => {to_city}"


def format_transport(load):
    """Форматирует информацию о транспорте"""
    truck = load.get('truck', {})
    car_types = truck.get('carTypes', [])

    if not car_types:
        car_types = load.get('carTypes', [])

    if car_types:
        return get_car_types_name(car_types)
    return "Не указан"


def format_weight_volume(load):
    """Форматирует информацию о весе и объёме"""
    data = []
    load_info = load.get('load', {})
    weight = load_info.get('weight', '')
    volume = load_info.get('volume', '')
    cargo_type = load_info.get('cargoType', '')
    palletCount = load_info.get('palletCount', '')
    dogruz = load_info.get('dogruz', '')
    dogruzPossible = load_info.get('dogruzPossible', '')
    onlyToSeparateCar = load_info.get('onlyToSeparateCar', '')
    sborGruz = load_info.get('sborGruz', '')

    if weight:
        data.append(f"{weight} т")
    if volume:
        data.append(f"{volume} м³")
    if cargo_type:
        data.append(cargo_type)
    if palletCount:
        data.append(f"{palletCount} пал")
    if dogruz:
        data.append("догруз")
    if dogruzPossible:
        data.append("догруз возможен")
    if onlyToSeparateCar:
        data.append("только отдельная машина")
    if sborGruz:
        data.append("сборный груз")

    if not data:
        return ''

    return " | ".join(data)


def format_route(load):
    """Форматирует информацию о маршруте"""
    route = load.get('route', {})
    distance = route.get('distance', '')
    travel_time = route.get('travelTime', '')

    if distance or travel_time:
        return f"{distance} км"
    return "Не указан"


def format_rates(load):
    """Форматирует информацию о ставках"""
    rate_data = load.get('rate', {})
    if rate_data:
        # Пробуем получить priceNoNds и priceNds
        price_no_nds = rate_data.get('priceNoNds', '')
        price_nds = rate_data.get('priceNds', '')

        # Если нет, пробуем получить price
        if not price_no_nds and not price_nds:
            price = rate_data.get('price', '')
            if price:
                return f"{price} руб.", ""

        # Формируем строки
        result_no_nds = f"{price_no_nds} руб. (без НДС)" if price_no_nds else ""
        result_nds = f"{price_nds} руб. (с НДС)" if price_nds else ""

        # Если есть только одна ставка
        if result_no_nds and not result_nds:
            return result_no_nds, ""
        if not result_no_nds and result_nds:
            return "", result_nds

        return result_no_nds, result_nds

    price = load.get('price', '')
    if price:
        return f"{price} руб.", ""

    # Возвращаем пустые строки, если нет данных о ставках
    return "", ""


def get_note(load):
    """Получает примечание к грузу"""
    return load.get('note', '')


def get_firm(load):
    """Получает название компании"""
    firm = load.get('firm', {})
    return firm.get('name', '')


def get_date_add(load):
    """Получает дату добавления груза"""
    change_date = load.get('changeDate', '')
    if change_date:
        return formatted_date(change_date)

    add_date = load.get('addDate', '')
    if add_date:
        return formatted_date(add_date)

    return "Нет данных"


def get_load_id(load):
    """Получает ID груза"""
    return load.get('id', '')


def get_loading_types(load):
    """Получает типы загрузки"""
    truck = load.get('truck', {})
    ids = truck.get('loadingTypes', [])

    if not ids:
        ids = load.get('loadingTypes', [])

    if not ids:
        return ''

    loading_type_names = []
    for loading_type_id in ids:
        name = get_car_loading_type_name_by_id(str(loading_type_id))
        if name:
            loading_type_names.append(name)
    return ", ".join(loading_type_names) if loading_type_names else 'Не указан'


def calculate_rate_per_km(route, rate_no_nds, rate_nds):
    if route:
        f_route = extract_number(route)
        if f_route == 0:
            return 0, 0

        extract_rate_no_nds = extract_number(rate_no_nds)
        extract_rate_nds = extract_number(rate_nds)
        no_nds = float(extract_rate_no_nds) if extract_rate_no_nds else 0
        nds = float(extract_rate_nds) if extract_rate_nds else 0

        rate_per_km_nds = nds / f_route if nds else 0
        rate_per_km_no_nds = no_nds / f_route if no_nds else 0

        per_km_nds = round(rate_per_km_nds, 1)
        per_km_no_nds = round(rate_per_km_no_nds, 1)

    else:
        per_km_nds = 0
        per_km_no_nds = 0

    return per_km_nds, per_km_no_nds


def extract_number(value) -> float:
    """Извлекает число из строки или возвращает 0"""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r'[\d]+(?:[.,]\d+)?', str(value))
    if match:
        return float(match.group().replace(',', '.'))
    return 0


def get_sizes(load):
    """Форматирует габариты"""
    try:
        loading = load.get('loading', {})
        loading_cargos = loading.get('loadingCargos', [])
        if not loading_cargos or len(loading_cargos) == 0:
            return None

        first_load = loading_cargos[0]
        sizes = first_load.get('sizes', {})

        length = sizes.get('length', '')
        width = sizes.get('width', '')
        height = sizes.get('height', '')

        if length or width or height:
            len_str = f"{float(length):.2f}" if length else ''
            width_str = f"{float(width):.2f}" if width else ''
            height_str = f"{float(height):.2f}" if height else ''

            return f"{len_str}×{width_str}×{height_str}"
    except (ValueError, TypeError, IndexError) as e:
        logger.warning(f"Ошибка при форматировании габаритов: {e}")

    return None
