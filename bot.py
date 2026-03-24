import asyncio
import re
from datetime import datetime, timedelta
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
    guests = State()               # новое состояние

# ----- Функции валидации (остаются без изменений) -----
def validate_name(name: str) -> bool:
    if len(name) < 2:
        return False
    pattern = r'^[a-zA-Zа-яА-ЯёЁ\s\-]+$'
    return bool(re.match(pattern, name.strip()))

def validate_phone(phone: str) -> bool:
    digits = re.sub(r'\D', '', phone)
    if len(digits) != 11:
        return False
    if digits[0] not in ['7', '8']:
        return False
    return True

def format_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11:
        if digits[0] == '8':
            digits = '7' + digits[1:]
        return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return phone

def validate_date(date_str: str) -> bool:
    pattern = r'^\d{2}\.\d{2}$'
    if not re.match(pattern, date_str):
        return False
    try:
        day, month = map(int, date_str.split('.'))
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
        # Проверка на прошедшую дату (текущий год)
        current_date = datetime.now()
        current_year = current_date.year
        input_date = datetime(current_year, month, day)
        if input_date.date() < current_date.date():
            # Можно разрешить, но предупредить (будет предупреждение в process_date)
            pass
        return True
    except ValueError:
        return False

def validate_time(time_str: str) -> bool:
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
    try:
        hours = int(hours_str)
        if hours < 1 or hours > 12:
            return False
        return True
    except ValueError:
        return False

def validate_guests(guests_str: str) -> bool:
    """Проверка количества гостей (целое положительное число, не более 100)"""
    try:
        guests = int(guests_str)
        if guests < 1 or guests > 100:
            return False
        return True
    except ValueError:
        return False

