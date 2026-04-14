from aiogram.fsm.state import State, StatesGroup


class AuctionCreationStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_min_bid = State()
    waiting_bid_step = State()
    waiting_duration = State()
    waiting_photos = State()
