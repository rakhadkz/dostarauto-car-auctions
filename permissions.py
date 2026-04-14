from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.staff_service import get_staff_by_telegram_id


def is_superadmin(telegram_id: int) -> bool:
    return telegram_id in settings.superadmin_ids


async def get_role(session: AsyncSession, telegram_id: int) -> str | None:
    """Returns 'superadmin', 'admin', 'manager', or None (regular user)."""
    if is_superadmin(telegram_id):
        return "superadmin"
    staff = await get_staff_by_telegram_id(session, telegram_id)
    if staff:
        return staff.role
    return None


async def is_any_staff(session: AsyncSession, telegram_id: int) -> bool:
    role = await get_role(session, telegram_id)
    return role is not None


async def can_revoke(session: AsyncSession, telegram_id: int) -> bool:
    role = await get_role(session, telegram_id)
    return role in ("superadmin", "admin")


async def can_manage_staff(session: AsyncSession, telegram_id: int) -> bool:
    return is_superadmin(telegram_id)


async def can_manage_clients(session: AsyncSession, telegram_id: int) -> bool:
    """Managers may only manage auctions, not users (approve/revoke/payments)."""
    role = await get_role(session, telegram_id)
    return role in ("superadmin", "admin")
