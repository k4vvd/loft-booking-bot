import asyncio
import re
from datetime import datetime
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

# ----- Функции валидации -----
def validate_name(name: str) -> bool:
    """Проверка имени: минимум 2 символа, только буквы, пробелы и дефисы"""
    if len(name) < 2:
        return False
    pattern = r'^[a-zA-Zа-яА-ЯёЁ\s\-]+$'
    return bool(re.match(pattern, name.strip()))

def validate_phone(phone: str) -> bool:
    """Проверка российского номера телефона"""
    digits = re.sub(r'\D', '', phone)
    if len(digits) != 11:
        return False
    if digits[0] not in ['7', '8']:
        return False
    return True

def format_phone(phone: str) -> str:
    """Форматирует телефон для красивого отображения"""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11:
        if digits[0] == '8':
            digits = '7' + digits[1:]
        return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return phone

def validate_date(date_str: str) -> bool:
    """Проверка формата даты (DD.MM)"""
    pattern = r'^\d{2}\.\d{2}$'
    if not re.match(pattern, date_str):
        return False
    try:
        day, month = map(int, date_str.split('.'))
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
        # Проверка, что дата не в прошлом (необязательно строго)
        current_date = datetime.now()
        current_year = current_date.year
        input_date = datetime(current_year, month, day)
        if input_date.date() < current_date.date():
            # Можно разрешить, но предупредить
            pass
        return True
    except ValueError:
        return False

def validate_time(time_str: str) -> bool:
    """Проверка формата времени (HH:MM)"""
    pattern = r'^\d{2}:\d{2}$'
    if not re.match(pattern, time_str):
        return False
    try:
        hours, minutes = map(int, time_str.split(':'))
        if hours < 0 or hours > 23:
            return False
        if minutes < 0 or minutes > 59:
            return False
        return True
    except ValueError:
        return False

def validate_hours(hours_str: str) -> bool:
    """Проверка количества часов"""
    try:
        hours = int(hours_str)
        if hours < 1 or hours > 12:
            return False
        return True
    except ValueError:
        return False

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
    await message.answer(
        "Введите ваше имя:\n"
        "*(минимум 2 символа, только буквы, пробелы и дефисы)*",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(BookingState.name)

@dp.message(lambda message: message.text == "📋 Мои брони")
async def my_bookings(message: types.Message):
    await message.answer("Здесь будут ваши бронирования.")

@dp.message(lambda message: message.text == "❓ Помощь")
async def help_message(message: types.Message):
    await message.answer(
        "📖 *Помощь по боту*\n\n"
        "📅 *Забронировать* - создать новую бронь\n"
        "📋 *Мои брони* - просмотр ваших броней\n\n"
        "*Правила ввода:*\n"
        "• Имя: только буквы, от 2 символов\n"
        "• Телефон: российский номер (11 цифр)\n"
        "• Дата: формат ДД.ММ (например, 25.12)\n"
        "• Время: формат ЧЧ:ММ (например, 18:00)\n"
        "• Часы: число от 1 до 12\n\n"
        "По всем вопросам: @administrator",
        parse_mode="Markdown"
    )

# ----- Процесс бронирования -----
@dp.message(BookingState.name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not validate_name(name):
        await message.answer(
            "❌ *Некорректное имя*\n"
            "Имя должно содержать только буквы, пробелы и дефисы, "
            "минимум 2 символа.\n\n"
            "Пожалуйста, введите имя еще раз:",
            parse_mode="Markdown"
        )
        return
    await state.update_data(name=name)
    await message.answer(
        "Введите ваш *телефон*\n",
        parse_mode="Markdown"
    )
    await state.set_state(BookingState.phone)

@dp.message(BookingState.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not validate_phone(phone):
        await message.answer(
            "❌ *Некорректный номер телефона*\n"
            "Пожалуйста, введите российский номер телефона "
            "Примеры: +7 999 123-45-67, 89991234567, +79991234567",
            parse_mode="Markdown"
        )
        return
    formatted_phone = format_phone(phone)
    await state.update_data(phone=formatted_phone)
    await message.answer(
        "Введите *дату*\n"
        "Формат: ДД.ММ",
        parse_mode="Markdown"
    )
    await state.set_state(BookingState.date)

@dp.message(BookingState.date)
async def process_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    if not validate_date(date_str):
        await message.answer(
            "❌ *Некорректная дата*\n"
            "Пожалуйста, введите дату в формате ДД.ММ\n"
            "Пример: 25.12 (25 декабря)\n\n"
            "Введите дату еще раз:",
            parse_mode="Markdown"
        )
        return
    # Необязательная проверка на прошлую дату
    current_date = datetime.now()
    current_year = current_date.year
    day, month = map(int, date_str.split('.'))
    input_date = datetime(current_year, month, day)
    if input_date.date() < current_date.date():
        await message.answer(
            "⚠️ *Внимание!*\n"
            f"Дата {date_str} уже прошла в этом году.\n"
            "Если вы хотите забронировать на следующий год, "
            "пожалуйста, укажите год (например, 25.12.2025)\n\n"
            "Или введите другую дату:",
            parse_mode="Markdown"
        )
        return
    await state.update_data(date=date_str)
    await message.answer(
        "Введите *время* начала вашего бронирования:\n",
        parse_mode="Markdown"
    )
    await state.set_state(BookingState.time)

@dp.message(BookingState.time)
async def process_time(message: types.Message, state: FSMContext):
    time_str = message.text.strip()
    if not validate_time(time_str):
        await message.answer(
            "❌ *Некорректное время*\n"
            "Пожалуйста, введите время в формате ЧЧ:ММ\n"
            "Примеры: 18:00, 09:30, 14:15\n\n"
            "Введите время еще раз:",
            parse_mode="Markdown"
        )
        return
    await state.update_data(time=time_str)
    await message.answer(
        "Введите *количество часов* на которое хотите забронировать лофт:\n"
        "Только число",
        parse_mode="Markdown"
    )
    await state.set_state(BookingState.hours)

@dp.message(BookingState.hours)
async def process_hours(message: types.Message, state: FSMContext):
    hours_str = message.text.strip()
    if not validate_hours(hours_str):
        await message.answer(
            "❌ *Некорректное количество часов*\n"
            "Пожалуйста, введите число от 1 до 12.\n\n"
            "Введите количество часов еще раз:",
            parse_mode="Markdown"
        )
        return
    hours = int(hours_str)
    await state.update_data(hours=hours)
    data = await state.get_data()

    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking")
            ]
        ]
    )

    await message.answer(
        f"📋 *Проверьте данные бронирования:*\n\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {data['time']}\n"
        f"⏱ Часов: {hours}\n\n"
        f"Всё верно?",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard
    )

