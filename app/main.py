from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.handlers.admin import admin_router
from app.handlers.user import user_router
from app.logging_config import setup_logging


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(user_router)

    logging.getLogger(__name__).info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
