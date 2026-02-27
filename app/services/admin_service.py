from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories.admins import AdminRepository


class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.repo = AdminRepository(session)

    async def is_admin(self, tg_id: int) -> bool:
        if tg_id in self.settings.admin_ids or tg_id in self.settings.super_admin_ids:
            return True
        return await self.repo.is_admin(tg_id)

    async def is_super_admin(self, tg_id: int) -> bool:
        return tg_id in self.settings.super_admin_ids

    async def add_admin(self, tg_id: int, added_by_tg_id: int) -> None:
        if await self.repo.is_admin(tg_id):
            return
        await self.repo.add_admin(tg_id=tg_id, added_by_tg_id=added_by_tg_id)

    async def remove_admin(self, tg_id: int) -> bool:
        if tg_id in self.settings.super_admin_ids:
            return False
        return await self.repo.delete_admin(tg_id)
