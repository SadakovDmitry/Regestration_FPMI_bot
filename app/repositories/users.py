from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.tg_id == tg_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def ensure_user(self, tg_id: int, username: str | None) -> User:
        user = await self.get_by_tg_id(tg_id)
        if user:
            if user.username != username:
                user.username = username
            return user

        user = User(tg_id=tg_id, username=username, is_reachable=True)
        self.session.add(user)
        await self.session.flush()
        return user
