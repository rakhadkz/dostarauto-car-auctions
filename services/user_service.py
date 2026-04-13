from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    phone: str,
    iin: str,
    bank_account: str,
) -> User:
    user = User(
        telegram_id=telegram_id,
        full_name=full_name,
        phone=phone,
        iin=iin,
        bank_account=bank_account,
        status="pending_review",
        is_admin=False,
        created_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_status(session: AsyncSession, user_id: int, status: str) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.status = status
        await session.commit()
        await session.refresh(user)
    return user


async def get_users_by_status(session: AsyncSession, status: str) -> list[User]:
    result = await session.execute(
        select(User).where(User.status == status).order_by(User.created_at)
    )
    return list(result.scalars().all())


async def get_approved_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(User.status == "approved")
    )
    return list(result.scalars().all())
