import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from config import fmt_dt
from database import async_session_factory
from keyboards.participant import auction_update_keyboard
from services.auction_service import get_auction_with_bids, get_expired_active_auctions
from services.notification_service import notify_auction_finished, notify_winner

logger = logging.getLogger(__name__)


async def send_auction_reminders(bot: Bot, auction_id: int) -> None:
    """Sends a halfway reminder to all participants who have placed a bid."""
    async with async_session_factory() as session:
        auction = await get_auction_with_bids(session, auction_id)

        if not auction or auction.status != "active":
            logger.info(f"Reminder skipped for auction {auction_id} — not active.")
            return

        end_str = fmt_dt(auction.end_time)
        sent = 0
        for bid in auction.bids:
            try:
                await bot.send_message(
                    bid.user.telegram_id,
                    f"⏰ *Напоминание: аукцион скоро завершится!*\n\n"
                    f"🚗 {auction.title}\n"
                    f"💰 Ваша текущая ставка: *{float(bid.amount):,.0f} KZT*\n"
                    f"⏰ Завершается: {end_str}\n\n"
                    f"Вы ещё можете изменить ставку до завершения аукциона.",
                    parse_mode="Markdown",
                    reply_markup=auction_update_keyboard(auction_id),
                )
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send reminder to {bid.user.telegram_id}: {e}")

        logger.info(f"Auction {auction_id} reminder sent to {sent} participant(s).")


async def check_and_close_auctions(bot: Bot) -> None:
    """Finds expired active auctions, determines winners, and sends notifications."""
    async with async_session_factory() as session:
        auctions = await get_expired_active_auctions(session)

        for auction in auctions:
            try:
                await _close_auction(session, bot, auction)
            except Exception as e:
                logger.error(f"Error closing auction {auction.id} '{auction.title}': {e}")


async def _close_auction(session: AsyncSession, bot: Bot, auction) -> None:
    winner_bid = None
    if auction.bids:
        winner_bid = max(auction.bids, key=lambda b: float(b.amount))

    auction.status = "finished"
    auction.winner_id = winner_bid.user_id if winner_bid else None
    await session.commit()

    logger.info(
        f"Auction {auction.id} '{auction.title}' closed. "
        f"Winner: {winner_bid.user.telegram_id if winner_bid else 'none'}"
    )

    winner_user_id = winner_bid.user_id if winner_bid else None
    for bid in auction.bids:
        if bid.user_id == winner_user_id:
            await notify_winner(bot, bid.user, auction, float(bid.amount))
        else:
            await notify_auction_finished(bot, bid.user, auction)
