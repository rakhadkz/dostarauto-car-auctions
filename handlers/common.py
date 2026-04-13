from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from keyboards.admin import admin_main_keyboard, manager_main_keyboard, superadmin_main_keyboard
from keyboards.participant import paid_keyboard, participant_main_keyboard
from permissions import get_role
from services.user_service import get_user_by_telegram_id
from states.registration import RegistrationStates

router = Router()

_ROLE_GREETINGS = {
    "superadmin": ("👑 Добро пожаловать, Суперадминистратор!", superadmin_main_keyboard),
    "admin": ("👋 Добро пожаловать, Администратор!", admin_main_keyboard),
    "manager": ("👋 Добро пожаловать, Менеджер!", manager_main_keyboard),
}


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()

    role = await get_role(session, message.from_user.id)
    if role in _ROLE_GREETINGS:
        greeting, keyboard_fn = _ROLE_GREETINGS[role]
        await message.answer(greeting, reply_markup=keyboard_fn())
        return

    user = await get_user_by_telegram_id(session, message.from_user.id)

    if user is None:
        await state.set_state(RegistrationStates.waiting_name)
        await message.answer(
            "👋 Добро пожаловать в бот автомобильных аукционов!\n\n"
            "Для участия в аукционах необходимо пройти регистрацию.\n\n"
            "Введите ваше *ФИО*:",
            parse_mode="Markdown",
        )
        return

    match user.status:
        case "pending_review":
            await message.answer(
                "⏳ Ваша заявка на рассмотрении. Ожидайте одобрения администратора."
            )
        case "approved_waiting_payment":
            await message.answer(
                f"✅ Ваша заявка одобрена!\n\n"
                f"Пожалуйста, оплатите взнос:\n{settings.KASPI_ACCESS_FEE_LINK}\n\n"
                f"После оплаты нажмите кнопку ниже.",
                reply_markup=paid_keyboard(),
            )
        case "payment_pending_check":
            await message.answer("⏳ Ваша оплата проверяется. Пожалуйста, ожидайте.")
        case "approved":
            await message.answer(
                "✅ Добро пожаловать! У вас есть доступ ко всем аукционам.",
                reply_markup=participant_main_keyboard(),
            )
        case "rejected":
            await message.answer(
                "❌ Ваша заявка отклонена. Обратитесь в поддержку."
            )
        case "revoked":
            await message.answer(
                "🚫 Ваш доступ заблокирован. Обратитесь в поддержку."
            )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("❌ Действие отменено. Отправьте /start для продолжения.")
    else:
        await message.answer("Нечего отменять.")
