from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery


class HideUsedInlineKeyboardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if event.message is not None:
            try:
                await event.message.edit_reply_markup(reply_markup=None)
            except (TelegramBadRequest, TelegramForbiddenError):
                # Keyboard may already be removed, message may be not editable, etc.
                pass

        return await handler(event, data)
