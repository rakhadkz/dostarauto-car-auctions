from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Bid


async def get_user_bid(session: AsyncSession, auction_id: int, user_id: int) -> Bid | None:
    result = await session.execute(
        select(Bid).where(Bid.auction_id == auction_id, Bid.user_id == user_id)
    )
    return result.scalar_one_or_none()


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


async def get_user_bids_with_auctions(session: AsyncSession, user_id: int) -> list[tuple]:
    from models import Auction

    result = await session.execute(
        select(Bid, Auction)
        .join(Auction, Bid.auction_id == Auction.id)
        .where(Bid.user_id == user_id)
        .order_by(Bid.updated_at.desc())
    )
    return result.all()
