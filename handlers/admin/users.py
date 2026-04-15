import math

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from callbacks import PageCB, UserActionCB
from config import settings
from keyboards.admin import (
    PAGE_SIZE,
    pagination_keyboard,
    payment_confirmation_keyboard,
    revoke_keyboard,
    user_approval_keyboard,
)
from keyboards.participant import paid_keyboard, participant_main_keyboard
from permissions import can_manage_clients, can_revoke
from services.user_service import (
    count_users_by_status,
    get_users_by_status,
    update_user_status,
)

router = Router()


def _fmt_user(user) -> str:
    return (
        f"👤 *{user.full_name}*\n"
        f"📞 {user.phone}\n"
        f"🪪 ИИН: `{user.iin}`\n"
        f"🏦 Счёт: `{user.bank_account}`\n"
        f"🆔 Telegram: `{user.telegram_id}`"
    )


_USER_SECTIONS: dict[str, dict] = {
    "pending": {
        "status": "pending_review",
        "title": "👥 Заявки на регистрацию",
        "empty": "📭 Нет заявок на регистрацию.",
        "order": "created_desc",
        "keyboard": user_approval_keyboard,
    },
    "awaiting_pay": {
        "status": "approved_waiting_payment",
        "title": "💰 Ожидают оплаты",
        "empty": "📭 Нет пользователей, ожидающих оплаты.",
        "order": "created_desc",
        "keyboard": None,
    },
    "confirm_pay": {
        "status": "payment_pending_check",
        "title": "✔️ Подтверждение оплаты",
        "empty": "📭 Нет оплат для подтверждения.",
        "order": "created_desc",
        "keyboard": payment_confirmation_keyboard,
    },
    "approved": {
        "status": "approved",
        "title": "👤 Одобренные пользователи",
        "empty": "📭 Нет одобренных пользователей.",
        "order": "name_asc",
        "keyboard": revoke_keyboard,
    },
}


