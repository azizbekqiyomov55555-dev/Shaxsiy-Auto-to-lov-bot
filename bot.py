import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
API_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Holatlarni belgilash
class PaymentStates(StatesGroup):
    waiting_for_amount = State()

# --- API FUNKSIYASI ---
async def get_checkout_url(amount, description):
    url = "https://checkout.uz/api/v1/create_payment"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "amount": int(amount),
        "description": description
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=15) as response:
                result = await response.json()
                logging.info(f"API JAVOBI: {result}")
                
                if response.status == 200 and result.get("status") == "success":
                    return result.get("payment", {}).get("_url")
                return None
        except Exception as e:
            logging.error(f"ULANISH XATOSI: {e}")
            return None

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Assalomu alaykum! To'lov qilish uchun summani kiriting (so'mda):\n"
        "ℹ️ Minimal miqdor: 100 so'm\n\n"
        "Masalan: 5000"
    )
    await state.set_state(PaymentStates.waiting_for_amount)

@dp.message(PaymentStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    # Faqat raqamligini tekshirish
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqamlarda summa kiriting:")
        return

    amount = int(message.text)
    
    # --- MINIMAL SUMMA TEKSHIRUVI (100 so'm) ---
    if amount < 100:
        await message.answer("❌ Xatolik: Minimal to'lov miqdori 100 so'm bo'lishi kerak.\nQaytadan kiriting:")
        return

    msg = await message.answer("⏳ To'lov havolasi yaratilmoqda...")
    
    description = f"Foydalanuvchi @{message.from_user.username or message.from_user.id} to'lovi"
    pay_url = await get_checkout_url(amount, description)

    if pay_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=pay_url)]
        ])
        await msg.edit_text(
            f"✅ To'lov tayyor!\n\n"
            f"💰 Summa: {amount:,} so'm\n"
            f"📝 Ta'rif: {description}\n\n"
            f"To'lash uchun pastdagi tugmani bosing:",
            reply_markup=keyboard
        )
        # To'lov linki berilgach holatni tozalaymiz
        await state.clear()
    else:
        # Agar API xato bersa (masalan kassa tasdiqlanmagan bo'lsa)
        await msg.edit_text(
            "⚠️ To'lov tizimi hozircha nofaol.\n"
            "Iltimos, administrator kassa tasdiqlashini kuting."
        )
        await state.clear()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi")
