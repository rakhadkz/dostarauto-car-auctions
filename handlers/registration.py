import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.admin import payment_confirmation_keyboard, user_approval_keyboard
from keyboards.participant import paid_keyboard
from services.notification_service import notify_admins
from services.user_service import get_user_by_telegram_id, update_user_status, create_user
from states.registration import RegistrationStates
from config import settings

router = Router()


@router.message(RegistrationStates.waiting_name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else ""
    if len(name) < 3:
        await message.answer("❌ Введите ваше ФИО (минимум 3 символа):")
        return

    await state.update_data(full_name=name)
    await state.set_state(RegistrationStates.waiting_phone)
    await message.answer("📞 Введите номер телефона (например: +7 777 123 45 67):")


@router.message(RegistrationStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip() if message.text else ""
    if not re.match(r"^\+?[\d\s\-\(\)]{10,16}$", phone):
        await message.answer("❌ Неверный формат номера телефона. Попробуйте ещё раз:")
        return

    await state.update_data(phone=phone)
    await state.set_state(RegistrationStates.waiting_iin)
    await message.answer("🪪 Введите ваш ИИН (12 цифр):")


@router.message(RegistrationStates.waiting_iin)
async def process_iin(message: Message, state: FSMContext) -> None:
    iin = message.text.strip() if message.text else ""
    if not re.match(r"^\d{12}$", iin):
        await message.answer("❌ ИИН должен содержать ровно 12 цифр. Попробуйте ещё раз:")
        return

    await state.update_data(iin=iin)
    await state.set_state(RegistrationStates.waiting_bank_account)
    await message.answer(
        "🏦 Введите номер банковского счёта (начинается с KZ, например: KZ123456789012345678):"
    )


@router.message(RegistrationStates.waiting_bank_account)
async def process_bank_account(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    bank_account = message.text.strip().upper() if message.text else ""
    if not re.match(r"^KZ\d{18}$", bank_account):
        await message.answer(
            "❌ Неверный номер счёта. Должен начинаться с KZ и содержать 18 цифр (20 символов всего).\n"
            "Пример: KZ123456789012345678\n\nПопробуйте ещё раз:"
        )
        return

    data = await state.get_data()
    user = await create_user(
        session=session,
        telegram_id=message.from_user.id,
        full_name=data["full_name"],
        phone=data["phone"],
        iin=data["iin"],
        bank_account=bank_account,
    )
    await state.clear()

    await message.answer(
        "✅ Заявка отправлена!\n\n"
        "Ваша анкета на рассмотрении. Вы получите уведомление после одобрения."
    )

    text = (
        f"📋 *Новая заявка на регистрацию*\n\n"
        f"ФИО: {user.full_name}\n"
        f"Телефон: {user.phone}\n"
        f"ИИН: {user.iin}\n"
        f"🏦 Счёт: `{user.bank_account}`\n"
        f"Telegram ID: `{user.telegram_id}`"
    )
    await notify_admins(
        bot,
        text,
        reply_markup=user_approval_keyboard(user.id),
        session=session,
        staff_filter="admins_only",
    )


@router.message(F.text == "💳 Я оплатил")
async def user_paid(message: Message, session: AsyncSession, bot: Bot) -> None:
    user = await get_user_by_telegram_id(session, message.from_user.id)

    if not user or user.status != "approved_waiting_payment":
        await message.answer(
            "❌ Ваш аккаунт не находится в статусе ожидания оплаты. Отправьте /start для проверки статуса."
        )
        return

    await update_user_status(session, user.id, "payment_pending_check")
    await message.answer(
        "⏳ Оплата отправлена на проверку. "
        "Мы уведомим вас после подтверждения."
    )

    text = (
        f"💰 *Оплата отправлена*\n\n"
        f"ФИО: {user.full_name}\n"
        f"Телефон: {user.phone}\n"
        f"ИИН: {user.iin}\n"
        f"Telegram ID: `{user.telegram_id}`"
    )
    await notify_admins(
        bot,
        text,
        reply_markup=payment_confirmation_keyboard(user.id),
        session=session,
        staff_filter="admins_only",
    )
