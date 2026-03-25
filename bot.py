import logging
import asyncio
import aiohttp
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
API_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"

# Loglarni yoqamiz - terminalda nima bo'layotganini ko'rib turasiz
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZA (users.db faylida saqlanadi) ---
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS payments (payment_id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER)")
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- AVTOMATIK TEKSHIRUVCHI (ORQA FONDA ISHLAYDI) ---
async def payment_monitor():
    logging.info("🚀 Avtomatik tekshiruvchi ishga tushdi...")
    while True:
        try:
            await asyncio.sleep(10) # Har 10 soniyada bazadagi to'lovlarni tekshiradi
            
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()
            cursor.execute("SELECT payment_id, user_id, amount FROM payments")
            pending_list = cursor.fetchall()
            conn.close()

            if not pending_list:
                continue

            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
                
                for p_id, u_id, amt in pending_list:
                    # Statusni tekshirish (Hujjatga ko'ra ID integer bo'lishi kerak)
                    payload = {"id": int(p_id)}
                    async with session.post("https://checkout.uz/api/v1/status_payment", json=payload, headers=headers) as resp:
                        res = await resp.json()
                        logging.info(f"Tekshiruv ID {p_id}: {res}")

                        if res.get("status") == "success" and res.get("data", {}).get("status") == "paid":
                            # 1. Balansni oshirish
                            update_balance(u_id, amt)
                            
                            # 2. Bazadan o'chirish (qayta qo'shilmasligi uchun)
                            conn = sqlite3.connect("users.db")
                            c = conn.cursor()
                            c.execute("DELETE FROM payments WHERE payment_id = ?", (p_id,))
                            conn.commit()
                            conn.close()
                            
                            # 3. Foydalanuvchiga xabar
                            await bot.send_message(u_id, f"✅ **To'lov tasdiqlandi!**\n\n💰 Hisobingizga {amt:,} so'm qo'shildi.")
                            logging.info(f"✅ User {u_id} balansi +{amt} ga yangilandi.")

        except Exception as e:
            logging.error(f"⚠️ Monitor xatosi: {e}")

# --- BOT BUYRUQLARI ---

@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
    res = cursor.fetchone()
    conn.close()
    bal = res[0] if res else 0
    await message.answer(f"👤 Hisobingiz: {bal:,} so'm\n\nTo'lov qilish uchun summani kiriting:")

@dp.message(F.text.isdigit())
async def create_pay(message: types.Message):
    amount = int(message.text)
    if amount < 100:
        await message.answer("Minimal 100 so'm kiriting.")
        return

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"amount": amount, "description": f"User {message.from_user.id}"}

    async with aiohttp.ClientSession() as session:
        async with session.post("https://checkout.uz/api/v1/create_payment", json=payload, headers=headers) as resp:
            res = await resp.json()
            if res.get("status") == "success":
                p = res.get("payment")
                p_id, p_url = p.get("_id"), p.get("_url")

                # Bazaga kutilayotgan to'lovni yozamiz
                conn = sqlite3.connect("users.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO payments (payment_id, user_id, amount) VALUES (?, ?, ?)", (p_id, message.from_user.id, amount))
                conn.commit()
                conn.close()

                kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💳 To'lash", url=p_url)]])
                await message.answer(f"💵 Summa: {amount:,} so'm\n\nTo'lovdan so'ng 10-20 soniya kuting, pul o'zi tushadi ⚡️", reply_markup=kb)
            else:
                await message.answer("❌ API xatosi.")

async def main():
    init_db()
    asyncio.create_task(payment_monitor()) # Monitoringni yoqish
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
