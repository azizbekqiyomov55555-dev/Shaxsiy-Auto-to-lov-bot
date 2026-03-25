import logging
import asyncio
import aiohttp
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
API_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def add_balance(user_id, amount):
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- API FUNKSIYALARI ---

async def create_payment(amount, user_id):
    url = "https://checkout.uz/api/v1/create_payment"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"amount": int(amount), "description": f"ID: {user_id} balansini to'ldirish"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                if result.get("status") == "success":
                    return result.get("payment")
                return None
        except Exception as e:
            logging.error(f"Xato: {e}")
            return None

async def check_payment_status(payment_id):
    url = "https://checkout.uz/api/v1/status_payment"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"id": int(payment_id)}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                logging.info(f"Tekshirish javobi: {result}")
                
                # API 'paid' statusini qaytarsa
                if result.get("status") == "success":
                    data = result.get("data", {})
                    if data.get("status") == "paid":
                        return True, data.get("amount")
                return False, 0
        except Exception as e:
            logging.error(f"Tekshirishda xato: {e}")
            return False, 0

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(
        f"👋 Salom {message.from_user.full_name}!\n\n"
        f"💰 Balansingiz: {balance:,} so'm\n\n"
        f"Hisobni to'ldirish uchun summani kiriting (masalan: 1000):"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(f"💳 Joriy balansingiz: {balance:,} so'm")

@dp.message(F.text.isdigit())
async def process_amount(message: types.Message):
    amount = int(message.text)
    if amount < 100:
        await message.answer("❌ Minimal summa 100 so'm!")
        return

    msg = await message.answer("⏳ To'lov havolasi yaratilmoqda...")
    payment = await create_payment(amount, message.from_user.id)

    if payment:
        p_id = payment.get("_id")
        p_url = payment.get("_url")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=p_url)],
            [InlineKeyboardButton(text="🔄 To'lovni tekshirish", callback_data=f"check_{p_id}")]
        ])
        
        await msg.edit_text(
            f"💵 Miqdor: {amount:,} so'm\n\n"
            f"To'lovni amalga oshirgach, pastdagi tugmani bosing 👇",
            reply_markup=keyboard
        )
    else:
        await msg.edit_text("❌ To'lov yaratishda xatolik yuz berdi.")

@dp.callback_query(F.data.startswith("check_"))
async def check_callback(callback: types.CallbackQuery):
    payment_id = callback.data.split("_")[1]
    
    is_paid, amount = await check_payment_status(payment_id)
    
    if is_paid:
        add_balance(callback.from_user.id, amount)
        new_balance = get_balance(callback.from_user.id)
        
        await callback.message.edit_text(
            f"✅ Tabriklaymiz! To'lov qabul qilindi.\n\n"
            f"➕ Hisobingizga {amount:,} so'm qo'shildi.\n"
            f"💰 Yangi balans: {new_balance:,} so'm"
        )
    else:
        await callback.answer("❌ To'lov hali topilmadi. To'lagan bo'lsangiz biroz kutib qayta urunib ko'ring.", show_alert=True)

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
