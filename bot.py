BOT_TOKEN = "8682934608:AAF2UOPlVaUvep-NZowbgbS9k90NXcw0JzY"
ADMIN_ID = 784623145

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_booking

BOT_TOKEN = "8682934608:AAF2UOPlVaUvep-NZowbgbS9k90NXcw0JzY"  # сюда свой токен
ADMIN_ID = 784623145   # сюда свой ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- FSM ---
class BookingStates(StatesGroup):
    name = State()
    phone = State()
    date = State()
    time = State()
    hours = State()

# --- Старт ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()  # сброс предыдущих данных
    await message.answer(
        "Добро пожаловать!\nВведите ваше имя:"
    )
    await state.set_state(BookingStates.name)

# --- FSM хэндлеры ---
@dp.message(BookingStates.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ваш телефон:")
    await state.set_state(BookingStates.phone)

@dp.message(BookingStates.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Введите дату брони (например 20.04):")
    await state.set_state(BookingStates.date)

@dp.message(BookingStates.date)
async def process_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("Введите время брони (например 18:00):")
    await state.set_state(BookingStates.time)

@dp.message(BookingStates.time)
async def process_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Введите количество часов (например 3):")
    await state.set_state(BookingStates.hours)

@dp.message(BookingStates.hours)
async def process_hours(message: types.Message, state: FSMContext):
    try:
        hours = int(message.text)
        data = await state.get_data()
        name = data["name"]
        phone = data["phone"]
        date = data["date"]
        time = data["time"]

        booking_id = await add_booking(
            message.from_user.id, name, phone, date, time, hours
        )

        if booking_id:
            await message.answer("Бронь успешно создана!")
            await bot.send_message(
                ADMIN_ID,
                f"Новая бронь!\nID: {booking_id}\nИмя: {name}\nТелефон: {phone}\nДата: {date}\nВремя: {time}\nЧасы: {hours}"
            )
        else:
            # если пересечение есть, показываем кнопку
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Выбрать другую дату", callback_data="new_date")]
                ]
            )
            await message.answer("Время занято!", reply_markup=kb)

        await state.clear()
    except ValueError:
        await message.answer("Неправильный формат. Введите только число часов.")

# --- Callback кнопки ---
@dp.callback_query(lambda c: c.data == "new_date")
async def choose_new_date(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новую дату (например 21.04):")
    await state.set_state(BookingStates.date)
    await callback.answer()

# --- Main ---
async def main():
    await init_db()  # инициализация базы
    print("Бот запущен!")
    await dp.start_polling(bot)

asyncio.run(main())