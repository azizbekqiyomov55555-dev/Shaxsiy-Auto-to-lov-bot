import logging
import requests
import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from flask import Flask, request

# 🔐 TOKEN (keyin almashtir!)
API_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"

MERCHANT_ID = "MTdiZDIzOTRkYjAzN2UyM2U0ZmE"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

app = Flask(__name__)

# 🧠 vaqtinchalik balans (RAM)
users_balance = {}

# 🔘 Tugmalar
menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add(KeyboardButton("💰 Balans"))

balans_menu = ReplyKeyboardMarkup(resize_keyboard=True)
balans_menu.add(KeyboardButton("➕ Hisobni to‘ldirish"))

# 🟢 START
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    if msg.from_user.id not in users_balance:
        users_balance[msg.from_user.id] = 0

    await msg.answer("Xush kelibsiz!", reply_markup=menu)

# 💰 BALANS
@dp.message_handler(lambda msg: msg.text == "💰 Balans")
async def balans(msg: types.Message):
    bal = users_balance.get(msg.from_user.id, 0)
    await msg.answer(f"Balansingiz: {bal} so‘m", reply_markup=balans_menu)

# 💳 TO‘LOV YARATISH
@dp.message_handler(lambda msg: msg.text == "➕ Hisobni to‘ldirish")
async def pay(msg: types.Message):
    amount = 1000

    url = "https://checkout.uz/api/v1/invoice"

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "merchant_id": MERCHANT_ID,
        "amount": amount,
        "account": {
            "user_id": str(msg.from_user.id)
        }
    }

    response = requests.post(url, json=data, headers=headers)

    print("STATUS:", response.status_code)
    print("FULL RESPONSE:", response.text)

    try:
        res = response.json()
    except:
        await msg.answer("❌ API xato (JSON emas)")
        return

    pay_url = res.get("data", {}).get("pay_url")

    if pay_url:
        await msg.answer(f"💳 To‘lov qilish:\n{pay_url}")
    else:
        await msg.answer("❌ To‘lov link kelmadi")

# 🔔 WEBHOOK (TO‘LOV KELGANI)
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("Webhook keldi:", data)

    status = data.get("status")
    account = data.get("account", {})
    user_id = account.get("user_id")

    if status in ["paid", "success"]:
        if user_id:
            user_id = int(user_id)

            # 💰 balans qo‘shish
            users_balance[user_id] = users_balance.get(user_id, 0) + 1000

            asyncio.run(bot.send_message(
                user_id,
                f"✅ To‘lov qabul qilindi!\n💰 +1000 so‘m qo‘shildi"
            ))

    return "OK"

# 🚀 RUN
if __name__ == '__main__':
    from threading import Thread

    def run_flask():
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)

    Thread(target=run_flask).start()
    executor.start_polling(dp)
