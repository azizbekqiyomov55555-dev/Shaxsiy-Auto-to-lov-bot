import asyncio
import logging
import aiohttp
from datetime import datetime
import pytz
import json
import hashlib
import hmac
from aiohttp import web

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command

# ================== SOZLAMALAR ==================
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
ADMIN_ID = 8332077004
MAIN_CHANNEL_ID = "@Azizbekl2026"

# CHECKOUT.UZ SOZLAMALARI
CHECKOUT_API_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"
CHECKOUT_MERCHANT_ID = "46"
CHECKOUT_BASE_URL = "https://checkout.uz/api/v1"
WEBHOOK_URL = "https://shaxsiy-auto-to-lov-bot-production.up.railway.app/webhook"

# ================== JSONBIN.IO SOZLAMALARI ==================
JSONBIN_API_KEY = "$2a$10$HEa6qY6FgdbvtwnxhGkIE.59M05ctGsBYJn7zuLyvhrrqsWH5peje"
JSONBIN_BIN_ID = "69c24750aa77b81da9139a00"
JSONBIN_BASE_URL = "https://api.jsonbin.io/v3"

# ================== JSONBIN.IO YORDAMCHI FUNKSIYALAR ==================
async def jb_read() -> dict:
    url = f"{JSONBIN_BASE_URL}/b/{JSONBIN_BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("record", {})
            return {}

async def jb_write(data: dict) -> bool:
    url = f"{JSONBIN_BASE_URL}/b/{JSONBIN_BIN_ID}"
    headers = {
        "X-Master-Key": JSONBIN_API_KEY,
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.put(url, json=data, headers=headers) as resp:
            return resp.status == 200

async def init_db():
    data = await jb_read()
    changed = False
    if not data:
        data = {}
        changed = True
    for key in ["users", "channels", "ads", "uc_prices", "uc_orders",
                "stars_prices", "stars_orders", "premium_prices", "premium_orders",
                "payment_orders", "settings"]:
        if key not in data:
            data[key] = []
            changed = True
    if "settings" not in data:
        data["settings"] = {
            "price": "50000",
            "card": "8600 0000 0000 0000 (Ism Familiya)",
            "start_msg": "Salom {name}! Botdan foydalaning.",
            "site_url": "https://azizbekqiyomov55555-dev.github.io/Test-bot-"
        }
        changed = True
    if "next_id" not in data:
        data["next_id"] = 1
        changed = True
    if changed:
        await jb_write(data)
    return data

def get_next_id(data: dict) -> int:
    nid = data.get("next_id", 1)
    data["next_id"] = nid + 1
    return nid

# ================== FSM HOLATLAR ==================
class AdForm(StatesGroup):
    video = State()
    level = State()
    guns = State()
    xsuits = State()
    rp = State()
    cars = State()
    price = State()
    phone = State()

class SupportForm(StatesGroup):
    msg = State()

class AdminForm(StatesGroup):
    start_msg = State()
    price = State()
    card = State()
    add_channel_id = State()
    add_channel_url = State()
    reply_msg = State()
    uc_price_amount = State()
    uc_price_value = State()
    stars_price_amount = State()
    stars_price_value = State()
    premium_price_duration = State()
    premium_price_value = State()

class UCOrderForm(StatesGroup):
    pubg_screenshot = State()

class StarsOrderForm(StatesGroup):
    choose_target = State()
    friend_username = State()

class PremiumOrderForm(StatesGroup):
    target_username = State()

# ================== BOT VA ROUTER ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ================== YORDAMCHI FUNKSIYALAR ==================
def get_time_tashkent():
    tz = pytz.timezone('Asia/Tashkent')
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

async def check_subscription(user_id):
    data = await jb_read()
    channels = data.get("channels", [])
    unsubbed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ['left', 'kicked']:
                unsubbed.append(ch["url"])
        except:
            pass
    return unsubbed

def get_main_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 E'lon berish"), KeyboardButton(text="🆘 Yordam")],
            [KeyboardButton(text="🎮 PUBG MOBILE UC OLISH 💎")],
            [KeyboardButton(text="⭐ TELEGRAM PREMIUM"), KeyboardButton(text="🌟 STARS OLISH")],
        ],
        resize_keyboard=True,
        is_persistent=True
    )
    return kb

