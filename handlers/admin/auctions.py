import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callbacks import AuctionCB, DonePhotosCB
from config import fmt_dt, settings
from permissions import is_any_staff
from keyboards.admin import (
    admin_main_keyboard,
    auction_view_keyboard,
    done_photos_keyboard,
    early_close_confirm_keyboard,
)
from models import Auction, Bid
from services.auction_close_service import finalize_auction_close
from services.auction_service import (
    create_auction,
    get_active_auctions,
    get_auction_with_bids,
    get_completed_auctions,
)
from services.notification_service import notify_auction_created
from scheduler.tasks import send_auction_reminders
from states.auction import AuctionCreationStates

logger = logging.getLogger(__name__)
router = Router()


# ── Auction creation FSM ────────────────────────────────────────────────────


@router.message(AuctionCreationStates.waiting_title)
async def process_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer(
            "❌ Название не может быть пустым. Введите название автомобиля:"
        )
        return
    await state.update_data(title=title)
    await state.set_state(AuctionCreationStates.waiting_description)
    await message.answer("Шаг 2/5: Введите *описание*:", parse_mode="Markdown")


@router.message(AuctionCreationStates.waiting_description)
async def process_description(message: Message, state: FSMContext) -> None:
    desc = message.text.strip() if message.text else ""
    if not desc:
        await message.answer("❌ Описание не может быть пустым. Попробуйте ещё раз:")
        return
    await state.update_data(description=desc)
    await state.set_state(AuctionCreationStates.waiting_min_bid)
    await message.answer(
        "Шаг 3/5: Введите *минимальную ставку* (тенге):", parse_mode="Markdown"
    )


@router.message(AuctionCreationStates.waiting_min_bid)
async def process_min_bid(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", "").replace(" ", "") if message.text else ""
    try:
        min_bid = float(raw)
        if min_bid <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Введите корректное положительное число (например: 500000):"
        )
        return

    await state.update_data(min_bid=min_bid)
    await state.set_state(AuctionCreationStates.waiting_duration)
    await message.answer(
        "Шаг 4/5: Введите *длительность аукциона в минутах* (например, 120 — это 2 часа):",
        parse_mode="Markdown",
    )


@router.message(AuctionCreationStates.waiting_duration)
async def process_duration(message: Message, state: FSMContext) -> None:
    raw = message.text.strip() if message.text else ""
    try:
        duration = int(raw)
        if duration <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное количество минут (например: 60):")
        return

    await state.update_data(duration=duration, photos=[])
    await state.set_state(AuctionCreationStates.waiting_photos)
    await message.answer(
        "Шаг 5/5: Отправьте фотографии автомобиля (до 10 штук).\n"
        "Когда закончите, нажмите кнопку или отправьте /done.",
        reply_markup=done_photos_keyboard(),
    )


@router.message(AuctionCreationStates.waiting_photos, F.photo)
async def process_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos: list[str] = data.get("photos", [])

    if len(photos) >= 10:
        await message.answer(
            "⚠️ Достигнут максимум 10 фото. Нажмите *Готово* для публикации.",
            parse_mode="Markdown",
        )
        return

    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)
    await message.answer(
        f"✅ Фото {len(photos)}/10 добавлено. Отправьте ещё или нажмите *Готово*.",
        parse_mode="Markdown",
        reply_markup=done_photos_keyboard(),
    )


@router.message(AuctionCreationStates.waiting_photos, Command("done"))
async def finish_via_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    scheduler: AsyncIOScheduler,
) -> None:
    await _finish_auction_creation(message, state, session, bot, scheduler)


@router.callback_query(DonePhotosCB.filter(), AuctionCreationStates.waiting_photos)
async def finish_via_button(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    scheduler: AsyncIOScheduler,
) -> None:
    await callback.answer()
    await _finish_auction_creation(callback.message, state, session, bot, scheduler)


async def _finish_auction_creation(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    scheduler: AsyncIOScheduler,
) -> None:
    data = await state.get_data()

    if not data.get("title"):
        await message.answer("❌ Данные аукциона утеряны. Начните заново с /cancel.")
        await state.clear()
        return

    auction = await create_auction(
        session=session,
        title=data["title"],
        description=data["description"],
        min_bid=data["min_bid"],
        duration_minutes=data["duration"],
        photo_file_ids=data.get("photos", []),
    )
    await state.clear()

    end_str = fmt_dt(auction.end_time)
    await message.answer(
        f"✅ *Аукцион создан!*\n\n"
        f"🚗 {auction.title}\n"
        f"💰 Мин. ставка: {float(auction.min_bid):,.0f} KZT\n"
        f"⏰ Завершается: {end_str}\n"
        f"📸 Фото: {len(data.get('photos', []))}",
        parse_mode="Markdown",
        reply_markup=admin_main_keyboard(),
    )

    # Reload with photos for notification
    result = await session.execute(
        select(Auction)
        .where(Auction.id == auction.id)
        .options(selectinload(Auction.photos))
    )
    auction_with_photos = result.scalar_one()

    await notify_auction_created(bot, session, auction_with_photos)
    await message.answer("📢 Уведомление отправлено всем одобренным участникам.")

    # Schedule halfway reminder
    reminder_time = auction.created_at + timedelta(minutes=data["duration"] / 2)
    if reminder_time.replace(tzinfo=timezone.utc) > datetime.now(tz=timezone.utc):
        scheduler.add_job(
            send_auction_reminders,
            trigger="date",
            run_date=reminder_time,
            kwargs={"bot": bot, "auction_id": auction.id},
        )
        logger.info(
            f"Reminder scheduled for auction {auction.id} at {reminder_time} UTC"
        )


