import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import init_db, add_booking

from database import init_db, add_booking, check_overlap

BOT_TOKEN = "8682934608:AAF2UOPlVaUvep-NZowbgbS9k90NXcw0JzY"
ADMIN_ID = 784623145

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM состояния
class BookingState(StatesGroup):
    name = State()
    phone = State()
    date = State()
    time = State()
    hours = State()

# /start
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Добро пожаловать! Введите ваше имя:")
    await state.set_state(BookingState.name)

# имя
@dp.message(BookingState.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите телефон:")
    await state.set_state(BookingState.phone)

# телефон
@dp.message(BookingState.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer("Введите дату (например, 20.04):")
    await state.set_state(BookingState.date)

# дата
@dp.message(BookingState.date)
async def process_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text.strip())
    await message.answer("Введите время (например, 18:00):")
    await state.set_state(BookingState.time)

# время
@dp.message(BookingState.time)
async def process_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text.strip())
    await message.answer("Введите количество часов (только число):")
    await state.set_state(BookingState.hours)

# часы
@dp.message(BookingState.hours)
async def process_hours(message: types.Message, state: FSMContext):
    # проверка числа
    try:
        hours = int(message.text.strip())
    except:
        await message.answer("Неправильный формат. Введите число часов (например: 3).")
        return

    await state.update_data(hours=hours)
    data = await state.get_data()

    # проверка пересечения
    overlap = await check_overlap(data["date"], data["time"], hours)
    if overlap:
        # переводим FSM в состояние выбора другой даты
        await state.set_state(BookingState.date)

        # кнопка
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Выбрать другую дату", callback_data="choose_date"))

        await message.answer(
            "Извините, выбранное время занято.",
            reply_markup=keyboard
        )
        return

    # добавление брони
    booking_id = await add_booking(
        message.from_user.id,
        data["name"],
        data["phone"],
        data["date"],
        data["time"],
        hours
    )

    await message.answer("Бронь создана! Администратор уведомлён.")
    await bot.send_message(
        ADMIN_ID,
        f"Новая бронь!\nID: {booking_id}\nИмя: {data['name']}\nТелефон: {data['phone']}\nДата: {data['date']}\nВремя: {data['time']}\nЧасы: {hours}"
    )
    await state.clear()

# обработчик кнопки
@dp.callback_query(lambda c: c.data == "choose_date")
async def choose_date_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новую дату (например, 20.04):")
    await state.set_state(BookingState.date)
    await callback.answer()  # убираем часики на кнопке

# запуск
async def main():
    await init_db()
    print("Бот запущен! Отправьте /start в Telegram")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())