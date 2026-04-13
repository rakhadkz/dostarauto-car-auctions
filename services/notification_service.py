import logging

from aiogram import Bot
from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from config import fmt_dt, settings
from keyboards.participant import auction_keyboard
from models import Auction, User
from services.staff_service import get_all_staff
from services.user_service import get_approved_users

logger = logging.getLogger(__name__)


async def notify_admins(
    bot: Bot,
    text: str,
    reply_markup=None,
    parse_mode: str = "Markdown",
    session=None,
) -> None:
    """Notifies all superadmins (from env) and all staff (from DB) if session is provided."""
    recipient_ids: set[int] = set(settings.superadmin_ids)

    if session is not None:
        staff_list = await get_all_staff(session)
        for s in staff_list:
            recipient_ids.add(s.telegram_id)

    for admin_id in recipient_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Failed to notify staff {admin_id}: {e}")


async def send_auction_to_user(bot: Bot, user_id: int, auction: Auction) -> None:
    try:
        if auction.photos:
            if len(auction.photos) == 1:
                await bot.send_photo(user_id, auction.photos[0].file_id)
            else:
                media = [InputMediaPhoto(media=p.file_id) for p in auction.photos]
                await bot.send_media_group(user_id, media)

        end_time_str = fmt_dt(auction.end_time)
        text = (
            f"🚗 *Новый аукцион: {auction.title}*\n\n"
            f"{auction.description}\n\n"
            f"💰 Минимальная ставка: {float(auction.min_bid):,.0f} KZT\n"
            f"⏰ Завершается: {end_time_str}"
        )
        await bot.send_message(
            user_id,
            text,
            parse_mode="Markdown",
            reply_markup=auction_keyboard(auction.id),
        )
    except Exception as e:
        logger.error(f"Failed to send auction to user {user_id}: {e}")


async def notify_auction_created(bot: Bot, session: AsyncSession, auction: Auction) -> None:
    approved_users = await get_approved_users(session)
    for user in approved_users:
        await send_auction_to_user(bot, user.telegram_id, auction)


async def notify_winner(bot: Bot, winner: User, auction: Auction, winning_amount: float) -> None:
    try:
        text = (
            f"🎉 *Поздравляем! Вы выиграли аукцион!*\n\n"
            f"🚗 {auction.title}\n"
            f"💰 Ваша выигрышная ставка: {winning_amount:,.0f} KZT\n\n"
            f"Пожалуйста, произведите оплату:\n{settings.KASPI_WINNER_LINK}"
        )
        await bot.send_message(winner.telegram_id, text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to notify winner {winner.telegram_id}: {e}")


async def notify_auction_finished(bot: Bot, user: User, auction: Auction) -> None:
    try:
        text = (
            f"🏁 *Аукцион завершён:* {auction.title}\n\n"
            f"Спасибо за участие!"
        )
        await bot.send_message(user.telegram_id, text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to notify participant {user.telegram_id}: {e}")
