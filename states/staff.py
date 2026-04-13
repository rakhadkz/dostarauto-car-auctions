from aiogram.fsm.state import State, StatesGroup


class AddStaffStates(StatesGroup):
    waiting_telegram_id = State()
