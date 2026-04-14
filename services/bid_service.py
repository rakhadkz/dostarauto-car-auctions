from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Bid


async def get_user_bid(
    session: AsyncSession, auction_id: int, user_id: int
) -> Bid | None:
    result = await session.execute(
        select(Bid).where(Bid.auction_id == auction_id, Bid.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_max_bid(session: AsyncSession, auction_id: int) -> float | None:
    """Returns the current maximum bid amount for an auction, or None if no bids."""
    result = await session.execute(
        select(func.max(Bid.amount)).where(Bid.auction_id == auction_id)
    )
    value = result.scalar_one_or_none()
    return float(value) if value is not None else None


async def delete_user_bid(
    session: AsyncSession, auction_id: int, user_id: int
) -> tuple[bool, bool, float | None]:
    """
    Hard-deletes the user's bid for this auction.

    Returns (deleted, was_at_auction_max, new_max_after_delete).
    was_at_auction_max: user's amount was equal to global max before delete.
    """
    bid = await get_user_bid(session, auction_id, user_id)
    if not bid:
        return False, False, await get_max_bid(session, auction_id)

    max_before = await get_max_bid(session, auction_id)
    user_amount = float(bid.amount)
    was_at_max = max_before is not None and abs(user_amount - max_before) < 0.01

    await session.delete(bid)
    await session.commit()

    new_max = await get_max_bid(session, auction_id)
    return True, was_at_max, new_max


async def place_or_update_bid(
    session: AsyncSession,
    auction_id: int,
    user_id: int,
    amount: float,
) -> tuple[Bid, bool]:
    """Returns (bid, is_new_bid). Enforces unique constraint via update-or-insert."""
    existing = await get_user_bid(session, auction_id, user_id)

    utc_now = datetime.now(tz=timezone.utc).replace(tzinfo=None)

    if existing:
        existing.amount = amount
        existing.updated_at = utc_now
        await session.commit()
        return existing, False

    bid = Bid(
        auction_id=auction_id,
        user_id=user_id,
        amount=amount,
        created_at=utc_now,
        updated_at=utc_now,
    )
    session.add(bid)
    await session.commit()
    return bid, True


async def get_user_bids_with_auctions(
    session: AsyncSession, user_id: int
) -> list[tuple]:
    from models import Auction

    result = await session.execute(
        select(Bid, Auction)
        .join(Auction, Bid.auction_id == Auction.id)
        .where(Bid.user_id == user_id)
        .order_by(Bid.updated_at.desc())
    )
    return result.all()