# ================== CHECKOUT.UZ FUNKSIYALAR ==================
async def create_checkout_payment(amount: int, description: str, order_id: int, user_id: int) -> str:
    """Create payment link via checkout.uz and return payment URL."""
    url = f"{CHECKOUT_BASE_URL}/payment"
    headers = {
        "Authorization": f"Bearer {CHECKOUT_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "merchant_id": CHECKOUT_MERCHANT_ID,
        "amount": amount,
        "description": description,
        "callback_url": WEBHOOK_URL,
        "metadata": {
            "order_id": order_id,
            "user_id": user_id,
            "type": description.split()[0]  # e.g., "UC", "Stars", "Premium", "Ad"
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 201:
                data = await resp.json()
                return data.get("payment_url")
            else:
                error = await resp.text()
                logging.error(f"Checkout.uz error: {error}")
                return None

async def verify_checkout_signature(payload: bytes, signature: str) -> bool:
    secret = CHECKOUT_API_KEY.encode()
    computed = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)

# ================== WEBHOOK HANDLER ==================
async def webhook_handler(request: web.Request):
    signature = request.headers.get("X-Signature", "")
    body = await request.read()
    if not await verify_checkout_signature(body, signature):
        return web.Response(status=400, text="Invalid signature")

    data = await request.json()
    payment_id = data.get("payment_id")
    status = data.get("status")
    metadata = data.get("metadata", {})
    order_id = metadata.get("order_id")
    user_id = metadata.get("user_id")
    payment_type = metadata.get("type")

    if status == "completed":
        db = await jb_read()
        payment_orders = db.get("payment_orders", [])
        for po in payment_orders:
            if po["payment_id"] == payment_id:
                po["status"] = "paid"
                break
        else:
            payment_orders.append({
                "payment_id": payment_id,
                "order_id": order_id,
                "user_id": user_id,
                "type": payment_type,
                "status": "paid",
                "paid_at": get_time_tashkent()
            })
        db["payment_orders"] = payment_orders

        if payment_type == "Ad":
            users = db.get("users", [])
            for u in users:
                if u["user_id"] == user_id:
                    u["paid_slots"] = u.get("paid_slots", 0) + 1
                    break
            db["users"] = users
            await bot.send_message(user_id, "✅ To'lovingiz qabul qilindi! Endi e'lon berishingiz mumkin.", reply_markup=get_main_menu())

        elif payment_type == "UC":
            uc_orders = db.get("uc_orders", [])
            for o in uc_orders:
                if o["id"] == order_id:
                    o["status"] = "paid"
                    break
            db["uc_orders"] = uc_orders
            await bot.send_message(ADMIN_ID, f"💎 UC buyurtma #{order_id} to'landi!\nFoydalanuvchi: {user_id}\nTo'lovni tekshirib UC yuboring.")

        elif payment_type == "Stars":
            stars_orders = db.get("stars_orders", [])
            for o in stars_orders:
                if o["id"] == order_id:
                    o["status"] = "paid"
                    break
            db["stars_orders"] = stars_orders
            await bot.send_message(ADMIN_ID, f"⭐ Stars buyurtma #{order_id} to'landi!\nFoydalanuvchi: {user_id}\nTo'lovni tekshirib Stars yuboring.")

        elif payment_type == "Premium":
            premium_orders = db.get("premium_orders", [])
            for o in premium_orders:
                if o["id"] == order_id:
                    o["status"] = "paid"
                    break
            db["premium_orders"] = premium_orders
            await bot.send_message(ADMIN_ID, f"⭐ Premium buyurtma #{order_id} to'landi!\nFoydalanuvchi: {user_id}\nTo'lovni tekshirib Premium ulang.")

        await jb_write(db)
        return web.Response(status=200, text="OK")
    else:
        # Payment failed (ignored)
        return web.Response(status=200, text="OK")

# ================== START VA OBUNA ==================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    users = data.get("users", [])
    if not any(u["user_id"] == message.from_user.id for u in users):
        users.append({
            "user_id": message.from_user.id,
            "full_name": message.from_user.full_name,
            "username": message.from_user.username or "",
            "join_date": get_time_tashkent(),
            "posted_ads": 0,
            "paid_slots": 0,
            "pending_approval": 0
        })
        data["users"] = users
        await jb_write(data)

    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 Kanal {i+1} — Obuna bo'lish", url=url)]
            for i, url in enumerate(unsubbed)
        ] + [[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]])
        await message.answer("Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=btn)
        return

    start_text = data.get("settings", {}).get("start_msg", "Salom {name}!").replace("{name}", message.from_user.full_name)
    await message.answer(start_text, reply_markup=get_main_menu(), parse_mode="HTML")

@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    unsubbed = await check_subscription(call.from_user.id)
    if unsubbed:
        await call.answer("Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        data = await jb_read()
        start_text = data.get("settings", {}).get("start_msg", "Salom {name}!").replace("{name}", call.from_user.full_name)
        await call.message.answer(f"Rahmat! Obuna tasdiqlandi.\n\n{start_text}", reply_markup=get_main_menu())

# ================== MENU HANDLERLAR ==================
@router.message(F.text == "📝 E'lon berish")
async def menu_ad_cb(message: Message, state: FSMContext):
    if await check_subscription(message.from_user.id):
        await message.answer("Iltimos, avval kanallarga obuna bo'ling. /start ni bosing.")
        return

    data = await jb_read()
    users = data.get("users", [])
    user = next((u for u in users if u["user_id"] == message.from_user.id), None)
    if not user:
        await message.answer("Iltimos, /start bosing.")
        return

    posted = user.get("posted_ads", 0)
    paid = user.get("paid_slots", 0)
    pending = user.get("pending_approval", 0)

    if pending:
        await message.answer("⏳ Oldingi e'loningiz admin tomonidan ko'rib chiqilmoqda. Yangi e'lon berish uchun kuting.")
        return

    if posted >= (1 + paid):
        price = int(data.get("settings", {}).get("price", "50000"))
        # Create payment order
        order_id = get_next_id(data)
        payment_order = {
            "id": get_next_id(data),  # separate ID for payment record
            "order_id": order_id,
            "user_id": message.from_user.id,
            "type": "Ad",
            "amount": price,
            "status": "pending",
            "created_at": get_time_tashkent()
        }
        data["payment_orders"].append(payment_order)
        await jb_write(data)

        payment_url = await create_checkout_payment(price, f"Ad {order_id}", order_id, message.from_user.id)
        if payment_url:
            btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 To'lov qilish", url=payment_url)],
                [InlineKeyboardButton(text="🔄 Tekshirish", callback_data=f"check_payment_{order_id}")]
            ])
            await message.answer(
                f"Sizning bepul e'lonlar limitingiz tugagan.\n"
                f"1-video bepul, 2-sidan boshlab pullik.\n"
                f"E'lon narxi: {price} so'm.\n\n"
                f"To'lovni quyidagi tugma orqali amalga oshiring:",
                reply_markup=btn
            )
        else:
            await message.answer("❌ To'lov tizimida xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        return

    await message.answer("E'loningizni boshlaymiz.\nIltimos, akkaunt obzori videosini yuboring:")
    await state.set_state(AdForm.video)

@router.message(F.text == "🆘 Yordam")
async def menu_help_cb(message: Message, state: FSMContext):
    await message.answer("Adminga xabaringizni yozib qoldiring:")
    await state.set_state(SupportForm.msg)

# ================== PUBG MOBILE UC OLISH ==================
def get_uc_prices_keyboard(data, page=0):
    prices = sorted(data.get("uc_prices", []), key=lambda x: x.get("position", 0))
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Narxlar yo'q", callback_data="no_prices")]])
    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages-1))
    start, end = page*ITEMS_PER_PAGE, (page+1)*ITEMS_PER_PAGE
    rows = [[InlineKeyboardButton(
        text=f"💎 {p['uc_amount']} UC — {p['price']:,} so'm".replace(",", " "),
        callback_data=f"buy_uc_{p['id']}_{p['uc_amount']}_{p['price']}"
    )] for p in prices[start:end]]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"uc_page_{page-1}"))
    if page < total_pages-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"uc_page_{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="uc_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(F.text == "🎮 PUBG MOBILE UC OLISH 💎")
