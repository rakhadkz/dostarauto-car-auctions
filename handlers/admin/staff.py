from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from callbacks import StaffActionCB
from keyboards.admin import (
    staff_management_keyboard,
    staff_remove_keyboard,
    superadmin_main_keyboard,
)
from permissions import can_manage_staff
from services.staff_service import add_staff, get_all_staff, remove_staff
from states.staff import AddStaffStates

router = Router()

_ROLE_LABELS = {"admin": "Администратор", "manager": "Менеджер"}


# ── Staff management menu ─────────────────────────────────────────────────────


@router.message(F.text == "👑 Управление персоналом")
async def staff_menu(message: Message, session: AsyncSession) -> None:
    if not await can_manage_staff(session, message.from_user.id):
        return
    await message.answer(
        "👑 Управление персоналом", reply_markup=staff_management_keyboard()
    )


@router.message(F.text == "◀️ Назад")
async def back_to_main(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    if not await can_manage_staff(session, message.from_user.id):
        return
    await state.clear()
    await message.answer("Главное меню", reply_markup=superadmin_main_keyboard())


# ── Add admin ─────────────────────────────────────────────────────────────────


@router.message(F.text == "➕ Добавить администратора")
async def start_add_admin(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    if not await can_manage_staff(session, message.from_user.id):
        return
    await state.update_data(role="admin")
    await state.set_state(AddStaffStates.waiting_telegram_id)
    await message.answer(
        "Введите Telegram ID нового *администратора*:",
        parse_mode="Markdown",
    )


# ── Add manager ───────────────────────────────────────────────────────────────


@router.message(F.text == "➕ Добавить менеджера")
async def start_add_manager(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    if not await can_manage_staff(session, message.from_user.id):
        return
    await state.update_data(role="manager")
    await state.set_state(AddStaffStates.waiting_telegram_id)
    await message.answer(
        "Введите Telegram ID нового *менеджера*:",
        parse_mode="Markdown",
    )


# ── FSM: process telegram ID input ───────────────────────────────────────────


@router.message(AddStaffStates.waiting_telegram_id)
async def process_staff_telegram_id(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    raw = message.text.strip() if message.text else ""
    try:
        new_telegram_id = int(raw)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите числовой Telegram ID:")
        return

    data = await state.get_data()
    role: str = data["role"]

    staff, is_new = await add_staff(
        session=session,
        telegram_id=new_telegram_id,
        role=role,
        added_by=message.from_user.id,
    )
    await state.clear()

    role_label = _ROLE_LABELS.get(role, role)
    if is_new:
        await message.answer(
            f"✅ *{role_label}* успешно добавлен.\nTelegram ID: `{new_telegram_id}`",
            parse_mode="Markdown",
            reply_markup=staff_management_keyboard(),
        )
    else:
        await message.answer(
            f"ℹ️ Пользователь уже в системе. Роль обновлена на *{role_label}*.",
            parse_mode="Markdown",
            reply_markup=staff_management_keyboard(),
        )

    try:
        await bot.send_message(
            new_telegram_id,
            f"✅ Вам назначена роль *{role_label}*. Отправьте /start для доступа к панели.",
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ── List staff ────────────────────────────────────────────────────────────────


@router.message(F.text == "👥 Список персонала")
async def list_staff(message: Message, session: AsyncSession) -> None:
    if not await can_manage_staff(session, message.from_user.id):
        return

    staff_list = await get_all_staff(session)
    if not staff_list:
        await message.answer("📭 Персонал не добавлен.")
        return

    for s in staff_list:
        role_label = _ROLE_LABELS.get(s.role, s.role)
        text = f"👤 *{role_label}*\n🆔 Telegram: `{s.telegram_id}`"
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=staff_remove_keyboard(s.id),
        )


# ── Remove staff ──────────────────────────────────────────────────────────────


@router.callback_query(StaffActionCB.filter(F.action == "remove"))
async def remove_staff_callback(
    callback: CallbackQuery,
    callback_data: StaffActionCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if not await can_manage_staff(session, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    staff = await remove_staff(session, callback_data.staff_id)
    if not staff:
        await callback.answer("Сотрудник не найден.", show_alert=True)
        return

    role_label = _ROLE_LABELS.get(staff.role, staff.role)
    await callback.answer(f"✅ {role_label} удалён!")
    await callback.message.edit_text(
        callback.message.text + f"\n\n🗑 *Удалён*",
        parse_mode="Markdown",
    )

    try:
        await bot.send_message(
            staff.telegram_id,
            "ℹ️ Ваша роль сотрудника была отозвана.",
        )
    except Exception:
        pass
