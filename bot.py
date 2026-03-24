import logging
import hashlib
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- KONFIGURATSIYA ---
API_TOKEN = '8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc'
KASSA_ID = "46"
SECRET_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

# Bot va Dispatcher
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- TO'LOV LINKINI YARATISH ---
def create_payment_url(amount, order_id):
    # Checkout.uz uchun to'lov linki formati
    # Odatda: https://checkout.uz/pay/{kassa_id}/{amount}/{order_id}
    # Eslatma: Tizimingizga qarab format farq qilishi mumkin. 
    # Quyida eng keng tarqalgan usul:
    return f"https://checkout.uz/pay/{KASSA_ID}/{amount}/{order_id}"

# --- BOT BUYRUQLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # Namuna sifatida 50 yulduz (11500 so'm)
    amount = 11500
    order_id = f"order_{message.from_user.id}_{message.message_id}" # Noyob ID
    
    pay_url = create_payment_url(amount, order_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])
    
    text = (
        f"🌟 **Stars: 50**\n"
        f"💵 **Narxi: {amount} so'm**\n"
        f"👤 **Username: @{message.from_user.username}**\n\n"
        "To'lov qilish tugmasini bosing. To'lovdan so'ng hisobingizga avtomatik tushadi."
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

# --- WEBHOOK (TO'LOVNI TEKSHIRISH) ---
# Bu qism Checkout.uz'dan keladigan xabarni qabul qiladi
async def handle_webhook(request):
    data = await request.post() # Checkout.uz ma'lumotlarni POST orqali yuboradi
    
    # Checkout yuboradigan ma'lumotlar (namuna)
    order_id = data.get('order_id')
    status = data.get('status') # 'success' yoki 'paid'
    amount = data.get('amount')
    sign = data.get('sign') # Xavfsizlik uchun imzo (hash)
    
    # Imzoni tekshirish (Fake to'lovlardan himoya)
    # logic: md5(kassa_id + amount + order_id + secret_key)
    check_str = f"{KASSA_ID}{amount}{order_id}{SECRET_KEY}"
    my_sign = hashlib.md5(check_str.encode()).hexdigest()
    
    if my_sign == sign and status == 'success':
        # To'lov muvaffaqiyatli!
        # Foydalanuvchi ID sini order_id dan ajratib olamiz
        user_id = int(order_id.split('_')[1])
        
        await bot.send_message(user_id, "✅ To'lov muvaffaqiyatli! 50 yulduz hisobingizga qo'shildi.")
        return web.Response(text="OK")
    
    return web.Response(text="Error", status=400)

# --- WEB SERVERNİ ISHGA TUSHIRISH ---
async def on_startup(dispatcher):
    app = web.Application()
    app.router.add_post('/webhook/checkout', handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080) # Port 8080
    await site.start()
    print("Webhook server 8080-portda ishlamoqda...")

# Botni yurgizish
if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(on_startup(dp))
    dp.run_polling(bot)