async def uc_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    await message.answer("UC miqdorini tanlang:", reply_markup=get_uc_prices_keyboard(data), parse_mode="HTML")

@router.callback_query(F.data.startswith("uc_page_"))
async def uc_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    await call.message.edit_reply_markup(reply_markup=get_uc_prices_keyboard(data, page))

@router.callback_query(F.data == "uc_back")
async def uc_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_uc_"))
async def buy_uc_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    uc_id, uc_amount, price = int(parts[2]), int(parts[3]), int(parts[4])
    await state.update_data(uc_id=uc_id, uc_amount=uc_amount, uc_price=price)
    await call.message.edit_text("PUBG ID raqamingizni kiriting:")
    await state.set_state(UCOrderForm.pubg_screenshot)
    await call.answer()

@router.message(UCOrderForm.pubg_screenshot, F.text)
async def get_pubg_id(message: Message, state: FSMContext):
    pubg_id = message.text
    await state.update_data(pubg_id=pubg_id)
    st = await state.get_data()
    uc_amount = st['uc_amount']
    price = st['uc_price']
    data = await jb_read()

    # Create order in db
    order_id = get_next_id(data)
    uc_order = {
        "id": order_id,
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username or "",
        "uc_amount": uc_amount,
        "price": price,
        "pubg_id": pubg_id,
        "status": "pending",
        "order_date": get_time_tashkent()
    }
    data["uc_orders"].append(uc_order)

    # Payment record
    payment_order = {
        "id": get_next_id(data),
        "order_id": order_id,
        "user_id": message.from_user.id,
        "type": "UC",
        "amount": price,
        "status": "pending",
        "created_at": get_time_tashkent()
    }
    data["payment_orders"].append(payment_order)
    await jb_write(data)

    payment_url = await create_checkout_payment(price, f"UC {order_id}", order_id, message.from_user.id)
    if payment_url:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=payment_url)],
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data=f"check_payment_{order_id}")]
        ])
        await message.answer(
            f"💎 <b>{uc_amount} UC — {price:,} so'm</b>\n\n"
            f"To'lovni quyidagi tugma orqali amalga oshiring:\n"
            f"To'lovdan keyin admin tasdiqlaydi va UC yuboriladi.",
            reply_markup=btn, parse_mode="HTML"
        )
    else:
        await message.answer("❌ To'lov tizimida xatolik. Keyinroq urinib ko'ring.")
    await state.clear()

@router.message(UCOrderForm.pubg_screenshot)
async def pubg_id_wrong(message: Message):
    await message.answer("Iltimos, PUBG ID raqamingizni yuboring.")

# ================== STARS OLISH ==================
def get_stars_prices_keyboard(data, page=0):
    prices = sorted(data.get("stars_prices", []), key=lambda x: x.get("position", 0))
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Narxlar yo'q", callback_data="no_prices")]])
    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages-1))
    start, end = page*ITEMS_PER_PAGE, (page+1)*ITEMS_PER_PAGE
    rows = [[InlineKeyboardButton(
        text=f"⭐ {p['stars_amount']} Stars — {p['price']:,} so'm".replace(",", " "),
        callback_data=f"buy_stars_{p['id']}_{p['stars_amount']}_{p['price']}"
    )] for p in prices[start:end]]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"stars_page_{page-1}"))
    if page < total_pages-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"stars_page_{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="stars_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(F.text == "🌟 STARS OLISH")
async def stars_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    await message.answer("Stars miqdorini tanlang:", reply_markup=get_stars_prices_keyboard(data), parse_mode="HTML")

@router.callback_query(F.data.startswith("stars_page_"))
async def stars_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    await call.message.edit_reply_markup(reply_markup=get_stars_prices_keyboard(data, page))

@router.callback_query(F.data == "stars_back")
async def stars_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_stars_"))
async def buy_stars_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    stars_id, stars_amount, price = int(parts[2]), int(parts[3]), int(parts[4])
    await state.update_data(stars_id=stars_id, stars_amount=stars_amount, stars_price=price)
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 O'zimga", callback_data="stars_target_me")],
        [InlineKeyboardButton(text="👫 Do'stimga", callback_data="stars_target_friend")]
    ])
    await call.message.edit_text("Stars kimga kerak?", reply_markup=btn)
    await state.set_state(StarsOrderForm.choose_target)
    await call.answer()

@router.callback_query(F.data == "stars_target_me", StarsOrderForm.choose_target)
async def stars_target_me(call: CallbackQuery, state: FSMContext):
    await state.update_data(target_type="me", target_username=call.from_user.username or str(call.from_user.id))
    await ask_stars_payment(call, state)

@router.callback_query(F.data == "stars_target_friend", StarsOrderForm.choose_target)
async def stars_target_friend(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Do'stingizning Telegram username'ini kiriting (masalan: @username):")
    await state.set_state(StarsOrderForm.friend_username)
    await call.answer()

@router.message(StarsOrderForm.friend_username)
async def get_stars_friend_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    await state.update_data(target_type="friend", target_username=username)
    await ask_stars_payment(message, state)

async def ask_stars_payment(event, state: FSMContext):
    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = st['stars_price']
    target_type = st['target_type']
    target_username = st['target_username']
    data = await jb_read()

    order_id = get_next_id(data)
    stars_order = {
        "id": order_id,
        "user_id": event.from_user.id,
        "full_name": event.from_user.full_name,
        "username": event.from_user.username or "",
        "stars_amount": stars_amount,
        "price": price,
        "target_type": target_type,
        "target_username": target_username,
        "status": "pending",
        "order_date": get_time_tashkent()
    }
    data["stars_orders"].append(stars_order)

    payment_order = {
        "id": get_next_id(data),
        "order_id": order_id,
        "user_id": event.from_user.id,
        "type": "Stars",
        "amount": price,
        "status": "pending",
        "created_at": get_time_tashkent()
    }
    data["payment_orders"].append(payment_order)
    await jb_write(data)

    payment_url = await create_checkout_payment(price, f"Stars {order_id}", order_id, event.from_user.id)
    if payment_url:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=payment_url)],
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data=f"check_payment_{order_id}")]
        ])
        await event.message.answer(
            f"⭐ <b>{stars_amount} Stars — {price:,} so'm</b>\n"
            f"👤 Kimga: {target_username}\n\n"
            f"To'lovni quyidagi tugma orqali amalga oshiring:",
            reply_markup=btn, parse_mode="HTML"
        )
    else:
        await event.message.answer("❌ To'lov tizimida xatolik.")
    await state.clear()

