import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

# --- KONFIGURATSIYA ---
API_TOKEN = '8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc'
KASSA_ID = 46  # Integer bo'lgani yaxshi
SECRET_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- API ORQALI TO'LOV LINKINI OLISH ---
async def get_checkout_url(amount, order_id):
    url = "https://api.checkout.uz/api/v1/payment/create"
    headers = {
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "amount": int(amount), # Checkout.uz odatda so'mda qabul qiladi
        "order_id": str(order_id),
        "kassa_id": KASSA_ID,
        "return_url": "https://t.me/SizningBotUsername" # SHU YERGA BOTINGIZNI LINKINI YOZING
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                status_code = response.status
                result = await response.json()
                
                if status_code == 200 and result.get("status") == True:
                    return result.get("payment_url")
                else:
                    # Konsolda xatoni ko'rish uchun:
                    logging.error(f"API Xatosi (Status {status_code}): {result}")
                    return None
        except Exception as e:
            logging.error(f"Ulanishda xato: {e}")
            return None

# --- BOT BUYRUQLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500
    # Noyob order_id yaratish
    unique_order_id = f"ID_{message.from_user.id}_{message.message_id}"
    
    msg = await message.answer("⏳ To'lov havolasi tayyorlanmoqda...")
    
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
            "Tugmani bosing va to'lovni amalga oshiring."
        )
        await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await msg.edit_text("❌ To'lov tizimida texnik xatolik. Iltimos, keyinroq urinib ko'ring yoki admin bilan bog'laning.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")
