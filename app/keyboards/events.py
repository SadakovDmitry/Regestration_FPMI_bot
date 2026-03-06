from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Event
from app.models.enums import EventType


def events_list_kb(events: list[Event]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for event in events:
        kb.button(text=event.title, callback_data=f"event_open:{event.id}")
    kb.adjust(1)
    return kb.as_markup()


def event_card_kb(event_id: int, can_register: bool, can_cancel: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_register:
        kb.button(text="✅ Зарегистрироваться", callback_data=f"register_event:{event_id}")
    if can_cancel:
        kb.button(text="❌ Отменить", callback_data=f"cancel_event:{event_id}")
    kb.button(text="🧾 Мои регистрации", callback_data="my_regs")
    kb.button(text="🔙 Назад", callback_data="events_back")
    kb.adjust(1)
    return kb.as_markup()


def group_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="С Физтеха", callback_data="group_mipt")],
            [InlineKeyboardButton(text="Не с Физтеха", callback_data="group_not_mipt")],
        ]
    )


def yes_no_kb(yes_data: str, no_data: str, yes_text: str = "Да", no_text: str = "Нет") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=yes_text, callback_data=yes_data),
                InlineKeyboardButton(text=no_text, callback_data=no_data),
            ]
        ]
    )


def pd_consent_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Я согласен(на) на обработку персональных данных",
                    callback_data="pd_consent_yes",
                )
            ]
        ]
    )


def event_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=EventType.solo.value, callback_data="event_type:solo"),
                InlineKeyboardButton(text=EventType.team.value, callback_data="event_type:team"),
            ]
        ]
    )
