"""Finalize active auctions (scheduled expiry or manual close)."""

import logging
from typing import Literal

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from models import Auction
from services.notification_service import (
    notify_auction_finished,
    notify_staff_auction_closed,
    notify_winner,
)

logger = logging.getLogger(__name__)

CloseMode = Literal["scheduled", "manual"]


async def finalize_auction_close(
    session: AsyncSession,
    bot: Bot,
    auction: Auction,
    *,
    mode: CloseMode,
) -> None:
    """
    Sets status finished and winner_id, commits, then sends notifications.
    `auction.bids` must be loaded (with `Bid.user`) for participant messages.
    """
    winner_bid = None
    if auction.bids:
        winner_bid = max(auction.bids, key=lambda b: float(b.amount))

    auction.status = "finished"
    auction.winner_id = winner_bid.user_id if winner_bid else None
    await session.commit()

    logger.info(
        "Auction %s '%s' closed (%s). Winner: %s",
        auction.id,
        auction.title,
        mode,
        winner_bid.user.telegram_id if winner_bid else "none",
    )

    win_amount = float(winner_bid.amount) if winner_bid else None
    early = mode == "manual"
    await notify_staff_auction_closed(bot, session, auction, win_amount, early=early)

    winner_user_id = winner_bid.user_id if winner_bid else None
    for bid in auction.bids:
        if bid.user_id == winner_user_id:
            await notify_winner(bot, bid.user, auction, float(bid.amount))
        else:
            await notify_auction_finished(bot, bid.user, auction)
