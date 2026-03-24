import logging
import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

# 🔐 TOKEN (o‘zingnikini qo‘y)
API_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"

# 🔥 Checkout ma’lumotlari
MERCHANT_ID = "MTdiZDIzOTRkYjAzN2UyM2U0ZmE"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 🔘 Tugmalar
menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add(KeyboardButton("💰 Balans"))

balans_menu = ReplyKeyboardMarkup(resize_keyboard=True)
balans_menu.add(KeyboardButton("➕ Hisobni to‘ldirish"))

# 🟢 START
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("Xush kelibsiz!", reply_markup=menu)

# 💰 Balans
@dp.message_handler(lambda msg: msg.text == "💰 Balans")
async def balans(msg: types.Message):
    await msg.answer("Balansingiz: 0 so‘m", reply_markup=balans_menu)

# 💳 TO‘LOV LINK
@dp.message_handler(lambda msg: msg.text == "➕ Hisobni to‘ldirish")
async def pay(msg: types.Message):
    amount = 1000  # 🔥 summa

    # 🔥 TO‘G‘RI LINK
    pay_url = f"https://checkout.uz/pay?merchant_id={MERCHANT_ID}&amount={amount}&account[user_id]={msg.from_user.id}"

    await msg.answer(f"💳 To‘lov qilish uchun link:\n{pay_url}")

# 🚀 RUN
if __name__ == '__main__':
    executor.start_polling(dp)
