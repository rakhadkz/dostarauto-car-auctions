from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callbacks import AuctionCB
from keyboards.participant import auction_keyboard, auction_update_keyboard, participant_main_keyboard
from models import Auction, Bid
from services.auction_service import get_active_auctions
from services.bid_service import get_user_bid, get_user_bids_with_auctions, place_or_update_bid
from services.notification_service import notify_admins
from services.user_service import get_user_by_telegram_id
from states.bid import BidStates

router = Router()


# ── FSM handlers must come first ─────────────────────────────────────────────


@router.message(BidStates.waiting_amount)
async def process_bid_amount(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
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

    if amount < float(auction.min_bid):
        await message.answer(
            f"❌ Ставка должна быть не менее *{float(auction.min_bid):,.0f} KZT*. Попробуйте ещё раз:",
            parse_mode="Markdown",
        )
        return

    existing = await get_user_bid(session, auction_id, user.id)
    old_amount = float(existing.amount) if existing else None
    if existing and amount <= old_amount:
        await message.answer(
            f"❌ Новая ставка должна быть выше текущей "
            f"*{old_amount:,.0f} KZT*. Попробуйте ещё раз:",
            parse_mode="Markdown",
        )
        return

    _, is_new = await place_or_update_bid(session, auction_id, user.id, amount)
    await state.clear()

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
    await notify_admins(bot, admin_text)


# ── General participant handlers ──────────────────────────────────────────────


@router.message(F.text == "🚗 Активные аукционы")
async def show_active_auctions(message: Message, session: AsyncSession) -> None:
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("❌ Для просмотра аукционов необходимо пройти регистрацию.")
        return
    if user.status == "revoked":
        await message.answer("🚫 Ваш доступ заблокирован. Обратитесь в поддержку.")
        return
    if user.status != "approved":
        await message.answer("❌ Для просмотра аукционов необходимо пройти регистрацию.")
        return

    auctions = await get_active_auctions(session)
    if not auctions:
        await message.answer("📭 В данный момент активных аукционов нет.")
        return

    # Fetch all auction IDs where this user already has a bid
    auction_ids = [a.id for a in auctions]
    bid_result = await session.execute(
        select(Bid.auction_id).where(
            Bid.user_id == user.id, Bid.auction_id.in_(auction_ids)
        )
    )
    bid_auction_ids = set(bid_result.scalars().all())

    now = datetime.now(tz=timezone.utc)
    for auction in auctions:
        delta = auction.end_time.replace(tzinfo=timezone.utc) - now
        hours = max(0, int(delta.total_seconds() // 3600))
        minutes = max(0, int((delta.total_seconds() % 3600) // 60))

        text = (
            f"🚗 *{auction.title}*\n\n"
            f"{auction.description}\n\n"
            f"💰 Минимальная ставка: *{float(auction.min_bid):,.0f} KZT*\n"
            f"⏰ Осталось: {hours}ч {minutes}м"
        )

        keyboard = (
            auction_update_keyboard(auction.id)
            if auction.id in bid_auction_ids
            else auction_keyboard(auction.id)
        )

        if auction.photos:
            if len(auction.photos) == 1:
                await message.answer_photo(
                    auction.photos[0].file_id,
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            else:
                media = [InputMediaPhoto(media=p.file_id) for p in auction.photos]
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
        await callback.answer("❌ Для участия необходимо пройти регистрацию.", show_alert=True)
        return
    if user.status == "revoked":
        await callback.answer("🚫 Ваш доступ заблокирован. Обратитесь в поддержку.", show_alert=True)
        return
    if user.status != "approved":
        await callback.answer("❌ Для участия в аукционе необходимо быть зарегистрированным участником.", show_alert=True)
        return

    result = await session.execute(
        select(Auction).where(Auction.id == callback_data.auction_id)
    )
    auction = result.scalar_one_or_none()

    if not auction or auction.status != "active":
        await callback.answer("❌ Этот аукцион уже завершён.", show_alert=True)
        return

    existing = await get_user_bid(session, callback_data.auction_id, user.id)

    await state.update_data(auction_id=callback_data.auction_id)
    await state.set_state(BidStates.waiting_amount)

    if existing:
        await callback.message.answer(
            f"✏️ Ваша текущая ставка: *{float(existing.amount):,.0f} KZT*\n"
            f"Минимальная ставка: *{float(auction.min_bid):,.0f} KZT*\n\n"
            f"Введите новую ставку (должна быть выше текущей):",
            parse_mode="Markdown",
        )
    else:
        await callback.message.answer(
            f"💰 Минимальная ставка: *{float(auction.min_bid):,.0f} KZT*\n\n"
            f"Введите сумму ставки:",
            parse_mode="Markdown",
        )

    await callback.answer()
