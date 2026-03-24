import logging
import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
KASSA_ID = 46
SECRET_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_checkout_url(amount, order_id):
    # Railway DNS muammosi bo'lmasligi uchun asosiy URL
    url = "https://checkout.uz/api/v1/payment/create"
    
    headers = {
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "amount": int(amount),
        "order_id": str(order_id),
        "kassa_id": KASSA_ID,
        "description": f"Buyurtma #{order_id}"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=15) as response:
                result = await response.json()
                # Logda aniq nima bo'layotganini ko'ramiz
                logging.info(f"API JAVOBI: {result}")
                
                if response.status == 200 and result.get("status") == True:
                    return result.get("payment_url")
                else:
                    # Agar kassa nofaol bo'lsa, xatoni terminalda yozadi
                    logging.error(f"XATO: {result.get('message', 'Nomaʼlum xato')}")
                    return None
        except Exception as e:
            logging.error(f"ULANISH XATOSI: {e}")
            return None

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500
    order_id = f"ID_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    
    msg = await message.answer("⏳ To'lov havolasi yaratilmoqda...")
    
    pay_url = await get_checkout_url(amount, order_id)
    
    if pay_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)]
        ])
        await msg.edit_text("To'lov qilish uchun pastdagi tugmani bosing:", reply_markup=keyboard)
    else:
        # Kassa hali faollashmagan bo'lsa shu xabar chiqadi
        await msg.edit_text("❌ To'lov tizimi hozircha nofaol. Kassa tasdiqlanishini kutyapmiz.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
