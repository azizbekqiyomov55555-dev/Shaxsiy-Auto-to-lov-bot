import logging
import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- KONFIGURATSIYA (Railway Variables bo'limiga qo'shing) ---
# Agar Railway-da yozmasangiz, qo'shtirnoq ichiga yozib qo'yishingiz ham mumkin
BOT_TOKEN = os.getenv("BOT_TOKEN", "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc")
KASSA_ID = os.getenv("KASSA_ID", "46")
SECRET_KEY = os.getenv("SECRET_KEY", "N2MxYjNkYmI4ZjdlYjVjMWYxZTM")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- CHECKOUT.UZ API BILAN BOG'LANISH ---
async def get_checkout_url(amount, order_id):
    # API manzili (Agar api. xato bersa, checkout.uz/api/... ni sinab ko'radi)
    url = "https://api.checkout.uz/api/v1/payment/create"
    
    headers = {
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "amount": int(amount),
        "order_id": str(order_id),
        "kassa_id": int(KASSA_ID),
        "description": f"Stars 50 - Order {order_id}"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                status = response.status
                result = await response.json()
                
                logging.info(f"API Debug: Status {status}, Result: {result}")
                
                if status == 200 and result.get("status") == True:
                    return result.get("payment_url")
                else:
                    logging.error(f"Checkout API xatosi: {result}")
                    return None
        except Exception as e:
            logging.error(f"Ulanishda xato yuz berdi: {e}")
            return None

# --- BOT BUYRUQLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500 # So'mda
    unique_order_id = f"ORDER_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    
    msg = await message.answer("⏳ To'lov havolasi tayyorlanmoqda...")
    
    pay_url = await get_checkout_url(amount, unique_order_id)
    
    if pay_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
        ])
        
        text = (
            f"<b>To'lov ma'lumotlari:</b>\n\n"
            f"📦 Mahsulot: 50 Stars\n"
            f"💰 Narxi: {amount:,} so'm\n"
            f"🆔 Buyurtma ID: {unique_order_id}\n\n"
            "<i>To'lovdan so'ng xizmat avtomatik faollashadi.</i>"
        )
        await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await msg.edit_text("❌ To'lov havolasini olib bo'lmadi. Keyinroq urinib ko'ring yoki admin bilan bog'laning.")

# --- WEBHOOK: TO'LOVNI AUTO TASDIQLASH ---
async def handle_checkout_notification(request):
    try:
        data = await request.post()
        # Checkout.uz yuborgan ma'lumotlar
        order_id = data.get("order_id")
        status = data.get("status") # Odatda 1 yoki 'success'
        
        if status:
            # Order ID ichidan foydalanuvchi ID sini ajratamiz (ORDER_USERID_TIME)
            user_id = order_id.split("_")[1]
            
            # Foydalanuvchiga xabar yuborish
            await bot.send_message(
                user_id, 
                f"✅ <b>Tabriklaymiz! To'lovingiz qabul qilindi.</b>\nBuyurtma: {order_id}\n\nStars balansingizga qo'shildi!"
            )
            logging.info(f"To'lov muvaffaqiyatli: {order_id}")
        
        return web.Response(text="OK")
    except Exception as e:
        logging.error(f"Webhookda xato: {e}")
        return web.Response(text="error", status=500)

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    # Web serverni sozlash (Webhook uchun)
    app = web.Application()
    app.router.add_post('/checkout/callback', handle_checkout_notification)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Railway-da PORT avtomatik beriladi
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logging.info(f"Bot va Webhook server {port}-portda ishga tushdi.")
    
    # Botni ishga tushirish
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
