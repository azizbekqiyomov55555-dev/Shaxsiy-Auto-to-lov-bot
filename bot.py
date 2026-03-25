import logging
import asyncio
import aiohttp
import sqlite3
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

# --- MA'LUMOTLAR BAZASI (SQLite) ---
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    if res: return res[0]
    return 0

def add_balance(user_id, amount):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Holatlar
class PaymentStates(StatesGroup):
    waiting_for_amount = State()

# --- API FUNKSIYALARI ---

# 1. To'lov yaratish
async def create_payment(amount, description):
    url = "https://checkout.uz/api/v1/create_payment"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"amount": int(amount), "description": description}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                if response.status == 200 and result.get("status") == "success":
                    return result.get("payment") # Obyektni qaytaramiz (id va url bor)
                return None
        except Exception as e:
            logging.error(f"API ERROR: {e}")
            return None

# 2. To'lov holatini tekshirish
async def check_payment_status(payment_id):
    url = "https://checkout.uz/api/v1/status_payment"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"id": int(payment_id)}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                # JSON hujjatiga ko'ra "paid" statusini qidiramiz
                if result.get("status") == "success" and result.get("data", {}).get("status") == "paid":
                    return True, result.get("data", {}).get("amount")
                return False, 0
        except Exception as e:
            logging.error(f"CHECK ERROR: {e}")
            return False, 0

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(
        f"👤 Hisobingiz: {balance:,} so'm\n\n"
        f"Pul qo'shish uchun summani yozing (kamida 100 so'm):",
    )
    # Bizga state kerak emas, oddiy raqam yozsa ham tutamiz
    # Lekin tartib uchun state ishlatamiz:
    # await state.set_state(PaymentStates.waiting_for_amount)

@dp.message(F.text.isdigit())
async def process_amount(message: types.Message):
    amount = int(message.text)
    if amount < 100:
        await message.answer("Minimal miqdor 100 so'm!")
        return

    msg = await message.answer("⏳ Havola tayyorlanmoqda...")
    payment = await create_payment(amount, f"User {message.from_user.id} balance top-up")

    if payment:
        p_id = payment.get("_id")
        p_url = payment.get("_url")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=p_url)],
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data=f"check_{p_id}")]
        ])
        
        await msg.edit_text(
            f"💰 To'lov miqdori: {amount:,} so'm\n\n"
            f"To'lovni amalga oshirgach 'Tekshirish' tugmasini bosing.",
            reply_markup=keyboard
        )
    else:
        await msg.edit_text("❌ To'lov yaratib bo'lmadi. API xatosi.")

@dp.callback_query(F.data.startswith("check_"))
async def check_callback(callback: types.CallbackQuery):
    payment_id = callback.data.split("_")[1]
    
    is_paid, amount = await check_payment_status(payment_id)
    
    if is_paid:
        add_balance(callback.from_user.id, amount)
        new_balance = get_balance(callback.from_user.id)
        
        await callback.message.edit_text(
            f"✅ To'lov muvaffaqiyatli qabul qilindi!\n\n"
            f"➕ Hisobingizga {amount:,} so'm qo'shildi.\n"
            f"💳 Jami balans: {new_balance:,} so'm"
        )
        await callback.answer("Muvaffaqiyatli!")
    else:
        await callback.answer("❌ To'lov hali amalga oshirilmagan yoki xatolik.", show_alert=True)

async def main():
    init_db() # Bazani yaratish
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
