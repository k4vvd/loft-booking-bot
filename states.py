from aiogram.fsm.state import StatesGroup, State

class BookingState(StatesGroup):
    name = State()
    phone = State()
    date = State()
    time = State()
    hours = State()