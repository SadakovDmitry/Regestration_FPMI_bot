from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    last_name = State()
    first_name = State()
    middle_name = State()
    contact = State()
    group_name = State()


class EventCreateStates(StatesGroup):
    type = State()
    title = State()
    description = State()
    reg_start = State()
    reg_end = State()
    start_at = State()
    location = State()
    capacity = State()
    team_min = State()
    team_max = State()
    photo = State()
    preview = State()


class PublishScheduleStates(StatesGroup):
    publish_at = State()


class RegistrationStates(StatesGroup):
    last_name = State()
    first_name = State()
    middle_name = State()
    contact = State()
    group_or_not_mipt = State()
    group_name = State()
    pd_consent = State()

    team_name = State()
    team_size = State()
    team_has_not_mipt = State()
    not_mipt_count = State()

    member_last_name = State()
    member_first_name = State()
    member_middle_name = State()

    passport_series = State()
    passport_number = State()
    passport_issued_by = State()
    passport_division_code = State()
    passport_issue_date = State()
    birth_date = State()
    birth_place = State()
    registration_address = State()
    confirm = State()