# ----- Функция расчёта стоимости -----
def calculate_price(date_str: str, time_str: str, hours: int, guests: int) -> dict:
    """
    Рассчитывает стоимость аренды.
    Возвращает словарь:
        - hourly_cost: итоговая стоимость за часы
        - extra_guests_fee: доплата за гостей (>15)
        - cleaning_fee: стоимость уборки
        - total: общая сумма
        - details: список строк с почасовым разбором (для отображения)
    """
    # Определяем день недели по дате (используем текущий год)
    current_year = datetime.now().year
    day, month = map(int, date_str.split('.'))
    booking_date = datetime(current_year, month, day)
    weekday = booking_date.weekday()  # 0=пн, 6=вс

    # Определяем, будний (пн-чт) или выходной (пт-вс)
    is_weekend = weekday >= 4  # пт=4, сб=5, вс=6

    # Тарифы: для каждого часа (0-23) задаём цену
    # Структура: list из 24 элементов
    # Будни (пн-чт)
    weekday_rates = [5000] * 24  # ночная ставка 5000 (00:00-08:00)
    for h in range(8, 14):
        weekday_rates[h] = 1800   # 08:00-14:00
    for h in range(14, 24):
        weekday_rates[h] = 3500   # 14:00-00:00

    # Выходные (пт-вс)
    weekend_rates = [6000] * 24   # ночная ставка 6000 (00:00-08:00)
    for h in range(8, 14):
        weekend_rates[h] = 4000   # 08:00-14:00
    for h in range(14, 24):
        weekend_rates[h] = 5000   # 14:00-00:00

    rates = weekend_rates if is_weekend else weekday_rates

    # Преобразуем время начала в часы и минуты
    start_hour, start_minute = map(int, time_str.split(':'))
    start_time_min = start_hour * 60 + start_minute

    total_cost = 0
    details = []

    # Разбиваем по часам
    for i in range(hours):
        current_time_min = start_time_min + i * 60
        hour = (current_time_min // 60) % 24
        # Стоимость часа (полного) – если минуты не учитываем, считаем почасово
        # Для простоты считаем, что каждый час оплачивается полностью
        rate = rates[hour]
        total_cost += rate
        details.append(f"{hour:02d}:00 - {rate} руб/ч")

    # Доплата за гостей
    extra_guests_fee = 0
    if guests > 15:
        extra_guests_fee = (guests - 15) * 500

    # Уборка
    cleaning_fee = 2500 if guests <= 15 else 3000

    total = total_cost + extra_guests_fee + cleaning_fee

    return {
        "hourly_cost": total_cost,
        "extra_guests_fee": extra_guests_fee,
        "cleaning_fee": cleaning_fee,
        "total": total,
        "details": details
    }

# ----- Клавиатуры (без изменений) -----
def get_main_keyboard():
    buttons = [
        [KeyboardButton(text="📅 Забронировать")],
        [KeyboardButton(text="📋 Мои брони"), KeyboardButton(text="❓ Помощь")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

def get_date_keyboard():
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
        "* *",
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
        "*Тарифы:*\n"
        "ПН-ЧТ: 08-14 – 1800 руб/ч, 14-00 – 3500 руб/ч, 00-08 – 5000 руб/ч\n"
        "ПТ-ВС: 08-14 – 4000 руб/ч, 14-00 – 5000 руб/ч, 00-08 – 6000 руб/ч\n"
        "*Дополнительно:*\n"
        "• При более 15 гостей +500 руб/чел сверх 15\n"
        "• Уборка: 2500 руб (до 15 гостей) / 3000 руб (свыше 15)\n\n"
        "По всем вопросам: @aartspacen",
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
        "Введите ваш *телефон* (российский номер):\n",
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
            "(11 цифр, начинается с 7 или 8).\n\n"
            "Примеры: +7 999 123-45-67, 89991234567, +79991234567",
            parse_mode="Markdown"
        )
        return
    formatted_phone = format_phone(phone)
    await state.update_data(phone=formatted_phone)
    await message.answer(
        "Введите *дату* (например, 25.12):\n"
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
    # Проверка на прошедшую дату
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
        "Введите *время* начала вашей брони:\n",
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
        "Введите *количество часов*, на которое хотите забронировать лофт:\n",
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
    # Переходим к запросу количества гостей
    await message.answer(
        "Введите *количество гостей* (от 1 до 40):\n",
        parse_mode="Markdown"
    )
    await state.set_state(BookingState.guests)

@dp.message(BookingState.guests)
async def process_guests(message: types.Message, state: FSMContext):
    guests_str = message.text.strip()
    if not validate_guests(guests_str):
        await message.answer(
            "❌ *Некорректное количество гостей*\n"
            "Пожалуйста, введите число от 1 до 40.\n\n"
            "Введите количество гостей еще раз:",
            parse_mode="Markdown"
        )
        return
    guests = int(guests_str)
    await state.update_data(guests=guests)

    # Получаем все данные
    data = await state.get_data()
    # Рассчитываем стоимость
    price_info = calculate_price(data['date'], data['time'], data['hours'], guests)

    # Формируем детализированное сообщение
    details_text = "\n".join(price_info['details'][:5])  # покажем первые 5 часов, если много
    if len(price_info['details']) > 5:
        details_text += f"\n... и ещё {len(price_info['details']) - 5} часа(ов)"

    confirm_text = (
        f"📋 *Проверьте данные бронирования:*\n\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {data['time']}\n"
        f"⏱ Часов: {data['hours']}\n"
        f"👥 Гостей: {guests}\n\n"
        f"💰 *Расчёт стоимости:*\n"
        f"• Аренда: {price_info['hourly_cost']} руб\n"
        f"• Почасовая разбивка: \n {details_text})\n"
    )
    if price_info['extra_guests_fee'] > 0:
        confirm_text += f"• Доплата за гостей (>15): +{price_info['extra_guests_fee']} руб\n"
    confirm_text += (
        f"• Уборка: {price_info['cleaning_fee']} руб\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"*Итого: {price_info['total']} руб*\n\n"
        f"Всё верно?"
    )

    # Клавиатура подтверждения
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking")
            ]
        ]
    )

    await message.answer(
        confirm_text,
        parse_mode="Markdown",
        reply_markup=confirm_keyboard
    )
    # Сохраним рассчитанную стоимость в состоянии, чтобы не пересчитывать при подтверждении
    await state.update_data(price_info=price_info)

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
    price_info = data.get('price_info')
    if not price_info:
        # Если по какой-то причине нет price_info, пересчитаем
        price_info = calculate_price(data['date'], data['time'], data['hours'], data['guests'])

    # Проверка пересечения
    overlap = await check_overlap(data["date"], data["time"], data["hours"])
    if overlap:
        await callback.message.answer(
            "❌ *Извините, выбранное время занято*\n"
            "Пожалуйста, напишите сюда другую дату, далее вы сможете проверить другое время.",
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
        data["hours"],
        data["guests"],
        price_info['total'],
        price_info['cleaning_fee'],
        price_info['extra_guests_fee']
    )

    if booking_id:
        await callback.message.answer(
            f"✅ *Бронь успешно создана!*\n\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}\n"
            f"⏱ Часов: {data['hours']}\n"
            f"👥 Гостей: {data['guests']}\n"
            f"💰 *Стоимость:* {price_info['total']} руб\n\n"
            "Администратор уведомлён.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        # Уведомление админу
        admin_message = (
            f"🔔 *Новая бронь!*\n"
            f"ID: `{booking_id}`\n"
            f"👤 Имя: {data['name']}\n"
            f"📞 Телефон: {data['phone']}\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}\n"
            f"⏱ Часов: {data['hours']}\n"
            f"👥 Гостей: {data['guests']}\n"
            f"💰 Аренда: {price_info['hourly_cost']} руб\n"
            f"🧹 Уборка: {price_info['cleaning_fee']} руб\n"
        )
        if price_info['extra_guests_fee'] > 0:
            admin_message += f"➕ Доплата за гостей: {price_info['extra_guests_fee']} руб\n"
        admin_message += f"━━━━━━━━━━━━━━━━━━━\n*ИТОГО: {price_info['total']} руб*"
        await bot.send_message(ADMIN_ID, admin_message, parse_mode="Markdown")
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
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "❌ *Бронирование отменено*\n"
        "Вы можете начать заново с помощью кнопки 'Забронировать'.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    await state.clear()
    await callback.answer()

async def main():
    await init_db()
    print("🤖 Бот запущен! Отправьте /start в Telegram")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(close_db())