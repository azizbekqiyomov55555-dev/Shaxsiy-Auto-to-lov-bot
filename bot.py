import logging
import hashlib
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- KONFIGURATSIYA ---
API_TOKEN = '8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc'
KASSA_ID = "46"
SECRET_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- TO'G'RILANGAN TO'LOV LINKI ---
def create_payment_url(amount, order_id):
    # Checkout.uz ning to'g'ri link formati (so'rov parametrlari bilan)
    return f"https://checkout.uz/pay?merchant_id={KASSA_ID}&amount={amount}&order_id={order_id}"

# --- BOT BUYRUQLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500
    # Order ID da faqat raqam va harf bo'lgani ma'qul
    order_id = f"pay{message.from_user.id}x{message.message_id}"
    
    pay_url = create_payment_url(amount, order_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])
    
    # HTML formatida xavfsizroq
    username = message.from_user.username if message.from_user.username else "user"
    text = (
        f"🌟 <b>Stars: 50</b>\n"
        f"💵 <b>Narxi: {amount} so'm</b>\n"
        f"👤 <b>Username: @{username}</b>\n\n"
        "To'lov qilish tugmasini bosing va ochilgan sahifada to'lovni bajaring."
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# --- WEBHOOK QISMI (O'ZGARISHSIZ) ---
async def handle_webhook(request):
    try:
        data = await request.post()
        order_id = data.get('order_id')
        status = data.get('status')
        amount = data.get('amount')
        sign = data.get('sign')
        
        check_str = f"{KASSA_ID}{amount}{order_id}{SECRET_KEY}"
        my_sign = hashlib.md5(check_str.encode()).hexdigest()
        
        if my_sign == sign and (status == 'success' or status == 'paid'):
            # ID ni order_id dan ajratib olish (pay12345x678 formatidan)
            user_id = int(order_id.replace('pay', '').split('x')[0])
            await bot.send_message(user_id, "✅ <b>To'lov qabul qilindi!</b>\n50 yulduz hisobingizga yuborildi.", parse_mode="HTML")
            return web.Response(text="OK")
        
        return web.Response(text="Fail", status=400)
    except:
        return web.Response(text="Error", status=500)

async def main():
    app = web.Application()
    app.router.add_post('/webhook/checkout', handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    # Railway'da portni avtomatik olish uchun:
    import os
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
