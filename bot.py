import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
KASSA_ID = 46  # Dashboarddagi ID bilan bir xilligini tekshiring
SECRET_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM" # Bu yerga 'Secret Key' emas, 'API Key' qo'yib ko'ring

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_checkout_url(amount, order_id):
    # API manzilini aniqlashtiring (kerak bo'lsa api.checkout.uz qilib ko'ring)
    url = "https://api.checkout.uz/api/v1/payment/create"
    
    headers = {
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "amount": int(amount), # Tiyn emas, so'mda bo'lsa int(11500)
        "order_id": str(order_id),
        "kassa_id": int(KASSA_ID),
        "description": f"Buyurtma #{order_id}"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=15) as response:
                result = await response.json()
                logging.info(f"API JAVOBI: {result}") # Terminalda bu qatorni kuzating!
                
                if response.status == 200 and result.get("status") == True:
                    return result.get("payment_url")
                else:
                    # Xato sababini aniqroq ko'rsatish uchun
                    error_msg = result.get('message', 'Nomaʼlum xato')
                    logging.error(f"CHECKOUT XATOSI: {error_msg}")
                    return None
        except Exception as e:
            logging.error(f"ULANISH XATOSI: {e}")
            return None

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500 # So'm miqdori
    order_id = f"ID_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    
    msg = await message.answer("⏳ To'lov havolasi yaratilmoqda...")
    
    pay_url = await get_checkout_url(amount, order_id)
    
    if pay_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)]
        ])
        await msg.edit_text(f"Hisobingiz: {amount} so'm.\nTo'lov qilish uchun pastdagi tugmani bosing:", reply_markup=keyboard)
    else:
        # Terminalda chiqqan logga qarab bu xabarni o'zgartirishingiz mumkin
        await msg.edit_text("❌ To'lov tizimida xatolik yuz berdi. Iltimos, keyinroq urunib ko'ring yoki administratorga murojaat qiling.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
