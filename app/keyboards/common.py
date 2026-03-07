from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

ADMIN_BTN_CREATE_EVENT = "➕ Создать мероприятие"
ADMIN_BTN_EVENTS_LIST = "📋 Мероприятия (все)"
ADMIN_BTN_PUBLISH = "🚀 Запустить мероприятие"
ADMIN_BTN_REGISTRATIONS = "🧾 Заявки на мероприятие"
ADMIN_BTN_WAITLIST = "⏳ Лист ожидания"
ADMIN_BTN_EXPORT = "📤 Выгрузка CSV/XLSX"
ADMIN_BTN_DELETE_EVENT = "🗑️ Удалить мероприятие"
ADMIN_BTN_SETTINGS = "⚙️ Настройки бота"
ADMIN_BTN_ADMINS = "👮 Управление админами"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Мероприятия"), KeyboardButton(text="🧾 Мои регистрации")],
            [KeyboardButton(text="🕒 Лист ожидания"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_BTN_CREATE_EVENT), KeyboardButton(text=ADMIN_BTN_EVENTS_LIST)],
            [KeyboardButton(text=ADMIN_BTN_PUBLISH), KeyboardButton(text=ADMIN_BTN_REGISTRATIONS)],
            [KeyboardButton(text=ADMIN_BTN_WAITLIST), KeyboardButton(text=ADMIN_BTN_EXPORT)],
            [KeyboardButton(text=ADMIN_BTN_DELETE_EVENT), KeyboardButton(text=ADMIN_BTN_SETTINGS)],
            [KeyboardButton(text=ADMIN_BTN_ADMINS)],
        ],
        resize_keyboard=True,
    )
