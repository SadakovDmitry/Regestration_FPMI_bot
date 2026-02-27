from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Event


def events_admin_list_kb(events: list[Event], prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for event in events:
        status = event.status.value
        kb.button(text=f"{event.id}. {event.title} [{status}]", callback_data=f"{prefix}:{event.id}")
    kb.adjust(1)
    return kb.as_markup()


def export_kind_kb(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Все регистрации CSV", callback_data=f"export_all_csv:{event_id}")],
            [InlineKeyboardButton(text="Только confirmed CSV", callback_data=f"export_confirmed_csv:{event_id}")],
            [InlineKeyboardButton(text="Проходки CSV", callback_data=f"export_passes_csv:{event_id}")],
            [InlineKeyboardButton(text="Все регистрации XLSX", callback_data=f"export_all_xlsx:{event_id}")],
        ]
    )


def publish_mode_kb(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Опубликовать сейчас",
                    callback_data=f"publish_now:{event_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отложить публикацию",
                    callback_data=f"publish_later:{event_id}",
                )
            ],
        ]
    )