async def _send_user_page(
    message: Message, session: AsyncSession, section_key: str, page: int
) -> None:
    sec = _USER_SECTIONS[section_key]
    total = await count_users_by_status(session, sec["status"])
    if total == 0:
        await message.answer(sec["empty"])
        return

    total_pages = math.ceil(total / PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PAGE_SIZE

    users = await get_users_by_status(
        session, sec["status"], offset=offset, limit=PAGE_SIZE, order=sec["order"]
    )

    start_idx = offset + 1
    end_idx = offset + len(users)
    await message.answer(
        f"{sec['title']} ({start_idx}–{end_idx} из {total})",
        parse_mode="Markdown",
    )

    kb_factory = sec["keyboard"]
    for user in users:
        await message.answer(
            _fmt_user(user),
            parse_mode="Markdown",
            reply_markup=kb_factory(user.id) if kb_factory else None,
        )

    nav = pagination_keyboard(section_key, page, total_pages)
    if nav:
        await message.answer(f"Страница: {page}/{total_pages}", reply_markup=nav)


@router.message(F.text == "👥 Заявки на регистрацию")
async def show_pending_users(message: Message, session: AsyncSession) -> None:
    if not await can_manage_clients(session, message.from_user.id):
        return
    await _send_user_page(message, session, "pending", 1)


@router.message(F.text == "💰 Ожидают оплаты")
async def show_awaiting_payment(message: Message, session: AsyncSession) -> None:
    if not await can_manage_clients(session, message.from_user.id):
        return
    await _send_user_page(message, session, "awaiting_pay", 1)


@router.message(F.text == "✔️ Подтверждение оплаты")
async def show_payment_confirmations(message: Message, session: AsyncSession) -> None:
    if not await can_manage_clients(session, message.from_user.id):
        return
    await _send_user_page(message, session, "confirm_pay", 1)


@router.message(F.text == "👤 Одобренные пользователи")
async def show_approved_users(message: Message, session: AsyncSession) -> None:
    if not await can_manage_clients(session, message.from_user.id):
        return
    await _send_user_page(message, session, "approved", 1)


@router.callback_query(PageCB.filter(F.section.in_(_USER_SECTIONS.keys())))
async def paginate_users(
    callback: CallbackQuery, callback_data: PageCB, session: AsyncSession
) -> None:
    if not await can_manage_clients(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await _send_user_page(
        callback.message, session, callback_data.section, callback_data.page
    )


@router.message(F.text == "🚫 Заблокированные пользователи")
async def show_revoked_users(message: Message, session: AsyncSession) -> None:
    if not await can_revoke(session, message.from_user.id):
        return

    from keyboards.admin import restore_keyboard

    users = await get_users_by_status(session, "revoked")
    if not users:
        await message.answer("📭 Нет заблокированных пользователей.")
        return

    for user in users:
        await message.answer(
            _fmt_user(user),
            parse_mode="Markdown",
            reply_markup=restore_keyboard(user.id),
        )


@router.callback_query(UserActionCB.filter(F.action == "approve"))
async def approve_user(
    callback: CallbackQuery,
    callback_data: UserActionCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if not await can_manage_clients(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user = await update_user_status(
        session, callback_data.user_id, "approved_waiting_payment"
    )
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await callback.answer("✅ Пользователь одобрен!")
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *Одобрен — ожидает оплаты*",
        parse_mode="Markdown",
    )

    try:
        await bot.send_message(
            user.telegram_id,
            f"✅ Ваша заявка одобрена!\n\n"
            f"Пожалуйста, оплатите взнос:\n{settings.KASPI_ACCESS_FEE_LINK}\n\n"
            f"После оплаты нажмите кнопку ниже.",
            reply_markup=paid_keyboard(),
        )
    except Exception:
        pass


@router.callback_query(UserActionCB.filter(F.action == "reject"))
async def reject_user(
    callback: CallbackQuery,
    callback_data: UserActionCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if not await can_manage_clients(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user = await update_user_status(session, callback_data.user_id, "rejected")
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await callback.answer("❌ Пользователь отклонён!")
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ *Отклонён*",
        parse_mode="Markdown",
    )

    try:
        await bot.send_message(
            user.telegram_id,
            "❌ Ваша заявка отклонена. Обратитесь в поддержку.",
        )
    except Exception:
        pass


@router.callback_query(UserActionCB.filter(F.action == "revoke"))
async def revoke_user(
    callback: CallbackQuery,
    callback_data: UserActionCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if not await can_revoke(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user = await update_user_status(session, callback_data.user_id, "revoked")
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await callback.answer("🚫 Доступ заблокирован!")
    await callback.message.edit_text(
        callback.message.text + "\n\n🚫 *Доступ заблокирован*",
        parse_mode="Markdown",
    )

    try:
        await bot.send_message(
            user.telegram_id,
            "🚫 Ваш доступ к платформе заблокирован. Обратитесь в поддержку.",
        )
    except Exception:
        pass


@router.callback_query(UserActionCB.filter(F.action == "restore"))
async def restore_user(
    callback: CallbackQuery,
    callback_data: UserActionCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if not await can_revoke(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user = await update_user_status(session, callback_data.user_id, "approved")
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await callback.answer("✅ Доступ восстановлен!")
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *Доступ восстановлен*",
        parse_mode="Markdown",
    )

    try:
        await bot.send_message(
            user.telegram_id,
            "✅ Ваш доступ восстановлен. Вы можете снова участвовать в аукционах.",
            reply_markup=participant_main_keyboard(),
        )
    except Exception:
        pass


@router.callback_query(UserActionCB.filter(F.action == "confirm_payment"))
async def confirm_payment(
    callback: CallbackQuery,
    callback_data: UserActionCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if not await can_manage_clients(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user = await update_user_status(session, callback_data.user_id, "approved")
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await callback.answer("✅ Оплата подтверждена!")
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *Оплата подтверждена — доступ открыт*",
        parse_mode="Markdown",
    )

    try:
        await bot.send_message(
            user.telegram_id,
            "✅ Ваша оплата подтверждена! Вам открыт полный доступ к аукционам.",
            reply_markup=participant_main_keyboard(),
        )
    except Exception:
        pass
