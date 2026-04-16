from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    setting_from_type = State()
    setting_from_location = State()
    setting_to_type = State()
    setting_to_location = State()
    adding_route = State()
    confirming_search = State()
    searching = State()


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


class AdminStates(StatesGroup):
    waiting_for_subscription_id = State()
    waiting_for_take_subscription_id = State()
    waiting_for_delete_user_id = State()