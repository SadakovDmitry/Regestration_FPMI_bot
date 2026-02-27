from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NotificationDelivery
from app.models.enums import DeliveryKind


class DeliveryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def exists(self, user_id: int, event_id: int | None, kind: DeliveryKind) -> bool:
        result = await self.session.execute(
            select(NotificationDelivery.id).where(
                NotificationDelivery.user_id == user_id,
                NotificationDelivery.event_id == event_id,
                NotificationDelivery.kind == kind,
            )
        )
        return result.scalar_one_or_none() is not None

    async def add(
        self,
        user_id: int,
        event_id: int | None,
        kind: DeliveryKind,
        payload_ref: str | None = None,
    ) -> NotificationDelivery:
        item = NotificationDelivery(
            user_id=user_id,
            event_id=event_id,
            kind=kind,
            payload_ref=payload_ref,
        )
        self.session.add(item)
        await self.session.flush()
        return item
