import logging
import asyncio
import aiohttp
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
API_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect("payments_bot.db")
    cursor = conn.cursor()
    # Foydalanuvchilar jadvali
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
    # Kutilayotgan to'lovlar jadvali (Avtomatik tekshirish uchun)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_payments (
            payment_id TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount INTEGER, 
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

def get_user_balance(user_id):
    conn = sqlite3.connect("payments_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect("payments_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- AVTOMATIK TEKSHIRISH TIZIMI (BACKGROUND TASK) ---
async def auto_payment_checker():
    """Har 15 soniyada barcha kutilayotgan to'lovlarni tekshiradi"""
    while True:
        await asyncio.sleep(15) # Har 15 soniyada tekshiradi
        
        conn = sqlite3.connect("payments_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT payment_id, user_id, amount FROM pending_payments WHERE status = 'pending'")
        pending = cursor.fetchall()
        conn.close()

        if not pending:
            continue

        async with aiohttp.ClientSession() as session:
            for p_id, u_id, amt in pending:
                url = "https://checkout.uz/api/v1/status_payment"
                headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
                
                try:
                    async with session.post(url, json={"id": str(p_id)}, headers=headers) as response:
                        result = await response.json()
                        
                        # Agar to'lov muvaffaqiyatli bo'lsa
                        if result.get("status") == "success" and result.get("data", {}).get("status") == "paid":
                            # 1. Balansni yangilash
                            update_balance(u_id, amt)
                            
                            # 2. Bazadan to'lovni o'chirish (yoki statusini o'zgartirish)
                            conn = sqlite3.connect("payments_bot.db")
                            c = conn.cursor()
                            c.execute("DELETE FROM pending_payments WHERE payment_id = ?", (p_id,))
                            conn.commit()
                            conn.close()
                            
                            # 3. Foydalanuvchiga AVTOMATIK xabar yuborish
                            new_bal = get_user_balance(u_id)
                            try:
                                await bot.send_message(
                                    u_id, 
                                    f"✅ **To'lov qabul qilindi!**\n\n"
                                    f"💰 Hisobingizga {amt:,} so'm qo'shildi.\n"
                                    f"💳 Joriy balansingiz: {new_bal:,} so'm"
                                )
                            except Exception as e:
                                logging.error(f"Xabar yuborishda xato: {e}")
                                
                except Exception as e:
                    logging.error(f"API tekshirishda xato: {e}")

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    balance = get_user_balance(message.from_user.id)
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}!\n\n"
        f"💰 Balansingiz: {balance:,} so'm\n\n"
        f"Hisobni to'ldirish uchun summani raqam bilan yozing:"
    )

@dp.message(F.text.isdigit())
async def process_amount(message: types.Message):
    amount = int(message.text)
    if amount < 100:
        await message.answer("❌ Minimal summa 100 so'm.")
        return

    # API orqali to'lov yaratish
    url = "https://checkout.uz/api/v1/create_payment"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"amount": amount, "description": f"User {message.from_user.id} to'lovi"}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            result = await response.json()
            
            if result.get("status") == "success":
                payment = result.get("payment")
                p_id = payment.get("_id")
                p_url = payment.get("_url")

                # Bazaga kutilayotgan to'lov sifatida saqlaymiz
                conn = sqlite3.connect("payments_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO pending_payments (payment_id, user_id, amount) VALUES (?, ?, ?)", 
                               (p_id, message.from_user.id, amount))
                conn.commit()
                conn.close()

                # Foydalanuvchiga link beramiz
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="💳 To'lov qilish", url=p_url)]
                ])
                await message.answer(
                    f"💵 To'lov miqdori: {amount:,} so'm\n\n"
                    f"To'lovni amalga oshirishingiz bilan pul avtomatik tarzda hisobingizga tushadi. "
                    f"Hech qanday tugmani bosish shart emas ⚡️",
                    reply_markup=kb
                )
            else:
                await message.answer("❌ To'lov tizimida xatolik. API kalitni tekshiring.")

async def main():
    init_db()
    # Orqa fonda tekshiruvchini ishga tushirish
    asyncio.create_task(auto_payment_checker())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