# ================== TELEGRAM PREMIUM ==================
def get_premium_prices_keyboard(data, page=0):
    prices = sorted(data.get("premium_prices", []), key=lambda x: x.get("price", 0))
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Narxlar yo'q", callback_data="no_prices")]])
    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages-1))
    start, end = page*ITEMS_PER_PAGE, (page+1)*ITEMS_PER_PAGE
    rows = [[InlineKeyboardButton(
        text=f"⭐ {p['duration']} — {p['price']:,} so'm".replace(",", " "),
        callback_data=f"buy_premium_{p['id']}_{p['price']}"
    )] for p in prices[start:end]]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"premium_page_{page-1}"))
    if page < total_pages-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"premium_page_{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="premium_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(F.text == "⭐ TELEGRAM PREMIUM")
async def premium_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    await message.answer("Premium muddatini tanlang:", reply_markup=get_premium_prices_keyboard(data), parse_mode="HTML")

@router.callback_query(F.data.startswith("premium_page_"))
async def premium_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    await call.message.edit_reply_markup(reply_markup=get_premium_prices_keyboard(data, page))

@router.callback_query(F.data == "premium_back")
async def premium_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_premium_"))
async def buy_premium_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    pid = int(parts[2])
    price = int(parts[3])
    data = await jb_read()
    premium_item = next((p for p in data.get("premium_prices", []) if p["id"] == pid), None)
    if not premium_item:
        await call.answer("Xatolik!")
        return
    duration = premium_item["duration"]
    await state.update_data(premium_pid=pid, premium_price=price, premium_duration=duration)
    await call.message.edit_text("Premium tushiriladigan profil username'ini yuboring (masalan: @username):")
    await state.set_state(PremiumOrderForm.target_username)
    await call.answer()

@router.message(PremiumOrderForm.target_username)
async def get_premium_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    await state.update_data(target_username=username)
    st = await state.get_data()
    price = st['premium_price']
    duration = st['premium_duration']
    data = await jb_read()

    order_id = get_next_id(data)
    premium_order = {
        "id": order_id,
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username or "",
        "duration": duration,
        "price": price,
        "target_username": username,
        "status": "pending",
        "order_date": get_time_tashkent()
    }
    data["premium_orders"].append(premium_order)

    payment_order = {
        "id": get_next_id(data),
        "order_id": order_id,
        "user_id": message.from_user.id,
        "type": "Premium",
        "amount": price,
        "status": "pending",
        "created_at": get_time_tashkent()
    }
    data["payment_orders"].append(payment_order)
    await jb_write(data)

    payment_url = await create_checkout_payment(price, f"Premium {order_id}", order_id, message.from_user.id)
    if payment_url:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", url=payment_url)],
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data=f"check_payment_{order_id}")]
        ])
        await message.answer(
            f"⭐ <b>{duration} — {price:,} so'm</b>\n"
            f"👤 Premium tushiriladigan profil: @{username}\n\n"
            f"To'lovni quyidagi tugma orqali amalga oshiring:",
            reply_markup=btn, parse_mode="HTML"
        )
    else:
        await message.answer("❌ To'lov tizimida xatolik.")
    await state.clear()

# ================== PAYMENT CHECK CALLBACK ==================
@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_cb(call: CallbackQuery):
    order_id = int(call.data.split("_")[2])
    data = await jb_read()
    payment_orders = data.get("payment_orders", [])
    payment = next((p for p in payment_orders if p["order_id"] == order_id), None)
    if payment and payment["status"] == "paid":
        await call.answer("✅ To'lov tasdiqlangan!", show_alert=True)
        await call.message.delete()
    else:
        await call.answer("⏳ To'lov hali tasdiqlanmagan. Iltimos, birozdan keyin tekshiring.", show_alert=True)

# ================== E'LON BERISH (AD FORM) ==================
@router.message(AdForm.video, F.video)
async def get_video(message: Message, state: FSMContext):
    await state.update_data(video=message.video.file_id)
    await message.answer("Akkaunt levelini (darajasini) kiriting:")
    await state.set_state(AdForm.level)

@router.message(AdForm.level)
async def get_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text)
    await message.answer("Nechta qurol (upgradable) bor? Faqat raqamda kiriting:")
    await state.set_state(AdForm.guns)

@router.message(AdForm.guns)
async def get_guns(message: Message, state: FSMContext):
    await state.update_data(guns=message.text)
    await message.answer("Nechta X-suit bor? Kiriting:")
    await state.set_state(AdForm.xsuits)

@router.message(AdForm.xsuits)
async def get_xsuits(message: Message, state: FSMContext):
    await state.update_data(xsuits=message.text)
    await message.answer("Nechta RP olingan? Kiriting:")
    await state.set_state(AdForm.rp)

@router.message(AdForm.rp)
async def get_rp(message: Message, state: FSMContext):
    await state.update_data(rp=message.text)
    await message.answer("Nechta mashina (skin) bor? Kiriting:")
    await state.set_state(AdForm.cars)

@router.message(AdForm.cars)
async def get_cars(message: Message, state: FSMContext):
    await state.update_data(cars=message.text)
    await message.answer("Narxini so'mda kiriting (masalan: 150000):")
    await state.set_state(AdForm.price)

