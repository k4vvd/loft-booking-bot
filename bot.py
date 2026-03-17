import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import init_db, add_booking, check_overlap

BOT_TOKEN = "8682934608:AAF2UOPlVaUvep-NZowbgbS9k90NXcw0JzY"
ADMIN_ID = 784623145

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# FSM для ввода брони
class BookingStates(StatesGroup):
    waiting_input = State()


# Кнопка выбора другой даты
def other_date_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Выбрать другую дату", callback_data="other_date"))
    return kb


@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.set_state(BookingStates.waiting_input)
    await message.answer(
        "Добро пожаловать!\n\n"
        "Напишите бронь в формате:\n"
        "Имя, телефон, дата, время, часы\n\n"
        "Пример: Иван, 89991234567, 20.04, 18:00, 3"
    )


@dp.message(BookingStates.waiting_input)
async def booking(message: types.Message, state: FSMContext):
    data = message.text.split(",")
    if len(data) != 5:
        await message.answer("Ошибка формата. Попробуйте снова.")
        return

    try:
        name = data[0].strip()
        phone = data[1].strip()
        date = data[2].strip()
        time = data[3].strip()
        hours = int(data[4].strip())
    except ValueError:
        await message.answer("Количество часов должно быть числом. Попробуйте снова.")
        return

    # Проверка пересечения
    if await check_overlap(date, time, hours):
        await message.answer(
            "На эту дату/время лофт занят!",
            reply_markup=other_date_keyboard()
        )
        return

    # Добавление брони
    booking_id = await add_booking(message.from_user.id, name, phone, date, time, hours)
    if booking_id is None:
        await message.answer(
            "На эту дату/время лофт занят!",
            reply_markup=other_date_keyboard()
        )
        return

    await message.answer("Бронь принята! Администратор уведомлён.")
    await bot.send_message(
        ADMIN_ID,
        f"Новая бронь!\n\n"
        f"ID: {booking_id}\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Дата: {date}\n"
        f"Время: {time}\n"
        f"Часы: {hours}"
    )


@dp.callback_query(lambda c: c.data == "other_date")
async def choose_other_date(callback: types.CallbackQuery):
    await callback.message.answer("Введите новую дату и время брони в том же формате:\nДата, время, часы")


async def main():
    await init_db()
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())