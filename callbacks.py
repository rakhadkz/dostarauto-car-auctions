from aiogram.filters.callback_data import CallbackData


class UserActionCB(CallbackData, prefix="usr"):
    action: str  # approve | reject | confirm_payment
    user_id: int


class AuctionCB(CallbackData, prefix="auc"):
    action: str  # view | bid | update_bid | delete_bid | delete_bid_confirm | delete_bid_cancel | end_early | ...
    auction_id: int


class DonePhotosCB(CallbackData, prefix="done_ph"):
    pass


class StaffActionCB(CallbackData, prefix="stf"):
    action: str  # remove
    staff_id: int


class PageCB(CallbackData, prefix="pg"):
    section: str
    page: int
