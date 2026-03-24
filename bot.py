import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

# --- KONFIGURATSIYA ---
API_TOKEN = os.getenv("BOT_TOKEN", "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc")
KASSA_ID = 46  # Integer (son) bo'lishi shart
SECRET_KEY = os.getenv("SECRET_KEY", "N2MxYjNkYmI4ZjdlYjVjMWYxZTM")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- API ORQALI BUYURTMANI RO'YXATDAN O'TKAZISH ---
async def get_checkout_url(amount, order_id):
    url = "https://api.checkout.uz/api/v1/payment/create"
    
    # Headerlarni Checkout.uz talabiga ko'ra to'g'rilaymiz
    headers = {
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "amount": int(amount), # So'mda (masalan: 11500)
        "order_id": str(order_id),
        "kassa_id": KASSA_ID,
        "description": "Stars sotib olish uchun" # Ba'zida bu maydon majburiy bo'ladi
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                print(f"API JAVOBI: {result}") # Railway loglarida xatoni ko'rish uchun
                
                if response.status == 200 and result.get("status") == True:
                    return result.get("payment_url")
                else:
                    return None
        except Exception as e:
            print(f"ULANISHDA XATO: {e}")
            return None

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500
    # Buyurtma ID raqami doim har xil bo'lishi kerak
    unique_order_id = f"{message.from_user.id}{int(asyncio.get_event_loop().time())}"
    
    wait_msg = await message.answer("⏳ To'lov havolasi yaratilmoqda...")
    
    pay_url = await get_checkout_url(amount, unique_order_id)
    
    if pay_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
        ])
        await wait_msg.edit_text(
            f"🌟 <b>Stars: 50</b>\n💵 <b>Narxi: {amount} so'm</b>\n\nTo'lov tugmasini bosing:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        # Xatolik chiqsa loglarni ko'ring
        await wait_msg.edit_text("❌ To'lov tizimiga ulanib bo'lmadi. Dashboarddan IP cheklovini tekshiring.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
