from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.exceptions import NotFoundError
from app.services.schemas import PersonInput


class ProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> User:
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        return user

    async def update(self, user_id: int, person: PersonInput) -> User:
        user = await self.get(user_id)
        user.last_name = person.last_name
        user.first_name = person.first_name
        user.middle_name = person.middle_name
        user.contact = person.contact
        user.group_name = person.group_name
        return user

    async def clear(self, user_id: int) -> User:
        user = await self.get(user_id)
        user.last_name = None
        user.first_name = None
        user.middle_name = None
        user.contact = None
        user.group_name = None
        return user