@router.message(AdForm.price)
async def get_price_ad(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Telefon raqamingizni kiriting (masalan: +998901234567):")
    await state.set_state(AdForm.phone)

@router.message(AdForm.phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    st = await state.get_data()
    text = (
        f"📋 <b>E'lon ma'lumotlari:</b>\n\n"
        f"🎮 Level: {st.get('level')}\n"
        f"🔫 Qurollar: {st.get('guns')}\n"
        f"👔 X-suitlar: {st.get('xsuits')}\n"
        f"🏆 RP: {st.get('rp')}\n"
        f"🚗 Mashinalar: {st.get('cars')}\n"
        f"💰 Narx: {st.get('price')} so'm\n"
        f"📞 Telefon: {st.get('phone')}"
    )

    data = await jb_read()
    ad_id = get_next_id(data)
    ads = data.get("ads", [])
    ads.append({
        "id": ad_id,
        "user_id": message.from_user.id,
        "video_id": st.get('video'),
        "text": text,
        "status": "pending"
    })
    data["ads"] = ads

    users = data.get("users", [])
    for u in users:
        if u["user_id"] == message.from_user.id:
            u["pending_approval"] = 1
            break
    data["users"] = users
    await jb_write(data)

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_ad_{ad_id}"),
         InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_ad_{ad_id}")]
    ])

    try:
        await bot.send_video(ADMIN_ID, video=st.get('video'),
            caption=f"📢 Yangi e'lon!\nFoydalanuvchi: {message.from_user.full_name} (ID: {message.from_user.id})\n\n{text}",
            reply_markup=btn, parse_mode="HTML")
    except:
        pass

    await message.answer("✅ E'loningiz adminga yuborildi. Tasdiqlanishini kuting.", reply_markup=get_main_menu())
    await state.clear()

# ================== SUPPORT ==================
@router.message(SupportForm.msg)
async def get_support_msg(message: Message, state: FSMContext):
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Javob berish", callback_data=f"reply_{message.from_user.id}")]])
    await bot.send_message(ADMIN_ID, f"📩 Yangi xabar!\nKimdan: {message.from_user.full_name} (ID: {message.from_user.id})\n\nXabar: {message.text}", reply_markup=btn)
    await message.answer("Xabaringiz adminga yetkazildi.", reply_markup=get_main_menu())
    await state.clear()

# ================== ADMIN PANEL ==================
@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data="admin_price"),
         InlineKeyboardButton(text="💳 Kartani o'zgartirish", callback_data="admin_card")],
        [InlineKeyboardButton(text="📝 Start xabarni o'zgartirish", callback_data="admin_startmsg")],
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_ch"),
         InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="admin_del_ch")],
        [InlineKeyboardButton(text="━━━━━ 💎 UC SOZLAMALARI ━━━━━", callback_data="section_title")],
        [InlineKeyboardButton(text="➕ UC narxi qo'shish", callback_data="admin_add_uc_price"),
         InlineKeyboardButton(text="📋 UC narxlari", callback_data="admin_uc_list")],
        [InlineKeyboardButton(text="📦 UC buyurtmalar", callback_data="admin_uc_orders"),
         InlineKeyboardButton(text="🗑 UC narxlarini tozalash", callback_data="admin_clear_uc")],
        [InlineKeyboardButton(text="━━━━━ ⭐ STARS SOZLAMALARI ━━━━━", callback_data="section_title")],
        [InlineKeyboardButton(text="➕ Stars narxi qo'shish", callback_data="admin_add_stars_price"),
         InlineKeyboardButton(text="📋 Stars narxlari", callback_data="admin_stars_list")],
        [InlineKeyboardButton(text="📦 Stars buyurtmalar", callback_data="admin_stars_orders"),
         InlineKeyboardButton(text="🗑 Stars narxlarini tozalash", callback_data="admin_clear_stars")],
        [InlineKeyboardButton(text="━━━━━ 💜 PREMIUM SOZLAMALARI ━━━━━", callback_data="section_title")],
        [InlineKeyboardButton(text="➕ Premium narxi qo'shish", callback_data="admin_add_premium_price"),
         InlineKeyboardButton(text="📋 Premium narxlari", callback_data="admin_premium_list")],
        [InlineKeyboardButton(text="📦 Premium buyurtmalar", callback_data="admin_premium_orders"),
         InlineKeyboardButton(text="🗑 Premium narxlarini tozalash", callback_data="admin_clear_premium")],
    ])
    await message.answer("⚙️ Admin panel", reply_markup=btn)

# ================== ADMIN STATISTIKA ==================
@router.callback_query(F.data == "admin_stats")
async def send_stats(call: CallbackQuery):
    data = await jb_read()
    users = data.get("users", [])
    uc_orders = data.get("uc_orders", [])
    stars_orders = data.get("stars_orders", [])
    premium_orders = data.get("premium_orders", [])
    uc_paid = sum(1 for o in uc_orders if o.get("status") == "paid")
    text = (
        f"📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: <b>{len(users)} ta</b>\n"
        f"💎 UC buyurtmalar: <b>{len(uc_orders)} ta</b> (toʻlangan: {uc_paid})\n"
        f"⭐ Stars buyurtmalar: <b>{len(stars_orders)} ta</b>\n"
        f"🎖 Premium buyurtmalar: <b>{len(premium_orders)} ta</b>\n"
        f"🕐 Vaqt: {get_time_tashkent()}"
    )
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

# ================== ADMIN UC NARX ==================
@router.callback_query(F.data == "admin_add_uc_price")
async def add_uc_price_step1(call: CallbackQuery, state: FSMContext):
    await call.message.answer("💎 UC miqdorini kiriting\n\nMasalan: `60`", parse_mode="HTML")
    await state.set_state(AdminForm.uc_price_amount)

