from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Event


def events_admin_list_kb(events: list[Event], prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for event in events:
        kb.button(text=f"#{event.id} • {event.title}", callback_data=f"{prefix}:{event.id}")
    kb.adjust(1)
    return kb.as_markup()


def export_kind_kb(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 CSV: все заявки", callback_data=f"export_all_csv:{event_id}")],
            [InlineKeyboardButton(text="✅ CSV: только confirmed", callback_data=f"export_confirmed_csv:{event_id}")],
            [InlineKeyboardButton(text="🛂 CSV: данные для проходок", callback_data=f"export_passes_csv:{event_id}")],
            [InlineKeyboardButton(text="📊 XLSX: все заявки", callback_data=f"export_all_xlsx:{event_id}")],
        ]
    )


def publish_mode_kb(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Запустить сейчас",
                    callback_data=f"publish_now:{event_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Запланировать запуск",
                    callback_data=f"publish_later:{event_id}",
                )
            ],
        ]
    )
