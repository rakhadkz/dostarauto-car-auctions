import html
import logging
from typing import Literal

from aiogram import Bot
from aiogram.types import InputMediaPhoto
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import fmt_dt, settings
from keyboards.participant import auction_keyboard, auction_update_keyboard
from models import Auction, Bid, User
from services.staff_service import get_all_staff
from services.user_service import get_approved_users

logger = logging.getLogger(__name__)

# Telegram allows at most 10 items per send_media_group / answer_media_group.
_TELEGRAM_MEDIA_GROUP_LIMIT = 10


async def notify_admins(
    bot: Bot,
    text: str,
    reply_markup=None,
    parse_mode: str = "Markdown",
    session=None,
    *,
    staff_filter: Literal["all", "admins_only"] = "all",
) -> None:
    """
    Notifies superadmins (from env) and DB staff when session is provided.

    staff_filter:
      - all: superadmins + every staff row (admin + manager) — e.g. bids, auction closed
      - admins_only: superadmins + staff with role admin — e.g. registration / payments
    """
    recipient_ids: set[int] = set(settings.superadmin_ids)

    if session is not None:
        staff_list = await get_all_staff(session)
        for s in staff_list:
            if staff_filter == "admins_only" and s.role != "admin":
                continue
            recipient_ids.add(s.telegram_id)

    for admin_id in recipient_ids:
        try:
            await bot.send_message(
                admin_id, text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Failed to notify staff {admin_id}: {e}")


async def send_auction_to_user(bot: Bot, user_id: int, auction: Auction) -> None:
    try:
        if auction.photos:
            plist = list(auction.photos)
            if len(plist) == 1:
                await bot.send_photo(user_id, plist[0].file_id)
            else:
                for i in range(0, len(plist), _TELEGRAM_MEDIA_GROUP_LIMIT):
                    chunk = plist[i : i + _TELEGRAM_MEDIA_GROUP_LIMIT]
                    media = [InputMediaPhoto(media=p.file_id) for p in chunk]
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


async def notify_auction_created(
    bot: Bot, session: AsyncSession, auction: Auction
) -> None:
    approved_users = await get_approved_users(session)
    for user in approved_users:
        await send_auction_to_user(bot, user.telegram_id, auction)


async def notify_winner(
    bot: Bot, winner: User, auction: Auction, winning_amount: float
) -> None:
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
        text = f"🏁 *Аукцион завершён:* {auction.title}\n\n" f"Спасибо за участие!"
        await bot.send_message(user.telegram_id, text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to notify participant {user.telegram_id}: {e}")


async def notify_staff_auction_closed(
    bot: Bot,
    session: AsyncSession,
    auction: Auction,
    winning_amount: float | None,
    *,
    early: bool = False,
) -> None:
    """Notifies superadmins and DB staff when an auction ends (winner only)."""
    title_esc = html.escape(auction.title or "")
    if early:
        header = "⏱️ <b>Аукцион был досрочно завершён</b>"
    else:
        header = "🏁 <b>Аукцион завершён</b>"
    time_caption = "Запланированное время завершения" if early else "Время завершения"
    lines = [
        header,
        "",
        f"🚗 <b>{title_esc}</b>",
        f"🆔 ID аукциона: <code>{auction.id}</code>",
        f"⏰ {time_caption}: {html.escape(fmt_dt(auction.end_time))}",
        "",
    ]
    if auction.winner_id and winning_amount is not None:
        winner = next(
            (b.user for b in auction.bids if b.user_id == auction.winner_id), None
        )
        if winner:
            lines.append(
                f"🏆 <b>Победитель — {html.escape(winner.full_name or '')}</b>"
            )
            lines.append(f"📞 {html.escape(winner.phone or '')}")
            lines.append(f"💰 Ставка: <b>{winning_amount:,.0f}</b> KZT")
        else:
            lines.append(
                f"🏆 Победитель ID: <code>{auction.winner_id}</code> — "
                f"<b>{winning_amount:,.0f}</b> KZT"
            )
    else:
        lines.append("⚠️ <b>Победителя нет</b> (ставок не было).")

    text = "\n".join(lines)
    await notify_admins(bot, text, session=session, parse_mode="HTML")


async def notify_bid_placed(
    bot: Bot,
    session: AsyncSession,
    auction: Auction,
    new_max: float,
    next_min: float,
    author_user_id: int,
) -> None:
    """Notify all bidders on the auction (except the one who just bid) about the new max."""
    result = await session.execute(
        select(Bid)
        .where(Bid.auction_id == auction.id, Bid.user_id != author_user_id)
        .options(selectinload(Bid.user))
    )
    bids = result.scalars().all()
    bid_step = float(auction.bid_step)

    for bid in bids:
        my_amount = float(bid.amount)
        personal = f"💵 *Ваша текущая ставка:* {my_amount:,.0f} KZT\n\n"
        text = (
            f"🔔 *Новая ставка в аукционе!*\n\n"
            f"🚗 {auction.title}\n\n"
            f"{personal}"
            f"💰 Текущая максимальная ставка: *{new_max:,.0f} KZT*\n"
            f"📈 Шаг ставки: *{bid_step:,.0f} KZT*\n\n"
            f"Чтобы стать лидером, ваша ставка должна быть не менее *{next_min:,.0f} KZT*"
        )
        try:
            await bot.send_message(
                bid.user.telegram_id,
                text,
                parse_mode="Markdown",
                reply_markup=auction_update_keyboard(auction.id),
            )
        except Exception as e:
            logger.error(f"Failed to notify bidder {bid.user.telegram_id}: {e}")


async def notify_bidders_max_changed_after_withdrawal(
    bot: Bot,
    session: AsyncSession,
    auction: Auction,
    new_max: float | None,
    exclude_user_id: int,
) -> None:
    """Notify remaining bidders when the auction max may have changed after a withdrawal."""
    result = await session.execute(
        select(Bid)
        .where(Bid.auction_id == auction.id, Bid.user_id != exclude_user_id)
        .options(selectinload(Bid.user))
    )
    bids = result.scalars().all()
    if not bids:
        return

    bid_step = float(auction.bid_step)
    if new_max is None:
        next_min = float(auction.min_bid)
        max_line = "_Ставок пока нет — вы можете стать лидером с минимальной ставки._"
    else:
        next_min = new_max + bid_step
        max_line = f"💰 Текущая максимальная ставка: *{new_max:,.0f} KZT*"

    for bid in bids:
        my_amount = float(bid.amount)
        is_leader = new_max is not None and abs(my_amount - new_max) < 0.01
        personal = f"💵 *Ваша текущая ставка:* {my_amount:,.0f} KZT\n"
        if is_leader:
            personal += "🏆 *Вы лидируете* — у вас сейчас максимальная ставка.\n"
        personal += "\n"

        footer = (
            ""
            if is_leader
            else f"\n\nЧтобы стать лидером, ваша ставка должна быть не менее *{next_min:,.0f} KZT*"
        )
        text = (
            f"📉 *Максимальная ставка в аукционе изменилась*\n\n"
            f"🚗 {auction.title}\n\n"
            f"{personal}"
            f"{max_line}\n"
            f"📈 Шаг ставки: *{bid_step:,.0f} KZT*"
            f"{footer}"
        )
        try:
            await bot.send_message(
                bid.user.telegram_id,
                text,
                parse_mode="Markdown",
                reply_markup=auction_update_keyboard(auction.id),
            )
        except Exception as e:
            logger.error(f"Failed to notify bidder {bid.user.telegram_id}: {e}")
