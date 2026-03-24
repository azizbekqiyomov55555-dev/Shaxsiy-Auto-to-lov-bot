import requests
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from flask import Flask, request

# 🔑 TOKEN
API_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"

# 🔥 CHECKOUT
MERCHANT_ID = "MTdiZDIzOTRkYjAzN2UyM2U0ZmE"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
app = Flask(__name__)

# 🔘 MENU
menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add(KeyboardButton("💰 Balans"))

balans_menu = ReplyKeyboardMarkup(resize_keyboard=True)
balans_menu.add(KeyboardButton("➕ Hisobni to‘ldirish"))

# 🟢 START
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("Xush kelibsiz!", reply_markup=menu)

# 💰 BALANS
@dp.message_handler(lambda msg: msg.text == "💰 Balans")
async def balans(msg: types.Message):
    await msg.answer("Balansingiz: 0 so‘m", reply_markup=balans_menu)

# 💳 TO‘LOV LINK
@dp.message_handler(lambda msg: msg.text == "➕ Hisobni to‘ldirish")
async def pay(msg: types.Message):
    amount = 1000

    url = "https://checkout.uz/api/create-invoice"

    data = {
        "merchant_id": MERCHANT_ID,
        "amount": amount,
        "account": {
            "user_id": msg.from_user.id
        }
    }

    try:
        response = requests.post(url, json=data)
        print("RAW:", response.text)

        res = response.json()

        pay_url = res.get("pay_url")

        if pay_url:
            await msg.answer(f"💳 To‘lov qilish:\n{pay_url}")
        else:
            await msg.answer(f"❌ Link kelmadi:\n{res}")

    except Exception as e:
        print("XATOLIK:", e)
        await msg.answer("❌ Xatolik yuz berdi")

# 🔔 WEBHOOK
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("Webhook:", data)

    status = data.get("status")
    user_id = data.get("account", {}).get("user_id")

    if status in ["paid", "success"]:
        if user_id:
            asyncio.run(bot.send_message(user_id, "✅ To‘lov qabul qilindi!"))

    return "OK"

# 🚀 RUN
if __name__ == '__main__':
    from threading import Thread

    def run_flask():
        app.run(host="0.0.0.0", port=5000)

    Thread(target=run_flask).start()
    executor.start_polling(dp)
