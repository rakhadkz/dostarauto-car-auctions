from datetime import datetime, timedelta, timezone
from models.auction import Auction

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Auction, AuctionPhoto, Bid


async def create_auction(
    session: AsyncSession,
    title: str,
    description: str,
    min_bid: float,
    duration_minutes: int,
    photo_file_ids: list[str],
) -> Auction:
    utc_now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    end_time = utc_now + timedelta(minutes=duration_minutes)
    auction = Auction(
        title=title,
        description=description,
        min_bid=min_bid,
        end_time=end_time,
        status="active",
        created_at=utc_now,
    )
    session.add(auction)
    await session.flush()

    for file_id in photo_file_ids:
        session.add(AuctionPhoto(auction_id=auction.id, file_id=file_id))

    await session.commit()
    await session.refresh(auction)
    return auction


async def get_active_auctions(session: AsyncSession) -> list[Auction]:
    result = await session.execute(
        select(Auction)
        .where(Auction.status == "active")
        .options(selectinload(Auction.photos), selectinload(Auction.bids))
        .order_by(Auction.created_at.desc())
    )
    return list(result.scalars().all())


async def get_completed_auctions(session: AsyncSession) -> list[Auction]:
    result = await session.execute(
        select(Auction)
        .where(Auction.status == "finished")
        .options(selectinload(Auction.photos))
        .order_by(Auction.created_at.desc())
    )
    return list(result.scalars().all())


async def get_auction_with_bids(session: AsyncSession, auction_id: int) -> Auction | None:
    result = await session.execute(
        select(Auction)
        .where(Auction.id == auction_id)
        .options(
            selectinload(Auction.photos),
            selectinload(Auction.bids).selectinload(Bid.user),
            selectinload(Auction.winner),
        )
    )
    return result.scalar_one_or_none()


async def get_expired_active_auctions(session: AsyncSession) -> list[Auction]:
    # Strip tzinfo for comparison with naive DB column
    now_naive = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    result = await session.execute(
        select(Auction)
        .where(Auction.status == "active", Auction.end_time <= now_naive)
        .options(selectinload(Auction.bids).selectinload(Bid.user))
    )
    return list[Auction](result.scalars().all())
