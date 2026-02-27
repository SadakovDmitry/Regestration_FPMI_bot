from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Event, Registration, User
from app.models.enums import DeliveryKind, RegistrationStatus
from app.repositories.deliveries import DeliveryRepository

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
        self.settings = get_settings()
        self.delivery_repo = DeliveryRepository(session)

    async def notify_new_event(self, event: Event) -> int:
        return await self._broadcast_all_users(
            event=event,
            kind=DeliveryKind.new_event,
            text=(
                f"🎉 Новое мероприятие: {event.title}\n"
                f"🗓 Когда: {event.start_at:%d.%m.%Y %H:%M}\n"
                "Жми «Открыть мероприятие», чтобы посмотреть детали и зарегистрироваться."
            ),
            markup=self._event_cta(event.id),
        )

    async def notify_registration_started(self, event: Event) -> int:
        return await self._broadcast_all_users(
            event=event,
            kind=DeliveryKind.registration_started,
            text=(
                f"🚀 Регистрация на «{event.title}» уже открыта!\n"
                f"Успей до {event.registration_end_at:%d.%m.%Y %H:%M}."
            ),
            markup=self._event_cta(event.id),
        )

    async def notify_registration_ends_soon(self, event: Event) -> int:
        return await self._broadcast_all_users(
            event=event,
            kind=DeliveryKind.registration_ends_soon,
            text=(
                f"⏳ До конца регистрации на «{event.title}» остался 1 час.\n"
                "Если планируешь участвовать, лучше зарегистрироваться сейчас."
            ),
            markup=self._event_cta(event.id),
        )

    async def notify_waitlist_invites(self, event_id: int) -> int:
        result = await self.session.execute(
            select(Registration)
            .join(User, User.id == Registration.user_id)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.invited_from_waitlist,
            )
        )
        registrations = list(result.scalars().all())

        sent = 0
        for registration in registrations:
            user = await self.session.get(User, registration.user_id)
            if not user or not user.is_reachable:
                continue
            if await self.delivery_repo.exists(user.id, event_id, DeliveryKind.waitlist_invite):
                continue
            ok = await self._safe_send(
                user,
                text="🔥 Освободилось место! Готов(а) участвовать? Ответь в течение 12 часов.",
                markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Да",
                                callback_data=f"waitlist_yes:{registration.id}",
                            ),
                            InlineKeyboardButton(
                                text="Нет",
                                callback_data=f"waitlist_no:{registration.id}",
                            ),
                        ]
                    ]
                ),
            )
            if not ok:
                continue
            await self._log_delivery(user.id, event_id, DeliveryKind.waitlist_invite)
            sent += 1

        return sent

    async def notify_confirmations(self, event_id: int) -> int:
        result = await self.session.execute(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.confirmation_requested_at.is_not(None),
                Registration.status.in_(
                    (
                        RegistrationStatus.registered,
                        RegistrationStatus.invited_from_waitlist,
                        RegistrationStatus.confirmed,
                    )
                ),
            )
        )
        registrations = list(result.scalars().all())

        sent = 0
        for registration in registrations:
            user = await self.session.get(User, registration.user_id)
            if not user or not user.is_reachable:
                continue
            if await self.delivery_repo.exists(user.id, event_id, DeliveryKind.confirmation_24h):
                continue

            ok = await self._safe_send(
                user,
                text="✅ Мероприятие уже скоро. Подтверди участие в течение 12 часов.",
                markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Пойду",
                                callback_data=f"confirm_yes:{registration.id}",
                            ),
                            InlineKeyboardButton(
                                text="Не пойду",
                                callback_data=f"confirm_no:{registration.id}",
                            ),
                        ]
                    ]
                ),
            )
            if not ok:
                continue
            await self._log_delivery(user.id, event_id, DeliveryKind.confirmation_24h)
            sent += 1

        return sent

    async def notify_ping_2h(self, event_id: int) -> int:
        result = await self.session.execute(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.confirmed,
            )
        )
        registrations = list(result.scalars().all())

        sent = 0
        for registration in registrations:
            user = await self.session.get(User, registration.user_id)
            if not user or not user.is_reachable:
                continue
            if await self.delivery_repo.exists(user.id, event_id, DeliveryKind.ping_2h):
                continue
            ok = await self._safe_send(
                user,
                text="⏰ Напоминание: до мероприятия осталось 2 часа.",
                markup=self._my_regs_cta(),
            )
            if not ok:
                continue
            await self._log_delivery(user.id, event_id, DeliveryKind.ping_2h)
            sent += 1

        return sent

    async def notify_ping_4d(self, event_id: int) -> int:
        result = await self.session.execute(
            select(Registration)
            .where(
                Registration.event_id == event_id,
                Registration.status.in_(
                    (
                        RegistrationStatus.registered,
                        RegistrationStatus.invited_from_waitlist,
                        RegistrationStatus.confirmed,
                    )
                ),
                Registration.has_not_mipt_members.is_(True),
            )
            .distinct()
        )
        registrations = list(result.scalars().all())

        sent = 0
        for registration in registrations:
            user = await self.session.get(User, registration.user_id)
            if not user or not user.is_reachable:
                continue
            if await self.delivery_repo.exists(user.id, event_id, DeliveryKind.ping_4d):
                continue
            ok = await self._safe_send(
                user,
                text="🛂 Проверь паспортные данные для оформления проходки.",
                markup=self._my_regs_cta(),
            )
            if not ok:
                continue
            await self._log_delivery(user.id, event_id, DeliveryKind.ping_4d)
            sent += 1

        return sent

    async def _broadcast_all_users(
        self,
        event: Event,
        kind: DeliveryKind,
        text: str,
        markup: InlineKeyboardMarkup,
    ) -> int:
        users_result = await self.session.execute(select(User).where(User.is_reachable.is_(True)))
        users = list(users_result.scalars().all())
        sent = 0

        for user in users:
            if await self.delivery_repo.exists(user.id, event.id, kind):
                continue

            ok = await self._safe_send(user=user, text=text, markup=markup)
            if ok:
                await self._log_delivery(user_id=user.id, event_id=event.id, kind=kind)
                sent += 1

            await self._throttle_mass_send()

        return sent

    async def _safe_send(
        self,
        user: User,
        text: str,
        markup: InlineKeyboardMarkup,
        retry_on_flood: bool = True,
    ) -> bool:
        try:
            await self.bot.send_message(chat_id=user.tg_id, text=text, reply_markup=markup)
            return True
        except TelegramRetryAfter as exc:
            wait_seconds = max(float(exc.retry_after), 1.0)
            logger.warning(
                "Telegram flood control for tg_id=%s retry_after=%s",
                user.tg_id,
                wait_seconds,
            )
            if not retry_on_flood:
                return False
            await asyncio.sleep(wait_seconds)
            return await self._safe_send(
                user=user,
                text=text,
                markup=markup,
                retry_on_flood=False,
            )
        except (TelegramForbiddenError, TelegramBadRequest):
            user.is_reachable = False
            logger.info("User is unreachable tg_id=%s", user.tg_id)
            return False
        except Exception:
            logger.exception("Unexpected telegram send error tg_id=%s", user.tg_id)
            return False

    async def _throttle_mass_send(self) -> None:
        delay = max(float(self.settings.mass_send_delay_seconds), 0.0)
        if delay > 0:
            await asyncio.sleep(delay)

    async def _log_delivery(self, user_id: int, event_id: int | None, kind: DeliveryKind) -> None:
        async with self.session.begin_nested():
            try:
                await self.delivery_repo.add(user_id=user_id, event_id=event_id, kind=kind)
                await self.session.flush()
            except IntegrityError:
                pass

    @staticmethod
    def _event_cta(event_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Открыть мероприятие",
                        callback_data=f"event_open:{event_id}",
                    )
                ],
                [InlineKeyboardButton(text="Мои регистрации", callback_data="my_regs")],
            ]
        )

    @staticmethod
    def _my_regs_cta() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Мои регистрации", callback_data="my_regs")],
            ]
        )
