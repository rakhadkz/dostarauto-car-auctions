from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from callbacks import AuctionCB, DonePhotosCB, StaffActionCB, UserActionCB

# ── Role-based main keyboards ─────────────────────────────────────────────────

_COMMON_ROWS = [
    [KeyboardButton(text="📋 Создать аукцион")],
    [KeyboardButton(text="🟢 Активные аукционы")],
    [KeyboardButton(text="🏁 Завершённые аукционы")],
    [KeyboardButton(text="👥 Заявки на регистрацию")],
    [KeyboardButton(text="💰 Ожидают оплаты")],
    [KeyboardButton(text="✔️ Подтверждение оплаты")],
    [KeyboardButton(text="👤 Одобренные пользователи")],
]


def superadmin_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=_COMMON_ROWS
        + [
            [KeyboardButton(text="🚫 Заблокированные пользователи")],
            [KeyboardButton(text="👑 Управление персоналом")],
        ],
        resize_keyboard=True,
    )


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=_COMMON_ROWS
        + [
            [KeyboardButton(text="🚫 Заблокированные пользователи")],
        ],
        resize_keyboard=True,
    )


def manager_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=_COMMON_ROWS,
        resize_keyboard=True,
    )


def user_approval_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=UserActionCB(
                        action="approve", user_id=user_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=UserActionCB(action="reject", user_id=user_id).pack(),
                ),
            ]
        ]
    )


def payment_confirmation_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить оплату",
                    callback_data=UserActionCB(
                        action="confirm_payment", user_id=user_id
                    ).pack(),
                )
            ]
        ]
    )


def auction_view_keyboard(
    auction_id: int, *, active: bool = False
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="📊 Просмотр ставок",
                callback_data=AuctionCB(action="view", auction_id=auction_id).pack(),
            )
        ]
    ]
    if active:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⏱️ Завершить досрочно",
                    callback_data=AuctionCB(
                        action="end_early", auction_id=auction_id
                    ).pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def early_close_confirm_keyboard(auction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, завершить",
                    callback_data=AuctionCB(
                        action="end_early_confirm", auction_id=auction_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=AuctionCB(
                        action="end_early_cancel", auction_id=auction_id
                    ).pack(),
                ),
            ]
        ]
    )


def revoke_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚫 Заблокировать",
                    callback_data=UserActionCB(action="revoke", user_id=user_id).pack(),
                )
            ]
        ]
    )


def restore_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Восстановить доступ",
                    callback_data=UserActionCB(
                        action="restore", user_id=user_id
                    ).pack(),
                )
            ]
        ]
    )


def staff_remove_keyboard(staff_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=StaffActionCB(
                        action="remove", staff_id=staff_id
                    ).pack(),
                )
            ]
        ]
    )


def staff_management_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить администратора")],
            [KeyboardButton(text="➕ Добавить менеджера")],
            [KeyboardButton(text="👥 Список персонала")],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )


def done_photos_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Готово — опубликовать аукцион",
                    callback_data=DonePhotosCB().pack(),
                )
            ]
        ]
    )
