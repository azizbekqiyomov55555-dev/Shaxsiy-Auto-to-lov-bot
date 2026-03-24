import logging
import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- KONFIGURATSIYA ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc")
KASSA_ID = os.getenv("KASSA_ID", "46")
SECRET_KEY = os.getenv("SECRET_KEY", "N2MxYjNkYmI4ZjdlYjVjMWYxZTM")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- CHECKOUT.UZ API BILAN BOG'LANISH (2 TA URL SINAB KO'RILADI) ---
async def get_checkout_url(amount, order_id):
    # Railway DNS muammosi uchun 2 xil manzil
    urls = [
        "https://api.checkout.uz/api/v1/payment/create",
        "https://checkout.uz/api/v1/payment/create"
    ]
    
    headers = {
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "amount": int(amount),
        "order_id": str(order_id),
        "kassa_id": int(KASSA_ID),
        "description": f"Stars to'lovi. Order: {order_id}"
    }

    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                logging.info(f"Ulanishga urinish: {url}")
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    status = response.status
                    result = await response.json()
                    
                    if status == 200 and result.get("status") == True:
                        logging.info(f"Muvaffaqiyatli: {url}")
                        return result.get("payment_url")
                    else:
                        logging.error(f"API Xatosi ({url}): {result}")
            except Exception as e:
                logging.error(f"Domen topilmadi yoki ulanmadi ({url}): {e}")
                continue # Keyingi URL-ni sinab ko'radi
    return None

# --- BOT BUYRUQLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500
    # Har safar yangi buyurtma ID yaratish (muhim!)
    unique_order_id = f"ID_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    
    msg = await message.answer("⏳ To'lov havolasi yaratilmoqda...")
    
    pay_url = await get_checkout_url(amount, unique_order_id)
    
    if pay_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
        ])
        await msg.edit_text(
            f"🌟 <b>Stars sotib olish</b>\n💰 Narxi: {amount:,} so'm\n\nTo'lov qilish uchun pastdagi tugmani bosing:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await msg.edit_text("❌ To'lov tizimida DNS xatolik (Railway interneti Checkout.uz ni topa olmayapti). Iltimos, 1 daqiqadan so'ng qayta urinib ko'ring.")

# --- WEBHOOK: TO'LOVNI TASDIQLASH ---
async def handle_callback(request):
    try:
        data = await request.post()
        order_id = data.get("order_id")
        status = data.get("status")
        
        if status:
            # Order_id dan foydalanuvchi ID sini olamiz: ID_USERID_TIME
            user_id = order_id.split("_")[1]
            await bot.send_message(user_id, f"✅ To'lovingiz qabul qilindi!\nBuyurtma: {order_id}")
            
        return web.Response(text="OK")
    except Exception as e:
        logging.error(f"Webhook xatosi: {e}")
        return web.Response(text="error", status=500)

# --- ASOSIY QISM ---
async def main():
    app = web.Application()
    app.router.add_post('/callback', handle_callback)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logging.info(f"Server {port}-portda ishga tushdi.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
