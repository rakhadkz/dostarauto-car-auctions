from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from callbacks import AuctionCB


def participant_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Активные аукционы")],
            [KeyboardButton(text="📊 Мои ставки")],
        ],
        resize_keyboard=True,
    )


def paid_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💳 Я оплатил")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def auction_keyboard(auction_id: int) -> InlineKeyboardMarkup:
    """Shown before the user has placed a bid."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤝 Участвовать",
                    callback_data=AuctionCB(action="bid", auction_id=auction_id).pack(),
                ),
            ]
        ]
    )


def auction_update_keyboard(auction_id: int) -> InlineKeyboardMarkup:
    """Shown after the user has already placed a bid."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить ставку",
                    callback_data=AuctionCB(
                        action="update_bid", auction_id=auction_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить ставку",
                    callback_data=AuctionCB(
                        action="delete_bid", auction_id=auction_id
                    ).pack(),
                ),
            ]
        ]
    )


def delete_bid_confirm_keyboard(auction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=AuctionCB(
                        action="delete_bid_confirm", auction_id=auction_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=AuctionCB(
                        action="delete_bid_cancel", auction_id=auction_id
                    ).pack(),
                ),
            ]
        ]
    )
