import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
# Professional API da Kassa ID odatda tokenga bog'langan bo'ladi, 
# lekin hujjatda ko'rsatilmagani uchun faqat tokendan foydalanamiz.
API_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM" 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_checkout_url(amount, description):
    # Professional API hujjati bo'yicha URL
    url = "https://checkout.uz/api/v1/create_payment"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # JSON hujjatidagi 'requestBody'ga asosan:
    payload = {
        "amount": int(amount),
        "description": description
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=15) as response:
                result = await response.json()
                logging.info(f"API JAVOBI: {result}")
                
                # Hujjat bo'yicha status "success" bo'lishi kerak
                if response.status == 200 and result.get("status") == "success":
                    # Link 'payment' obyekti ichidagi '_url' kalitida keladi
                    return result.get("payment", {}).get("_url")
                else:
                    logging.error(f"API XATOSI: {result}")
                    return None
        except Exception as e:
            logging.error(f"ULANISH XATOSI: {e}")
            return None

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500  # Skrinshotingizdagi summa
    # Buyurtma ID skrinshotingizdagidek chiqishi uchun description ga yozamiz
    order_id = f"#{15000 + message.from_user.id % 1000}" 
    description = f"Buyurtma {order_id}"
    
    msg = await message.answer("⏳ To'lov havolasi yaratilmoqda...")
    
    pay_url = await get_checkout_url(amount, description)
    
    if pay_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)]
        ])
        await msg.edit_text(
            f"💰 To'lov miqdori: {amount:,} so'm\n"
            f"📝 Ta'rif: {description}\n\n"
            f"To'lovni amalga oshirish uchun tugmani bosing:",
            reply_markup=keyboard
        )
    else:
        await msg.edit_text(
            "❌ To'lov tizimida xatolik.\n"
            "Sababi: API kalit noto'g'ri yoki kassa hali tasdiqlanmagan.\n"
            "Loglarni tekshiring!"
        )

async def main():
    # Bot ishga tushganda eski xabarlarni o'qib yubormasligi uchun
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi")
