from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_iin = State()
    waiting_bank_account = State()
