import logging
import hashlib
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import asyncio

# --- KONFIGURATSIYA ---
API_TOKEN = '8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc'
KASSA_ID = "46"
SECRET_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- TO'LOV LINKINI YARATISH ---
def create_payment_url(amount, order_id):
    # Checkout.uz standart formati
    return f"https://checkout.uz/pay/{KASSA_ID}/{amount}/{order_id}"

# --- BOT BUYRUQLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500
    # Noyob buyurtma ID yaratish (user_id va xabar vaqti orqali)
    order_id = f"{message.from_user.id}x{message.message_id}"
    
    pay_url = create_payment_url(amount, order_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])
    
    # Username'dagi '_' belgisi xato bermasligi uchun HTML ishlatamiz
    user_tag = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    
    text = (
        f"🌟 <b>Stars: 50</b>\n"
        f"💵 <b>Narxi: {amount} so'm</b>\n"
        f"👤 <b>Username: {user_tag}</b>\n\n"
        "To'lov qilish tugmasini bosing va to'lovni amalga oshiring. "
        "1 daqiqa ichida hisobingizga yuboriladi."
    )
    
    # parse_mode="HTML" - bu juda muhim!
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# --- WEBHOOK (TO'LOVNI QABUL QILISH) ---
async def handle_webhook(request):
    try:
        data = await request.post()
        
        order_id = data.get('order_id')
        status = data.get('status')
        amount = data.get('amount')
        sign = data.get('sign')
        
        # Checkout.uz imzosini tekshirish (Xavfsizlik)
        check_str = f"{KASSA_ID}{amount}{order_id}{SECRET_KEY}"
        my_sign = hashlib.md5(check_str.encode()).hexdigest()
        
        if my_sign == sign and status == 'success':
            # order_id dan foydalanuvchi ID sini ajratib olamiz (biz order_id ni 'IDxVaqt' deb ochgandik)
            user_id = int(order_id.split('x')[0])
            
            await bot.send_message(
                user_id, 
                "✅ <b>To'lov muvaffaqiyatli!</b>\n50 yulduz hisobingizga qo'shildi.",
                parse_mode="HTML"
            )
            return web.Response(text="OK")
        
        return web.Response(text="Invalid data", status=400)
    except Exception as e:
        logging.error(f"Webhook xatosi: {e}")
        return web.Response(text="Error", status=500)

# --- BOT VA WEB SERVERNİ BIRGA ISHLATISH ---
async def main():
    # Web serverni sozlash
    app = web.Application()
    app.router.add_post('/webhook/checkout', handle_webhook)
    
    runner = web.AppRunner(app)
    await runner.setup()
    # Railway porti uchun:
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    logging.info("Webhook server 8080-portda ishlamoqda...")
    
    # Botni polling rejimida ishga tushirish
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi!")
