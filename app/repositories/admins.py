from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Admin


class AdminRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_admin(self, tg_id: int) -> bool:
        result = await self.session.execute(select(Admin.id).where(Admin.tg_id == tg_id))
        return result.scalar_one_or_none() is not None

    async def list_admins(self) -> list[Admin]:
        result = await self.session.execute(select(Admin).order_by(Admin.tg_id.asc()))
        return list(result.scalars().all())

    async def add_admin(self, tg_id: int, added_by_tg_id: int | None = None) -> Admin:
        admin = Admin(tg_id=tg_id, added_by_tg_id=added_by_tg_id)
        self.session.add(admin)
        await self.session.flush()
        return admin

    async def delete_admin(self, tg_id: int) -> bool:
        result = await self.session.execute(select(Admin).where(Admin.tg_id == tg_id))
        admin = result.scalar_one_or_none()
        if not admin:
            return False
        await self.session.delete(admin)
        return True
