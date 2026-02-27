from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


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
            [KeyboardButton(text="➕ Создать мероприятие"), KeyboardButton(text="📋 Список мероприятий")],
            [KeyboardButton(text="📣 Опубликовать в канал"), KeyboardButton(text="🧾 Регистрации по мероприятию")],
            [KeyboardButton(text="🕒 Очередь ожидания"), KeyboardButton(text="📤 Экспорт CSV/Excel")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="👮 Админы")],
        ],
        resize_keyboard=True,
    )
