from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    setting_from_type = State()
    setting_from_location = State()
    setting_to_type = State()
    setting_to_location = State()
    adding_route = State()
    searching = State()
    setting_from_radius = State()
    setting_from_radius_custom = State()
    setting_to_radius = State()
    setting_to_radius_custom = State()
    setting_route_filters = State()


class MultiRouteStates(StatesGroup):
    managing_routes = State()
    editing_route = State()


class FilterStates(SearchStates):
    setting_filters = State()


class WeightStates(StatesGroup):
    setting_weight = State()
    setting_weight_min = State()
    setting_weight_max = State()


class VolumeStates(StatesGroup):
    setting_volume = State()
    setting_volume_min = State()
    setting_volume_max = State()


class CarLoadTypeStates(StatesGroup):
    setting_car_load_type = State()
    selecting_car_load_type = State()


class CarTypeStates(StatesGroup):
    setting_car_type = State()


class PresetStates(StatesGroup):
    naming_preset = State()
    selecting_preset = State()
    editing_preset = State()


class AdminStates(StatesGroup):
    waiting_for_subscription_id = State()
    waiting_for_take_subscription_id = State()
    waiting_for_delete_user_id = State()
