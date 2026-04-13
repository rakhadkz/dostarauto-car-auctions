from aiogram.fsm.state import State, StatesGroup


class BidStates(StatesGroup):
    waiting_amount = State()
