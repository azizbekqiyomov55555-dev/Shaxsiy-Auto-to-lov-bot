import logging
import hashlib
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import os

# --- KONFIGURATSIYA ---
API_TOKEN = '8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc'
KASSA_ID = "46"
SECRET_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM" # Dashboarddagi API Secret Key

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- API ORQALI PROFESSIONAL TO'LOV LINKINI OLISH ---
async def get_checkout_url(amount, order_id):
    url = "https://api.checkout.uz/api/v1/payment/create"
    headers = {
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": amount,
        "order_id": order_id,
        "kassa_id": int(KASSA_ID)
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                if result.get("status") == True:
                    return result.get("payment_url")
                else:
                    logging.error(f"API Xatosi: {result}")
                    return None
        except Exception as e:
            logging.error(f"API bilan bog'lanishda xato: {e}")
            return None

# --- BOT BUYRUQLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500
    # Buyurtma ID raqami noyob bo'lishi shart (masalan, foydalanuvchi ID va xabar vaqti)
    unique_order_id = f"{message.from_user.id}{message.message_id}"
    
    await message.answer("⏳ To'lov havolasi tayyorlanmoqda...")
    
    # API dan professional linkni olamiz
    pay_url = await get_checkout_url(amount, unique_order_id)
    
    if pay_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
        ])
        
        username = message.from_user.username if message.from_user.username else "foydalanuvchi"
        text = (
            f"🌟 <b>Stars: 50</b>\n"
            f"💵 <b>Narxi: {amount} so'm</b>\n"
            f"👤 <b>Username: @{username}</b>\n\n"
            "Tugmani bosing va ochilgan professional sahifada to'lovni bajaring."
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer("❌ To'lov tizimiga ulanishda xatolik yuz berdi. Iltimos, keyinroq urunib ko'ring.")

# --- WEBHOOK (TO'LOVNI TASDIQLASH) ---
async def handle_webhook(request):
    try:
        # Checkout.uz to'lovdan so'ng sizning webhookingizga POST yuboradi
        data = await request.post()
        # To'lov ma'lumotlarini tekshirish logikasi shu yerda bo'ladi
        return web.Response(text="OK")
    except:
        return web.Response(text="Error", status=500)

async def main():
    app = web.Application()
    app.router.add_post('/webhook/checkout', handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Railway yoki boshqa hosting uchun portni sozlash
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
