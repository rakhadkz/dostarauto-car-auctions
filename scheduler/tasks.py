import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from config import fmt_dt
from database import async_session_factory
from keyboards.participant import auction_update_keyboard
from services.auction_close_service import finalize_auction_close
from services.auction_service import get_auction_with_bids, get_expired_active_auctions

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
                await finalize_auction_close(session, bot, auction, mode="scheduled")
            except Exception as e:
                logger.error(f"Error closing auction {auction.id} '{auction.title}': {e}")