@router.message(AdminForm.uc_price_amount)
async def add_uc_price_step2(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    await state.update_data(uc_amount=int(message.text))
    await message.answer(f"💰 {message.text} UC narxini kiriting (so'mda)", parse_mode="HTML")
    await state.set_state(AdminForm.uc_price_value)

@router.message(AdminForm.uc_price_value)
async def add_uc_price_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    st = await state.get_data()
    uc_amount = st['uc_amount']
    price = int(message.text)
    data = await jb_read()
    prices = data.get("uc_prices", [])
    existing = next((p for p in prices if p["uc_amount"] == uc_amount), None)
    if existing:
        existing["price"] = price
        await message.answer(f"✅ <b>{uc_amount} UC</b> narxi yangilandi: <b>{price:,} so'm</b>".replace(",", " "), parse_mode="HTML")
    else:
        nid = get_next_id(data)
        prices.append({"id": nid, "uc_amount": uc_amount, "price": price, "position": 0})
        await message.answer(f"✅ <b>{uc_amount} UC — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML")
    data["uc_prices"] = prices
    await jb_write(data)
    await state.clear()

@router.callback_query(F.data == "admin_uc_list")
async def admin_uc_list(call: CallbackQuery):
    data = await jb_read()
    prices = sorted(data.get("uc_prices", []), key=lambda x: x.get("uc_amount", 0))
    if not prices:
        await call.message.answer("❌ Hozircha UC narxlari kiritilmagan.")
        await call.answer()
        return
    text = "💎 <b>UC NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
    rows = []
    for item in prices:
        text += f"• {item['uc_amount']} UC — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([
            InlineKeyboardButton(text=f"💎 {item['uc_amount']} UC — {item['price']:,} so'm".replace(",", " "), callback_data="uc_info"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_uc_price_{item['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_to_admin")])
    await call.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@router.callback_query(F.data.startswith("del_uc_price_"))
async def del_uc_price(call: CallbackQuery):
    pid = int(call.data.split("_")[3])
    data = await jb_read()
    prices = data.get("uc_prices", [])
    item = next((p for p in prices if p["id"] == pid), None)
    if item:
        data["uc_prices"] = [p for p in prices if p["id"] != pid]
        await jb_write(data)
        await call.answer(f"✅ {item['uc_amount']} UC narxi o'chirildi!", show_alert=True)
        await admin_uc_list(call)  # refresh list
    else:
        await call.answer("Topilmadi!", show_alert=True)

@router.callback_query(F.data == "admin_clear_uc")
async def admin_clear_uc_ask(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="confirm_clear_uc"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="back_to_admin"),
    ]])
    await call.message.answer("⚠️ Barcha UC narxlarini o'chirasizmi?\nBu amalni qaytarib bo'lmaydi!", parse_mode="HTML", reply_markup=btn)
    await call.answer()

@router.callback_query(F.data == "confirm_clear_uc")
async def confirm_clear_uc(call: CallbackQuery):
    data = await jb_read()
    data["uc_prices"] = []
    await jb_write(data)
    await call.answer("✅ Barcha UC narxlari o'chirildi!", show_alert=True)
    await call.message.delete()

# ================== ADMIN STARS NARX ==================
@router.callback_query(F.data == "admin_add_stars_price")
async def add_stars_price_step1(call: CallbackQuery, state: FSMContext):
    await call.message.answer("⭐ Stars miqdorini kiriting\n\nMasalan: `50`", parse_mode="HTML")
    await state.set_state(AdminForm.stars_price_amount)

@router.message(AdminForm.stars_price_amount)
async def add_stars_price_step2(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    await state.update_data(stars_amount=int(message.text))
    await message.answer(f"💰 {message.text} Stars narxini kiriting (so'mda)", parse_mode="HTML")
    await state.set_state(AdminForm.stars_price_value)

@router.message(AdminForm.stars_price_value)
async def add_stars_price_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = int(message.text)
    data = await jb_read()
    prices = data.get("stars_prices", [])
    existing = next((p for p in prices if p["stars_amount"] == stars_amount), None)
    if existing:
        existing["price"] = price
        await message.answer(f"✅ <b>{stars_amount} Stars</b> narxi yangilandi: <b>{price:,} so'm</b>".replace(",", " "), parse_mode="HTML")
    else:
        nid = get_next_id(data)
        prices.append({"id": nid, "stars_amount": stars_amount, "price": price, "position": 0})
        await message.answer(f"✅ <b>{stars_amount} Stars — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML")
    data["stars_prices"] = prices
    await jb_write(data)
    await state.clear()

@router.callback_query(F.data == "admin_stars_list")
async def admin_stars_list(call: CallbackQuery):
    data = await jb_read()
    prices = sorted(data.get("stars_prices", []), key=lambda x: x.get("stars_amount", 0))
    if not prices:
        await call.message.answer("❌ Hozircha Stars narxlari kiritilmagan.")
        await call.answer()
        return
    text = "⭐ <b>STARS NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
    rows = []
    for item in prices:
        text += f"• {item['stars_amount']} Stars — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([
            InlineKeyboardButton(text=f"⭐ {item['stars_amount']} Stars — {item['price']:,} so'm".replace(",", " "), callback_data="stars_info"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_stars_price_{item['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_to_admin")])
    await call.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@router.callback_query(F.data.startswith("del_stars_price_"))
async def del_stars_price(call: CallbackQuery):
    pid = int(call.data.split("_")[3])
    data = await jb_read()
    prices = data.get("stars_prices", [])
    item = next((p for p in prices if p["id"] == pid), None)
    if item:
        data["stars_prices"] = [p for p in prices if p["id"] != pid]
        await jb_write(data)
        await call.answer(f"✅ {item['stars_amount']} Stars narxi o'chirildi!", show_alert=True)
        await admin_stars_list(call)
    else:
        await call.answer("Topilmadi!", show_alert=True)

@router.callback_query(F.data == "admin_clear_stars")
async def admin_clear_stars_ask(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="confirm_clear_stars"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="back_to_admin"),
    ]])
    await call.message.answer("⚠️ Barcha Stars narxlarini o'chirasizmi?\nBu amalni qaytarib bo'lmaydi!", parse_mode="HTML", reply_markup=btn)
    await call.answer()

@router.callback_query(F.data == "confirm_clear_stars")
async def confirm_clear_stars(call: CallbackQuery):
    data = await jb_read()
    data["stars_prices"] = []
    await jb_write(data)
    await call.answer("✅ Barcha Stars narxlari o'chirildi!", show_alert=True)
    await call.message.delete()

# ================== ADMIN PREMIUM NARX ==================
@router.callback_query(F.data == "admin_add_premium_price")
async def add_premium_price_step1(call: CallbackQuery, state: FSMContext):
    await call.message.answer("⭐ Premium muddatini kiriting\n\nMasalan: `1 oylik`", parse_mode="HTML")
    await state.set_state(AdminForm.premium_price_duration)

@router.message(AdminForm.premium_price_duration)
async def add_premium_price_step2(message: Message, state: FSMContext):
    await state.update_data(premium_duration=message.text)
    await message.answer(f"💰 «{message.text}» narxini kiriting (so'mda)", parse_mode="HTML")
    await state.set_state(AdminForm.premium_price_value)

@router.message(AdminForm.premium_price_value)
async def add_premium_price_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    st = await state.get_data()
    duration = st['premium_duration']
    price = int(message.text)
    data = await jb_read()
    nid = get_next_id(data)
    prices = data.get("premium_prices", [])
    prices.append({"id": nid, "duration": duration, "price": price, "position": 0})
    data["premium_prices"] = prices
    await jb_write(data)
    await message.answer(f"✅ <b>{duration} — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "admin_premium_list")
async def admin_premium_list(call: CallbackQuery):
    data = await jb_read()
    prices = sorted(data.get("premium_prices", []), key=lambda x: x.get("price", 0))
    if not prices:
        await call.message.answer("❌ Hozircha Premium narxlari kiritilmagan.")
        await call.answer()
        return
    text = "💜 <b>PREMIUM NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
    rows = []
    for item in prices:
        text += f"• {item['duration']} — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([
            InlineKeyboardButton(text=f"💜 {item['duration']} — {item['price']:,} so'm".replace(",", " "), callback_data="premium_info"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_premium_price_{item['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_to_admin")])
    await call.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@router.callback_query(F.data.startswith("del_premium_price_"))
async def del_premium_price(call: CallbackQuery):
    pid = int(call.data.split("_")[3])
    data = await jb_read()
    prices = data.get("premium_prices", [])
    item = next((p for p in prices if p["id"] == pid), None)
    if item:
        data["premium_prices"] = [p for p in prices if p["id"] != pid]
        await jb_write(data)
        await call.answer(f"✅ {item['duration']} narxi o'chirildi!", show_alert=True)
        await admin_premium_list(call)
    else:
        await call.answer("Topilmadi!", show_alert=True)

@router.callback_query(F.data == "admin_clear_premium")
async def admin_clear_premium_ask(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="confirm_clear_premium"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="back_to_admin"),
    ]])
    await call.message.answer("⚠️ Barcha Premium narxlarini o'chirasizmi?\nBu amalni qaytarib bo'lmaydi!", parse_mode="HTML", reply_markup=btn)
    await call.answer()

@router.callback_query(F.data == "confirm_clear_premium")
async def confirm_clear_premium(call: CallbackQuery):
    data = await jb_read()
    data["premium_prices"] = []
    await jb_write(data)
    await call.answer("✅ Barcha Premium narxlari o'chirildi!", show_alert=True)
    await call.message.delete()

# ================== ADMIN BUYURTMALAR ==================
@router.callback_query(F.data == "admin_uc_orders")
async def admin_uc_orders(call: CallbackQuery):
    data = await jb_read()
    orders = sorted(data.get("uc_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]
    if not orders:
        await call.message.answer("📦 Hozircha UC buyurtmalar yo'q.")
        await call.answer()
        return
    text = "📦 <b>OXIRGI 20 UC BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "paid" else "❌")
        text += f"{emoji} #{o['id']} | {o['full_name']} | {o['uc_amount']} UC | {o['price']:,} so'm | {o['order_date']}\n".replace(",", " ")
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "admin_stars_orders")
async def admin_stars_orders(call: CallbackQuery):
    data = await jb_read()
    orders = sorted(data.get("stars_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]
    if not orders:
        await call.message.answer("⭐ Hozircha Stars buyurtmalar yo'q.")
        await call.answer()
        return
    text = "⭐ <b>OXIRGI 20 STARS BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "paid" else "❌")
        text += f"{emoji} #{o['id']} | {o['full_name']} | {o['stars_amount']} Stars | @{o['target_username']} | {o['order_date']}\n"
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "admin_premium_orders")
async def admin_premium_orders(call: CallbackQuery):
    data = await jb_read()
    orders = sorted(data.get("premium_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]
    if not orders:
        await call.message.answer("⭐ Hozircha Premium buyurtmalar yo'q.")
        await call.answer()
        return
    text = "⭐ <b>OXIRGI 20 PREMIUM BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "paid" else "❌")
        text += f"{emoji} #{o['id']} | {o['full_name']} | {o['duration']} | @{o['target_username']} | {o['order_date']}\n"
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

# ================== ADMIN SOZLAMALAR ==================
@router.callback_query(F.data == "admin_price")
async def set_price_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi e'lon narxini kiriting (faqat raqam):")
    await state.set_state(AdminForm.price)

@router.message(AdminForm.price)
async def save_price(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["price"] = message.text
    await jb_write(data)
    await message.answer("✅ Narx yangilandi!")
    await state.clear()

@router.callback_query(F.data == "admin_card")
async def set_card_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi karta raqamini kiriting (faqat ma'lumot uchun):")
    await state.set_state(AdminForm.card)

@router.message(AdminForm.card)
async def save_card(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["card"] = message.text
    await jb_write(data)
    await message.answer("✅ Karta yangilandi!")
    await state.clear()

@router.callback_query(F.data == "admin_startmsg")
async def set_start_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi start xabarini kiriting. ({name} — foydalanuvchi ismi):")
    await state.set_state(AdminForm.start_msg)

@router.message(AdminForm.start_msg)
async def save_start(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["start_msg"] = message.text
    await jb_write(data)
    await message.answer("✅ Start xabar yangilandi!")
    await state.clear()

@router.callback_query(F.data == "admin_add_ch")
async def add_ch_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal ID sini kiriting (masalan: @kanal_useri yoki -100123...):")
    await state.set_state(AdminForm.add_channel_id)

@router.message(AdminForm.add_channel_id)
async def add_ch_url(message: Message, state: FSMContext):
    await state.update_data(ch_id=message.text)
    await message.answer("Kanal ssilkasini kiriting (https://t.me/...):")
    await state.set_state(AdminForm.add_channel_url)

@router.message(AdminForm.add_channel_url)
async def save_ch(message: Message, state: FSMContext):
    st = await state.get_data()
    data = await jb_read()
    channels = data.get("channels", [])
    nid = get_next_id(data)
    channels.append({"id": nid, "channel_id": st['ch_id'], "url": message.text})
    data["channels"] = channels
    await jb_write(data)
    await message.answer("✅ Kanal qo'shildi!")
    await state.clear()

@router.callback_query(F.data == "admin_del_ch")
async def del_ch_step(call: CallbackQuery):
    data = await jb_read()
    channels = data.get("channels", [])
    if not channels:
        await call.message.answer("Kanallar yo'q.")
        return
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 O'chirish: {ch['channel_id']}", callback_data=f"delch_{ch['id']}")]
        for ch in channels
    ])
    await call.message.answer("Qaysi kanalni o'chirasiz?", reply_markup=btn)

@router.callback_query(F.data.startswith("delch_"))
async def del_ch_action(call: CallbackQuery):
    c_id = int(call.data.split("_")[1])
    data = await jb_read()
    data["channels"] = [c for c in data.get("channels", []) if c["id"] != c_id]
    await jb_write(data)
    await call.message.edit_text("✅ Kanal o'chirildi.")

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    await admin_panel(call.message)
    await call.answer()

# ================== ADMIN JAVOB ==================
@router.callback_query(F.data.startswith("reply_"))
async def reply_support_cb(call: CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.update_data(reply_to=user_id)
    await call.message.answer("Foydalanuvchiga javob matnini kiriting:")
    await state.set_state(AdminForm.reply_msg)

@router.message(AdminForm.reply_msg)
async def send_reply(message: Message, state: FSMContext):
    st = await state.get_data()
    user_id = st.get('reply_to')
    await bot.send_message(user_id, f"👨‍💻 Admin javobi:\n\n{message.text}")
    await message.answer("Javob yuborildi.")
    await state.clear()

# ================== ADMIN E'LON TASDIQLASH ==================
@router.callback_query(F.data.startswith("app_ad_"))
async def approve_ad(call: CallbackQuery):
    ad_id = int(call.data.split("_")[2])
    data = await jb_read()
    ads = data.get("ads", [])
    ad = next((a for a in ads if a["id"] == ad_id), None)
    if not ad:
        await call.answer("❌ E'lon topilmadi!", show_alert=True)
        return

    user_id = ad["user_id"]
    me = await bot.get_me()
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Sotuvchi bilan aloqa", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton(text="📢 Reklama berish", url=f"https://t.me/{me.username}?start=ad")]
    ])

    try:
        await bot.send_video(MAIN_CHANNEL_ID, video=ad["video_id"], caption=ad["text"], reply_markup=btn, parse_mode="HTML")
    except Exception as e:
        await call.answer(f"❌ Kanalga yuborishda XATO: {e}", show_alert=True)
        return

    ad["status"] = "approved"
    users = data.get("users", [])
    for u in users:
        if u["user_id"] == user_id:
            u["posted_ads"] = u.get("posted_ads", 0) + 1
            u["pending_approval"] = 0
            break
    data["ads"] = ads
    data["users"] = users
    await jb_write(data)

    await bot.send_message(user_id, "✅ E'loningiz kanalga joylandi!", reply_markup=get_main_menu())
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ KANALGA JOYLANDI", reply_markup=None)
    await call.answer("✅ E'lon kanalga joylandi!", show_alert=True)

@router.callback_query(F.data.startswith("rej_ad_"))
async def reject_ad(call: CallbackQuery):
    ad_id = int(call.data.split("_")[2])
    data = await jb_read()
    ads = data.get("ads", [])
    ad = next((a for a in ads if a["id"] == ad_id), None)
    if not ad:
        await call.answer("❌ E'lon topilmadi!", show_alert=True)
        return

    user_id = ad["user_id"]
    ad["status"] = "rejected"
    users = data.get("users", [])
    for u in users:
        if u["user_id"] == user_id:
            u["pending_approval"] = 0
            break
    data["ads"] = ads
    data["users"] = users
    await jb_write(data)

    await bot.send_message(user_id, "❌ E'loningiz admin tomonidan rad etildi.", reply_markup=get_main_menu())
    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ BEKOR QILINGAN", reply_markup=None)
    await call.answer("❌ E'lon bekor qilindi.", show_alert=True)

# ================== CHECKBOT ==================
@router.message(Command("checkbot"), F.from_user.id == ADMIN_ID)
async def check_bot_status(message: Message):
    me = await bot.get_me()
    try:
        member = await bot.get_chat_member(MAIN_CHANNEL_ID, me.id)
        status = member.status
        can_post = getattr(member, 'can_post_messages', False)
        ha = "✅ Ha"
        yoq = "❌ Yo'q"
        ok = "✅ Hammasi yaxshi!"
        xato = "❌ Botni kanalga ADMIN qilib qo'shish kerak!"
        await message.answer(
            f"🤖 Bot: @{me.username}\n"
            f"📢 Kanal: {MAIN_CHANNEL_ID}\n"
            f"👤 Status: {status}\n"
            f"✉️ Post yuborish huquqi: {ha if can_post else yoq}\n\n"
            f"{ok if can_post else xato}"
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")

# ================== ASOSIY ISHGA TUSHIRISH ==================
async def main():
    print("⏳ Jsonbin.io baza tekshirilmoqda...")
    await init_db()
    print("✅ Baza tayyor!")
    dp.include_router(router)
    print("✅ Bot ishga tushdi...")

    # Webhook server
    app = web.Application()
    app.router.add_post('/webhook', webhook_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("✅ Webhook server 8080-portda ishga tushdi.")

    # Bot polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
