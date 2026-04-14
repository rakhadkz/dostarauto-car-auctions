from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from callbacks import AuctionCB
from keyboards.participant import (
    auction_keyboard,
    auction_update_keyboard,
    delete_bid_confirm_keyboard,
    participant_main_keyboard,
)
from models import Auction, Bid
from services.auction_service import get_active_auctions
from services.bid_service import (
    delete_user_bid,
    get_max_bid,
    get_user_bid,
    get_user_bids_with_auctions,
    place_or_update_bid,
)
from services.notification_service import (
    notify_admins,
    notify_bid_placed,
    notify_bidders_max_changed_after_withdrawal,
)
from services.user_service import get_user_by_telegram_id
from states.bid import BidStates

router = Router()

# Telegram allows at most 10 items per answer_media_group.
_TELEGRAM_MEDIA_GROUP_LIMIT = 10


# ── FSM handlers must come first ─────────────────────────────────────────────


@router.message(BidStates.waiting_amount)
async def process_bid_amount(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    raw = message.text.strip().replace(",", "").replace(" ", "") if message.text else ""
    try:
        amount = float(raw)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное положительное число:")
        return

    data = await state.get_data()
    auction_id: int | None = data.get("auction_id")

    if not auction_id:
        await state.clear()
        await message.answer("❌ Что-то пошло не так. Попробуйте ещё раз.")
        return

    result = await session.execute(select(Auction).where(Auction.id == auction_id))
    auction = result.scalar_one_or_none()

    if not auction or auction.status != "active":
        await state.clear()
        await message.answer("❌ Этот аукцион уже завершён.")
        return

    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await state.clear()
        return

    bid_step = float(auction.bid_step)
    current_max = await get_max_bid(session, auction_id)
    existing = await get_user_bid(session, auction_id, user.id)
    old_amount = float(existing.amount) if existing else None

    # Determine minimum required amount
    if current_max is None:
        # First bidder — must be >= min_bid
        min_required = float(auction.min_bid)
    else:
        # Subsequent bidders (or updaters) — must be >= current_max + step
        min_required = current_max + bid_step

    if amount < min_required:
        if current_max is None:
            await message.answer(
                f"❌ Ставка должна быть не менее *{min_required:,.0f} KZT*. Попробуйте ещё раз:",
                parse_mode="Markdown",
            )
        else:
            await message.answer(
                f"❌ Текущая максимальная ставка: *{current_max:,.0f} KZT*\n"
                f"Ваша ставка должна быть не менее *{min_required:,.0f} KZT* "
                f"(максимум + шаг {bid_step:,.0f} KZT). Попробуйте ещё раз:",
                parse_mode="Markdown",
            )
        return

    # Race-condition check: re-read max right before saving
    latest_max = await get_max_bid(session, auction_id)
    if latest_max is not None:
        # Exclude the user's own bid from the max when checking
        latest_min_required = latest_max + bid_step
        # If this user already has the current max, they just need > their own bid
        if old_amount is not None and latest_max == old_amount:
            latest_min_required = old_amount + bid_step
        if amount < latest_min_required:
            await message.answer(
                f"⚠️ Пока вы вводили ставку, кто-то сделал ставку выше!\n\n"
                f"Текущая максимальная ставка: *{latest_max:,.0f} KZT*\n"
                f"Ваша ставка должна быть не менее *{latest_min_required:,.0f} KZT*. Попробуйте ещё раз:",
                parse_mode="Markdown",
            )
            return

    _, is_new = await place_or_update_bid(session, auction_id, user.id, amount)
    await state.clear()

    # Determine new max after saving (it's now at least `amount`)
    new_max = await get_max_bid(session, auction_id)
    next_min = (new_max or amount) + bid_step

    verb = "принята" if is_new else "обновлена"
    await message.answer(
        f"✅ *Ставка {verb}!*\nВаша ставка: *{amount:,.0f} KZT*\n\n"
        f"Вы можете изменить ставку в любое время до завершения аукциона.",
        parse_mode="Markdown",
        reply_markup=auction_update_keyboard(auction_id),
    )

    action_label = "Новая ставка" if is_new else "Ставка обновлена"
    admin_text = (
        f"📣 *{action_label}*\n\n"
        f"🚗 Аукцион: {auction.title}\n"
        f"👤 Участник: {user.full_name}\n"
        f"📞 Телефон: {user.phone}\n"
        f"🪪 ИИН: {user.iin}\n"
    )
    if is_new:
        admin_text += f"💰 Ставка: *{amount:,.0f} KZT*"
    else:
        admin_text += (
            f"💰 Предыдущая ставка: {old_amount:,.0f} KZT\n"
            f"💰 Новая ставка: *{amount:,.0f} KZT*"
        )
    await notify_admins(bot, admin_text, session=session)

    # Notify all other bidders about the new max
    await notify_bid_placed(
        bot=bot,
        session=session,
        auction=auction,
        new_max=new_max or amount,
        next_min=next_min,
        author_user_id=user.id,
    )


# ── General participant handlers ──────────────────────────────────────────────


@router.callback_query(AuctionCB.filter(F.action == "delete_bid"))
async def prompt_delete_bid(
    callback: CallbackQuery, callback_data: AuctionCB, session: AsyncSession
) -> None:
    user = await get_user_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Необходима регистрация.", show_alert=True)
        return

    auction = (
        await session.execute(select(Auction).where(Auction.id == callback_data.auction_id))
    ).scalar_one_or_none()
    if not auction or auction.status != "active":
        await callback.answer("❌ Аукцион уже не активен.", show_alert=True)
        return

    bid = await get_user_bid(session, callback_data.auction_id, user.id)
    if not bid:
        await callback.answer("У вас нет ставки на этот аукцион.", show_alert=True)
        return

    await callback.message.answer(
        "⚠️ *Удаление ставки*\n\n"
        f"🚗 {auction.title}\n"
        f"Ваша ставка: *{float(bid.amount):,.0f} KZT*\n\n"
        "Вы выйдете из числа участников и перестанете получать уведомления "
        "по этому аукциону. Позже вы сможете снова сделать ставку.\n\n"
        "Удалить ставку?",
        parse_mode="Markdown",
        reply_markup=delete_bid_confirm_keyboard(callback_data.auction_id),
    )
    await callback.answer()


@router.callback_query(AuctionCB.filter(F.action == "delete_bid_cancel"))
async def cancel_delete_bid(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_user_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer("Нет доступа", show_alert=True)
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Отменено")


@router.callback_query(AuctionCB.filter(F.action == "delete_bid_confirm"))
async def confirm_delete_bid(
    callback: CallbackQuery,
    callback_data: AuctionCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    user = await get_user_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer("Нет доступа", show_alert=True)
        return

    auction = (
        await session.execute(select(Auction).where(Auction.id == callback_data.auction_id))
    ).scalar_one_or_none()
    if not auction or auction.status != "active":
        await callback.answer("❌ Аукцион уже не активен.", show_alert=True)
        return

    bid = await get_user_bid(session, callback_data.auction_id, user.id)
    if not bid:
        await callback.answer("Ставка уже удалена или не найдена.", show_alert=True)
        return

    amount_removed = float(bid.amount)
    deleted, was_at_max, new_max = await delete_user_bid(
        session, callback_data.auction_id, user.id
    )
    if not deleted:
        await callback.answer("Не удалось удалить ставку.", show_alert=True)
        return

    chat_id = callback.message.chat.id
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.answer("Ставка удалена")
    await bot.send_message(
        chat_id,
        "✅ Ваша ставка удалена. Вы больше не участвуете в этом аукционе.\n\n"
        "При желании вы можете снова сделать ставку через «🚗 Активные аукционы».",
        reply_markup=auction_keyboard(callback_data.auction_id),
    )

    admin_text = (
        f"🗑 *Участник удалил ставку*\n\n"
        f"🚗 Аукцион: {auction.title}\n"
        f"👤 {user.full_name}\n"
        f"💰 Была: *{amount_removed:,.0f} KZT*"
    )
    await notify_admins(bot, admin_text, session=session)

    if was_at_max:
        await notify_bidders_max_changed_after_withdrawal(
            bot=bot,
            session=session,
            auction=auction,
            new_max=new_max,
            exclude_user_id=user.id,
        )


@router.message(F.text == "🚗 Активные аукционы")
async def show_active_auctions(message: Message, session: AsyncSession) -> None:
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer(
            "❌ Для просмотра аукционов необходимо пройти регистрацию."
        )
        return
    if user.status == "revoked":
        await message.answer("🚫 Ваш доступ заблокирован. Обратитесь в поддержку.")
        return
    if user.status != "approved":
        await message.answer(
            "❌ Для просмотра аукционов необходимо пройти регистрацию."
        )
        return

    auctions = await get_active_auctions(session)
    if not auctions:
        await message.answer("📭 В данный момент активных аукционов нет.")
        return

    auction_ids = [a.id for a in auctions]

    # Load all bids (with user) for these auctions in one query
    bids_result = await session.execute(
        select(Bid)
        .where(Bid.auction_id.in_(auction_ids))
        .options(selectinload(Bid.user))
    )
    all_bids = bids_result.scalars().all()

    # Group bids by auction_id; keep only max bid per user per auction
    from collections import defaultdict

    bids_by_auction: dict[int, list[Bid]] = defaultdict(list)
    best_per_user: dict[tuple[int, int], Bid] = {}
    for bid in all_bids:
        key = (bid.auction_id, bid.user_id)
        prev = best_per_user.get(key)
        if prev is None or float(bid.amount) > float(prev.amount):
            best_per_user[key] = bid
    for bid in best_per_user.values():
        bids_by_auction[bid.auction_id].append(bid)
    for bids in bids_by_auction.values():
        bids.sort(key=lambda b: float(b.amount), reverse=True)

    user_bid_auction_ids = {
        bid.auction_id for (a_id, u_id), bid in best_per_user.items() if u_id == user.id
    }

    now = datetime.now(tz=timezone.utc)
    for auction in auctions:
        delta = auction.end_time.replace(tzinfo=timezone.utc) - now
        hours = max(0, int(delta.total_seconds() // 3600))
        minutes_left = max(0, int((delta.total_seconds() % 3600) // 60))

        bid_step = float(auction.bid_step)
        sorted_bids = bids_by_auction.get(auction.id, [])
        current_max = float(sorted_bids[0].amount) if sorted_bids else None
        next_min = (
            (current_max + bid_step)
            if current_max is not None
            else float(auction.min_bid)
        )

        is_participant = auction.id in user_bid_auction_ids

        text = (
            f"🚗 *{auction.title}*\n\n"
            f"{auction.description}\n\n"
            f"💰 Минимальная ставка: *{float(auction.min_bid):,.0f} KZT*\n"
            f"📈 Шаг ставки: *{bid_step:,.0f} KZT*\n"
            f"⏰ Осталось: {hours}ч {minutes_left}м"
        )

        if current_max is not None:
            text += f"\n🏆 Текущая максимальная ставка: *{current_max:,.0f} KZT*"

        if is_participant and sorted_bids:
            text += "\n\n📊 *Участники:*\n"
            for i, bid in enumerate(sorted_bids, 1):
                if bid.user_id == user.id:
                    text += f"{i}. {bid.user.full_name} — {float(bid.amount):,.0f} KZT\n"
                else:
                    text += f"Участник #{i} — {float(bid.amount):,.0f} KZT\n"
            my_bid = next((b for b in sorted_bids if b.user_id == user.id), None)
            if my_bid:
                text += (
                    f"\n💵 *Ваша ставка:* {float(my_bid.amount):,.0f} KZT\n"
                )
            text += (
                f"\n💡 Вы можете увеличить вашу ставку. "
                f"Следующая ставка должна быть не менее *{next_min:,.0f} KZT*. "
                f"Хотите увеличить ставку?"
            )
        elif not is_participant and current_max is not None:
            text += (
                f"\n\n💡 Чтобы участвовать, ваша ставка должна быть "
                f"не менее *{next_min:,.0f} KZT* "
                f"(текущий максимум + шаг)."
            )

        keyboard = (
            auction_update_keyboard(auction.id)
            if is_participant
            else auction_keyboard(auction.id)
        )

        if auction.photos:
            plist = list(auction.photos)
            if len(plist) == 1:
                await message.answer_photo(
                    plist[0].file_id,
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            else:
                for i in range(0, len(plist), _TELEGRAM_MEDIA_GROUP_LIMIT):
                    chunk = plist[i : i + _TELEGRAM_MEDIA_GROUP_LIMIT]
                    media = [InputMediaPhoto(media=p.file_id) for p in chunk]
                    await message.answer_media_group(media)
                await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.message(F.text == "📊 Мои ставки")
async def show_my_bids(message: Message, session: AsyncSession) -> None:
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("❌ Для просмотра ставок необходимо пройти регистрацию.")
        return
    if user.status == "revoked":
        await message.answer("🚫 Ваш доступ заблокирован. Обратитесь в поддержку.")
        return
    if user.status != "approved":
        await message.answer("❌ Для просмотра ставок необходимо пройти регистрацию.")
        return

    rows = await get_user_bids_with_auctions(session, user.id)
    if not rows:
        await message.answer("📭 Вы ещё не сделали ни одной ставки.")
        return

    text = "📊 *Ваши ставки*\n\n"
    for bid, auction in rows:
        emoji = "🟢" if auction.status == "active" else "🏁"
        text += f"{emoji} *{auction.title}*: {float(bid.amount):,.0f} KZT\n"

    await message.answer(text, parse_mode="Markdown")


@router.callback_query(AuctionCB.filter(F.action.in_(["bid", "update_bid"])))
async def handle_bid_callback(
    callback: CallbackQuery,
    callback_data: AuctionCB,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if not user:
        await callback.answer(
            "❌ Для участия необходимо пройти регистрацию.", show_alert=True
        )
        return
    if user.status == "revoked":
        await callback.answer(
            "🚫 Ваш доступ заблокирован. Обратитесь в поддержку.", show_alert=True
        )
        return
    if user.status != "approved":
        await callback.answer(
            "❌ Для участия в аукционе необходимо быть зарегистрированным участником.",
            show_alert=True,
        )
        return

    result = await session.execute(
        select(Auction).where(Auction.id == callback_data.auction_id)
    )
    auction = result.scalar_one_or_none()

    if not auction or auction.status != "active":
        await callback.answer("❌ Этот аукцион уже завершён.", show_alert=True)
        return

    existing = await get_user_bid(session, callback_data.auction_id, user.id)
    current_max = await get_max_bid(session, callback_data.auction_id)
    bid_step = float(auction.bid_step)

    if current_max is None:
        min_required = float(auction.min_bid)
    else:
        min_required = current_max + bid_step

    await state.update_data(auction_id=callback_data.auction_id)
    await state.set_state(BidStates.waiting_amount)

    if existing:
        await callback.message.answer(
            f"✏️ *Изменение ставки*\n\n"
            f"Ваша текущая ставка: *{float(existing.amount):,.0f} KZT*\n"
            f"📈 Шаг ставки: *{bid_step:,.0f} KZT*\n"
            + (
                f"🏆 Текущий максимум: *{current_max:,.0f} KZT*\n"
                if current_max is not None
                else ""
            )
            + f"\nВведите новую ставку (не менее *{min_required:,.0f} KZT*):",
            parse_mode="Markdown",
        )
    else:
        await callback.message.answer(
            f"💰 *Сделать ставку*\n\n"
            f"Минимальная ставка: *{float(auction.min_bid):,.0f} KZT*\n"
            f"📈 Шаг ставки: *{bid_step:,.0f} KZT*\n"
            + (
                f"🏆 Текущий максимум: *{current_max:,.0f} KZT*\n"
                if current_max is not None
                else ""
            )
            + f"\nВведите сумму ставки (не менее *{min_required:,.0f} KZT*):",
            parse_mode="Markdown",
        )

    await callback.answer()
