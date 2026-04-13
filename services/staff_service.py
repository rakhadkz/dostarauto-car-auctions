from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Staff


async def get_staff_by_telegram_id(session: AsyncSession, telegram_id: int) -> Staff | None:
    result = await session.execute(select(Staff).where(Staff.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_all_staff(session: AsyncSession) -> list[Staff]:
    result = await session.execute(select(Staff).order_by(Staff.created_at))
    return list(result.scalars().all())


async def get_staff_by_role(session: AsyncSession, role: str) -> list[Staff]:
    result = await session.execute(
        select(Staff).where(Staff.role == role).order_by(Staff.created_at)
    )
    return list(result.scalars().all())


async def add_staff(
    session: AsyncSession, telegram_id: int, role: str, added_by: int
) -> tuple[Staff, bool]:
    """Returns (staff, is_new). If already exists, updates role."""
    existing = await get_staff_by_telegram_id(session, telegram_id)
    if existing:
        existing.role = role
        await session.commit()
        return existing, False

    staff = Staff(
        telegram_id=telegram_id,
        role=role,
        added_by=added_by,
        created_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
    )
    session.add(staff)
    await session.commit()
    return staff, True


async def remove_staff(session: AsyncSession, staff_id: int) -> Staff | None:
    result = await session.execute(select(Staff).where(Staff.id == staff_id))
    staff = result.scalar_one_or_none()
    if staff:
        await session.delete(staff)
        await session.commit()
    return staff