# ── General auction management ───────────────────────────────────────────────


@router.message(F.text == "📋 Создать аукцион")
async def start_create_auction(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not await is_any_staff(session, message.from_user.id):
        return
    await state.set_state(AuctionCreationStates.waiting_title)
    await message.answer(
        "🚗 *Создание нового аукциона*\n\nШаг 1/5: Введите *название автомобиля*:",
        parse_mode="Markdown",
    )


@router.message(F.text == "🔴 Активные аукционы")
async def show_active_auctions(message: Message, session: AsyncSession) -> None:
    if not await is_any_staff(session, message.from_user.id):
        return

    auctions = await get_active_auctions(session)
    if not auctions:
        await message.answer("📭 Нет активных аукционов.")
        return

    now = datetime.now(tz=timezone.utc)
    for auction in auctions:
        delta = auction.end_time.replace(tzinfo=timezone.utc) - now
        hours = max(0, int(delta.total_seconds() // 3600))
        minutes = max(0, int((delta.total_seconds() % 3600) // 60))
        text = (
            f"🟢 *{auction.title}*\n"
            f"💰 Мин. ставка: {float(auction.min_bid):,.0f} KZT\n"
            f"⏰ Осталось: {hours}ч {minutes}м\n"
            f"📊 Ставок: {len(auction.bids)}"
        )
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=auction_view_keyboard(auction.id, active=True),
        )


@router.message(F.text == "✅ Завершённые аукционы")
async def show_completed_auctions(message: Message, session: AsyncSession) -> None:
    if not await is_any_staff(session, message.from_user.id):
        return

    auctions = await get_completed_auctions(session)
    if not auctions:
        await message.answer("📭 Нет завершённых аукционов.")
        return

    for auction in auctions:
        text = f"🏁 *{auction.title}*\n" f"📅 Завершён: {fmt_dt(auction.end_time)}"
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=auction_view_keyboard(auction.id),
        )


@router.callback_query(AuctionCB.filter(F.action == "view"))
async def view_auction_details(
    callback: CallbackQuery, callback_data: AuctionCB, session: AsyncSession
) -> None:
    if not await is_any_staff(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    auction = await get_auction_with_bids(session, callback_data.auction_id)
    if not auction:
        await callback.answer("Аукцион не найден.", show_alert=True)
        return

    status_label = "🟢 Активен" if auction.status == "active" else "🏁 Завершён"
    text = f"🚗 *{auction.title}*\nСтатус: {status_label}\n\n"

    if auction.bids:
        sorted_bids = sorted(auction.bids, key=lambda b: float(b.amount), reverse=True)
        text += "📊 *Все ставки (от высокой к низкой):*\n"
        for i, bid in enumerate(sorted_bids, 1):
            medal = (
                "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
            )
            text += f"{medal} {bid.user.full_name}: {float(bid.amount):,.0f} KZT\n"

        if auction.status == "active":
            leader = sorted_bids[0]
            text += f"\n🏆 *Лидер:* {leader.user.full_name} — {float(leader.amount):,.0f} KZT"
            leader_phone = (leader.user.phone or "").strip()
            text += f"\n📞 {leader_phone}" if leader_phone else "\n📞 —"
    else:
        text += "_Ставок пока нет._"

    if auction.status == "finished":
        if auction.winner:
            text += f"\n✅ *Победитель:* {auction.winner.full_name}"
            winner_phone = (auction.winner.phone or "").strip()
            text += f"\n📞 {winner_phone}" if winner_phone else "\n📞 —"
        else:
            text += "\n\n⚠️ Аукцион завершён без ставок."

    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(AuctionCB.filter(F.action == "end_early"))
async def prompt_end_auction_early(
    callback: CallbackQuery, callback_data: AuctionCB, session: AsyncSession
) -> None:
    if not await is_any_staff(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    auction = await get_auction_with_bids(session, callback_data.auction_id)
    if not auction:
        await callback.answer("Аукцион не найден.", show_alert=True)
        return
    if auction.status != "active":
        await callback.answer("Аукцион уже не активен.", show_alert=True)
        return

    await callback.message.answer(
        "⚠️ *Досрочное завершение*\n\n"
        f"🚗 {auction.title}\n\n"
        "Победитель будет выбран по текущей лидирующей ставке. "
        "Участники получат те же уведомления, что и при обычном завершении аукциона.\n\n"
        "Продолжить?",
        parse_mode="Markdown",
        reply_markup=early_close_confirm_keyboard(auction.id),
    )
    await callback.answer()


@router.callback_query(AuctionCB.filter(F.action == "end_early_cancel"))
async def cancel_end_auction_early(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    if not await is_any_staff(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Отменено")


@router.callback_query(AuctionCB.filter(F.action == "end_early_confirm"))
async def confirm_end_auction_early(
    callback: CallbackQuery,
    callback_data: AuctionCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if not await is_any_staff(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    auction = await get_auction_with_bids(session, callback_data.auction_id)
    if not auction:
        await callback.answer("Аукцион не найден.", show_alert=True)
        return
    if auction.status != "active":
        await callback.answer("Аукцион уже не активен.", show_alert=True)
        return

    chat_id = callback.message.chat.id
    try:
        await callback.message.delete()
    except Exception:
        pass

    await finalize_auction_close(session, bot, auction, mode="manual")
    await callback.answer("Готово")
