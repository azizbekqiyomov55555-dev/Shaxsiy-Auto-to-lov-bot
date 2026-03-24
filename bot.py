import requests
import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from flask import Flask, request

API_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
MERCHANT_ID = "MTdiZDIzOTRkYjAzN2UyM2U0ZmE"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

app = Flask(__name__)

# tugmalar
menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add(KeyboardButton("💰 Balans"))

balans_menu = ReplyKeyboardMarkup(resize_keyboard=True)
balans_menu.add(KeyboardButton("➕ Hisobni to‘ldirish"))

# start
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("Xush kelibsiz!", reply_markup=menu)

# balans
@dp.message_handler(lambda msg: msg.text == "💰 Balans")
async def balans(msg: types.Message):
    await msg.answer("Balans: 0 so‘m", reply_markup=balans_menu)

# tolov
@dp.message_handler(lambda msg: msg.text == "➕ Hisobni to‘ldirish")
async def pay(msg: types.Message):
    url = "https://checkout.uz/api/v1/invoice"

    data = {
        "merchant_id": MERCHANT_ID,
        "amount": 1000,
        "account": {
            "user_id": str(msg.from_user.id)
        }
    }

    try:
        r = requests.post(url, json=data)
        print("RESP:", r.text)

        res = r.json()

        pay_url = res["data"]["pay_url"]

        await msg.answer(f"💳 To‘lov qilish:\n{pay_url}")

    except Exception as e:
        print("XATO:", e)
        await msg.answer("❌ To‘lov link kelmadi")

# webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("WEBHOOK:", data)

    status = data.get("status")
    user_id = data.get("account", {}).get("user_id")

    if status in ["paid", "success"]:
        if user_id:
            asyncio.run(bot.send_message(int(user_id), "✅ To‘lov qabul qilindi!"))

    return "OK"

# run
if __name__ == "__main__":
    from threading import Thread

    def run_flask():
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)

    Thread(target=run_flask).start()
    executor.start_polling(dp)
