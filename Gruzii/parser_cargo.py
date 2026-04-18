from storage import *
import logging

logging.basicConfig(level=logging.INFO)


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
        logging.error(f"Неожиданный тип данных в parsing_data: {type(data)}")
        return items

    if not loads:
        return items

    processed_list = load_processed(user_id)
    if processed_list is None:
        processed_list = []
    elif not isinstance(processed_list, list):
        processed_list = []

    for load in loads:
        load_num = load.get('loadNumber', '')
        if not load_num or load_num in processed_list:
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

        msg = (
            f"🆕 Новый груз #{load_num}\n"
            f"Дата: {dateAdd}\n"
            f"Направление: {direction}\n"
            f"Транспорт: {transport}\n"
            f"Тип загрузки: {loading_types}\n"
            f"Вес/Объём/Груз: {weight_volume}\n"
            f"Маршрут: {route}\n"
            f"Ставка: {rate_no_nds}; {rate_nds}\n"
            f"{'Примечание: ' + note if note else ''}\n"
            f"Компания: {firm}"
        )
        items.append((load_id, msg))
        processed_list.append(load_num)

    save_processed(user_id, processed_list)
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

    return f"{from_city} -> {to_city}"


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
    load_info = load.get('load', {})
    weight = load_info.get('weight', '')
    volume = load_info.get('volume', '')
    cargo_type = load_info.get('cargoType', '')

    if not weight:
        weight = load.get('weight', '')
    if not volume:
        volume = load.get('volume', '')

    return f"{weight} т / {volume} м³, {cargo_type}"


def format_route(load):
    """Форматирует информацию о маршруте"""
    route = load.get('route', {})
    distance = route.get('distance', '')
    travel_time = route.get('travelTime', '')

    if distance or travel_time:
        return f"{distance} км, {travel_time}"
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


def get_note(load):
    """Получает примечание к грузу"""
    return load.get('note', '')


def get_firm(load):
    """Получает название компании"""
    firm = load.get('firm', {})
    return firm.get('name', '')


def get_date_add(load):
    """Получает дату добавления груза"""
    add_date = load.get('addDate', '')
    return formatted_date(add_date)


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