# ----- Обработчики инлайн-кнопок -----
@dp.callback_query(lambda c: c.data == "choose_date")
async def choose_date_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введите новую *дату* (например, 20.04):",
        parse_mode="Markdown"
    )
    await state.set_state(BookingState.date)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_booking")
async def confirm_booking_callback(callback: types.CallbackQuery, state: FSMContext):
    # Убираем кнопки из сообщения
    await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()

    # Проверка пересечения
    overlap = await check_overlap(data["date"], data["time"], data["hours"])
    if overlap:
        await callback.message.answer(
            "❌ *Извините, выбранное время занято*\n"
            "Пожалуйста, выберите другую дату или время.",
            parse_mode="Markdown"
        )
        await state.set_state(BookingState.date)
        await callback.answer()
        return

    # Сохраняем бронь
    booking_id = await add_booking(
        callback.from_user.id,
        data["name"],
        data["phone"],
        data["date"],
        data["time"],
        data["hours"]
    )

    if booking_id:
        await callback.message.answer(
            "✅ *Бронь успешно создана!*\n\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}\n"
            f"⏱ Часов: {data['hours']}\n\n"
            "Администратор уведомлён.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        await bot.send_message(
            ADMIN_ID,
            f"🔔 *Новая бронь!*\n"
            f"ID: {booking_id}\n"
            f"👤 Имя: {data['name']}\n"
            f"📞 Телефон: {data['phone']}\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}\n"
            f"⏱ Часов: {data['hours']}",
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer(
            "❌ *Ошибка при создании брони*\n"
            "Пожалуйста, попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

    await state.clear()
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_booking")
async def cancel_booking_callback(callback: types.CallbackQuery, state: FSMContext):
    # Убираем кнопки из сообщения
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(
        "❌ *Бронирование отменено*\n"
        "Вы можете начать заново с помощью кнопки 'Забронировать'.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    await state.clear()
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