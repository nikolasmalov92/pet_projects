from storage import *


def parsing_data(data, user_id):
    loads = data.get("loads", [])
    processed_list = load_processed(user_id)
    items = []
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
    from_city = load.get('loading', {}).get('location', {}).get('city', '')
    to_city = load.get('unloading', {}).get('location', {}).get('city', '')
    return f"{from_city} -> {to_city}"


def format_transport(load):
    ids_transports = ", ".join(load.get('truck', {}).get('carTypes', []))
    return get_car_types_name(ids_transports)


def format_weight_volume(load):
    l = load.get('load', {})
    return f"{l.get('weight', '')} т / {l.get('volume', '')} м³, {l.get('cargoType', '')}"


def format_route(load):
    r = load.get('route', {})
    return f"{r.get('distance', '')} км, {r.get('travelTime', '')}"


def format_rates(load):
    rate_data = load.get('rate', {})
    if not rate_data:
        return "", ""
    return (
        f"{rate_data.get('priceNoNds', '')} руб. (без НДС)",
        f"{rate_data.get('priceNds', '')} руб. (c НДС)"
    )


def get_note(load):
    return load.get('note', '')


def get_firm(load):
    return load.get('firm', {}).get('name', '')


def get_date_add(load):
    return formatted_date(load.get('addDate', ''))


def get_load_id(load):
    return load.get('id', '')


def get_loading_types(load):
    ids = load.get('truck', {}).get('loadingTypes', [])
    if not ids:
        return ''

    loading_type_names = []
    for loading_type_id in ids:
        name = get_car_loading_type_name_by_id(str(loading_type_id))
        if name:
            loading_type_names.append(name)

    return ", ".join(loading_type_names) if loading_type_names else ' '

