from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession


async def scalar_one_or_none(session: AsyncSession, stmt: Select):
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def scalars_all(session: AsyncSession, stmt: Select):
    result = await session.execute(stmt)
    return list(result.scalars().all())


def q(model):
    return select(model)
