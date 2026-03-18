import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command

from database import init_db, add_booking, check_overlap, close_db

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

# ----- Клавиатуры -----
def get_main_keyboard():
    """Главное меню (reply-кнопки)"""
    buttons = [
        [KeyboardButton(text="📅 Забронировать")],
        [KeyboardButton(text="📋 Мои брони"), KeyboardButton(text="❓ Помощь")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

def get_date_keyboard():
    """Инлайн-кнопка для выбора другой даты"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Выбрать другую дату", callback_data="choose_date")]
        ]
    )
    return keyboard

# ----- Старт и основное меню -----
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Добро пожаловать! Выберите действие:",
        reply_markup=get_main_keyboard()
    )

@dp.message(lambda message: message.text == "📅 Забронировать")
async def start_booking(message: types.Message, state: FSMContext):
    await message.answer("Введите ваше имя:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(BookingState.name)

@dp.message(lambda message: message.text == "📋 Мои брони")
async def my_bookings(message: types.Message):
    # Здесь можно реализовать вывод броней пользователя из БД
    await message.answer("Здесь будут ваши бронирования.")

@dp.message(lambda message: message.text == "❓ Помощь")
async def help_message(message: types.Message):
    await message.answer(
        "Этот бот помогает бронировать лофт.\n"
        "Используйте /start для главного меню.\n"
        "По всем вопросам обращайтесь к администратору."
    )

# ----- Процесс бронирования -----
@dp.message(BookingState.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите телефон:")
    await state.set_state(BookingState.phone)

@dp.message(BookingState.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer("Введите дату (например, 20.04):")
    await state.set_state(BookingState.date)

@dp.message(BookingState.date)
async def process_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text.strip())
    await message.answer("Введите время (например, 18:00):")
    await state.set_state(BookingState.time)

@dp.message(BookingState.time)
async def process_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text.strip())
    await message.answer("Введите количество часов (только число):")
    await state.set_state(BookingState.hours)

@dp.message(BookingState.hours)
async def process_hours(message: types.Message, state: FSMContext):
    try:
        hours = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неправильный формат. Введите число часов (например: 3).")
        return

    await state.update_data(hours=hours)
    data = await state.get_data()

    overlap = await check_overlap(data["date"], data["time"], hours)
    if overlap:
        await state.set_state(BookingState.date)
        await message.answer(
            "❌ Извините, выбранное время занято.\n"
            "Нажмите кнопку ниже, чтобы выбрать другую дату:",
            reply_markup=get_date_keyboard()
        )
        return

    booking_id = await add_booking(
        message.from_user.id,
        data["name"],
        data["phone"],
        data["date"],
        data["time"],
        hours
    )

    if booking_id:
        await message.answer(
            "✅ Бронь успешно создана!\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}\n"
            f"⏱ Часов: {hours}\n\n"
            "Администратор уведомлён.",
            reply_markup=get_main_keyboard()
        )
        await bot.send_message(
            ADMIN_ID,
            f"🔔 **Новая бронь!**\n"
            f"ID: {booking_id}\n"
            f"👤 Имя: {data['name']}\n"
            f"📞 Телефон: {data['phone']}\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}\n"
            f"⏱ Часов: {hours}",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Ошибка при создании брони. Попробуйте позже.",
                             reply_markup=get_main_keyboard())
    await state.clear()

# ----- Обработчик инлайн-кнопки -----
@dp.callback_query(lambda c: c.data == "choose_date")
async def choose_date_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новую дату (например, 20.04):")
    await state.set_state(BookingState.date)
    await callback.answer()

# ----- Запуск -----
async def main():
    await init_db()
    print("🤖 Бот запущен! Отправьте /start в Telegram")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(close_db())