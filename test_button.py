import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8682934608:AAF2UOPlVaUvep-NZowbgbS9k90NXcw0JzY"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    button = InlineKeyboardButton(text="Нажми меня", callback_data="press_me")
    keyboard.add(button)
    await message.answer("Вот кнопка, нажми:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "press_me")
async def button_pressed(callback: types.CallbackQuery):
    await callback.message.answer("Кнопка сработала!")
    await callback.answer()  # убираем часики на кнопке

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())