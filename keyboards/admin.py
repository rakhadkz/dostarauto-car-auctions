from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from callbacks import AuctionCB, DonePhotosCB, PageCB, StaffActionCB, UserActionCB

PAGE_SIZE = 5

# ── Role-based main keyboards ─────────────────────────────────────────────────

_AUCTION_ROWS = [
    [KeyboardButton(text="📋 Создать аукцион")],
    [KeyboardButton(text="🟢 Активные аукционы")],
    [KeyboardButton(text="🏁 Завершённые аукционы")],
]

_COMMON_ROWS = _AUCTION_ROWS + [
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
    """Managers: auctions only (no user management)."""
    return ReplyKeyboardMarkup(
        keyboard=_AUCTION_ROWS,
        resize_keyboard=True,
    )


def staff_main_keyboard_for_role(role: str) -> ReplyKeyboardMarkup:
    if role == "superadmin":
        return superadmin_main_keyboard()
    if role == "admin":
        return admin_main_keyboard()
    return manager_main_keyboard()


AUCTION_CREATION_CANCEL_TEXT = "❌ Отменить создание"


def auction_creation_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=AUCTION_CREATION_CANCEL_TEXT)]],
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


def pagination_keyboard(
    section: str, page: int, total_pages: int
) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=PageCB(section=section, page=page - 1).pack(),
            )
        )
    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=PageCB(section=section, page=page + 1).pack(),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


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
