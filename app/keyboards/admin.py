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


def edit_event_fields_kb(is_team: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Название", callback_data="edit_field:title")
    kb.button(text="Описание", callback_data="edit_field:description")
    kb.button(text="Дата/время события", callback_data="edit_field:start_at")
    kb.button(text="Место", callback_data="edit_field:location")
    kb.button(text="Начало регистрации", callback_data="edit_field:registration_start_at")
    kb.button(text="Конец регистрации", callback_data="edit_field:registration_end_at")
    kb.button(text="Лимит мест", callback_data="edit_field:capacity")
    kb.button(text="Фото", callback_data="edit_field:photo_file_id")
    if is_team:
        kb.button(text="Мин. размер команды", callback_data="edit_field:team_min_size")
        kb.button(text="Макс. размер команды", callback_data="edit_field:team_max_size")
    kb.button(text="✅ Готово", callback_data="edit_done")
    kb.adjust(2)
    return kb.as_markup()
