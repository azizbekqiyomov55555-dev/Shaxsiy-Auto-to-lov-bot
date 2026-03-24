import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import os

# --- KONFIGURATSIYA (Railway Variables-dan oladi) ---
API_TOKEN = os.getenv("BOT_TOKEN")
KASSA_ID = os.getenv("KASSA_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- TO'LOV LINKINI YARATISH ---
def create_pay_url(amount, order_id):
    # Eng sodda va ishlaydigan usul - Direct Link
    return f"https://checkout.uz/pay/{KASSA_ID}?amount={amount}&order_id={order_id}"

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    amount = 11500  # Summa so'mda
    # Har bir to'lov uchun noyob ID (foydalanuvchi_id + vaqt)
    order_id = f"PAY_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    
    pay_url = create_pay_url(amount, order_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lov qilish (11,500 so'm)", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Holatni tekshirish", callback_data=f"check_{order_id}")]
    ])
    
    text = (
        "<b>Assalomu alaykum!</b>\n\n"
        "Stars sotib olish uchun quyidagi tugmani bosing.\n"
        "To'lovdan so'ng xizmat avtomatik faollashadi."
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# --- WEBHOOK: TO'LOV TASDIQLANGANINI QABUL QILISH ---
# Checkout.uz to'lov tugagach ushbu manzilga POST so'rov yuboradi
async def checkout_webhook(request):
    data = await request.post() # Checkout.uz POST orqali ma'lumot yuboradi
    
    # Kelgan ma'lumotlarni tekshiramiz
    order_id = data.get("order_id")
    status = data.get("status") # Odatda 'success' yoki '1' bo'ladi
    amount = data.get("amount")
    
    if status:
        # Foydalanuvchi ID-sini order_id ichidan ajratib olamiz
        # Biz order_id ni "PAY_USERID_TIME" formatida qilgan edik
        try:
            user_id = order_id.split("_")[1]
            
            # Foydalanuvchiga xabar yuboramiz
            await bot.send_message(
                user_id, 
                f"✅ <b>To'lov qabul qilindi!</b>\nSumma: {amount} so'm\nOrder: {order_id}\n\nRahmat!"
            )
            logging.info(f"To'lov tasdiqlandi: {order_id}")
        except Exception as e:
            logging.error(f"Webhook xatosi: {e}")

    return web.Response(text="OK") # Checkout.uz ga "OK" deb javob qaytarish shart

# --- SERVERNI ISHGA TUSHIRISH ---
async def main():
    # Web server yaratamiz (Webhook uchun)
    app = web.Application()
    app.router.add_post('/webhook/checkout', checkout_webhook)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Railway beradigan PORT-da ishga tushiramiz
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logging.info(f"Server {port}-portda ishlamoqda...")
    
    # Botni polling rejimida boshlaymiz
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
