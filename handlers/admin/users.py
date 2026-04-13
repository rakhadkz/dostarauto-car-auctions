from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from callbacks import UserActionCB
from config import settings
from keyboards.participant import paid_keyboard, participant_main_keyboard
from permissions import can_revoke, is_any_staff
from services.user_service import get_users_by_status, update_user_status

router = Router()


def _fmt_user(user) -> str:
    return (
        f"👤 *{user.full_name}*\n"
        f"📞 {user.phone}\n"
        f"🪪 ИИН: `{user.iin}`\n"
        f"🏦 Счёт: `{user.bank_account}`\n"
        f"🆔 Telegram: `{user.telegram_id}`"
    )


@router.message(F.text == "👥 Заявки на регистрацию")
async def show_pending_users(message: Message, session: AsyncSession) -> None:
    if not await is_any_staff(session, message.from_user.id):
        return

    from keyboards.admin import user_approval_keyboard

    users = await get_users_by_status(session, "pending_review")
    if not users:
        await message.answer("📭 Нет заявок на регистрацию.")
        return

    for user in users:
        await message.answer(
            _fmt_user(user),
            parse_mode="Markdown",
            reply_markup=user_approval_keyboard(user.id),
        )


@router.message(F.text == "💰 Ожидают оплаты")
async def show_awaiting_payment(message: Message, session: AsyncSession) -> None:
    if not await is_any_staff(session, message.from_user.id):
        return

    users = await get_users_by_status(session, "approved_waiting_payment")
    if not users:
        await message.answer("📭 Нет пользователей, ожидающих оплаты.")
        return

    for user in users:
        await message.answer(_fmt_user(user), parse_mode="Markdown")


@router.message(F.text == "✔️ Подтверждение оплаты")
async def show_payment_confirmations(message: Message, session: AsyncSession) -> None:
    if not await is_any_staff(session, message.from_user.id):
        return

    from keyboards.admin import payment_confirmation_keyboard

    users = await get_users_by_status(session, "payment_pending_check")
    if not users:
        await message.answer("📭 Нет оплат для подтверждения.")
        return

    for user in users:
        await message.answer(
            _fmt_user(user),
            parse_mode="Markdown",
            reply_markup=payment_confirmation_keyboard(user.id),
        )


@router.message(F.text == "👤 Одобренные пользователи")
async def show_approved_users(message: Message, session: AsyncSession) -> None:
    if not await is_any_staff(session, message.from_user.id):
        return

    from keyboards.admin import revoke_keyboard

    users = await get_users_by_status(session, "approved")
    if not users:
        await message.answer("📭 Нет одобренных пользователей.")
        return

    for user in users:
        await message.answer(
            _fmt_user(user),
            parse_mode="Markdown",
            reply_markup=revoke_keyboard(user.id),
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
    callback: CallbackQuery, callback_data: UserActionCB, session: AsyncSession, bot: Bot
) -> None:
    if not await is_any_staff(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user = await update_user_status(session, callback_data.user_id, "approved_waiting_payment")
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
    callback: CallbackQuery, callback_data: UserActionCB, session: AsyncSession, bot: Bot
) -> None:
    if not await is_any_staff(session, callback.from_user.id):
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
    callback: CallbackQuery, callback_data: UserActionCB, session: AsyncSession, bot: Bot
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
    callback: CallbackQuery, callback_data: UserActionCB, session: AsyncSession, bot: Bot
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
    callback: CallbackQuery, callback_data: UserActionCB, session: AsyncSession, bot: Bot
) -> None:
    if not await is_any_staff(session, callback.from_user.id):
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
