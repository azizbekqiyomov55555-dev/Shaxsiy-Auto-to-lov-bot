import asyncio
import logging
import aiohttp
import hashlib
import hmac
import json
from datetime import datetime
import pytz
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command
from aiohttp import web

# ================== SOZLAMALAR ==================
BOT_TOKEN = "8745465963:AAFEOfQ90-2Rb6ok10QMumHoNYfKwmPWZjA"
ADMIN_ID = 8537782289
MAIN_CHANNEL_ID = "@Azizbekl2026"

# ================== CHECKOUT.UZ SOZLAMALARI ==================
CHECKOUT_KASSA_ID = 46
CHECKOUT_SECRET_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"
CHECKOUT_BASE_URL = "https://checkout.uz/api"
WEBHOOK_BASE_URL = "https://shaxsiy-auto-to-lov-bot-production.up.railway.app"

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
            data = await resp.json()
            return data.get("record", {})

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

    if "users" not in data:
        data["users"] = []
        changed = True
    if "channels" not in data:
        data["channels"] = []
        changed = True
    if "ads" not in data:
        data["ads"] = []
        changed = True
    if "uc_prices" not in data:
        data["uc_prices"] = []
        changed = True
    if "uc_orders" not in data:
        data["uc_orders"] = []
        changed = True
    if "stars_prices" not in data:
        data["stars_prices"] = []
        changed = True
    if "stars_orders" not in data:
        data["stars_orders"] = []
        changed = True
    if "premium_prices" not in data:
        data["premium_prices"] = []
        changed = True
    if "premium_orders" not in data:
        data["premium_orders"] = []
        changed = True
    if "pending_payments" not in data:
        data["pending_payments"] = []
        changed = True
    if "settings" not in data:
        data["settings"] = {
            "price": "50000",
            "card": "8600 0000 0000 0000 (Ism Familiya)",
            "start_msg": "Salom {name}! Siz bu botdan PUBG Mobile akkauntingizni obzorini joylashingiz mumkin va u video kanalga joylanadi.",
            "site_url": "https://azizbekqiyomov55555-dev.github.io/Test-bot-"
        }
        changed = True
    if "next_id" not in data:
        data["next_id"] = 1
        changed = True

    if changed:
        await jb_write(data)

def get_next_id(data: dict) -> int:
    nid = data.get("next_id", 1)
    data["next_id"] = nid + 1
    return nid

# ================== CHECKOUT.UZ YORDAMCHI FUNKSIYALAR ==================

def generate_checkout_signature(params: dict, secret: str) -> str:
    """Checkout.uz uchun HMAC-SHA256 imzo generatsiya qilish"""
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    signature = hmac.new(
        secret.encode('utf-8'),
        sorted_params.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

async def create_checkout_payment(order_id: int, amount: int, description: str, user_id: int) -> dict:
    """Checkout.uz da to'lov yaratish"""
    params = {
        "kassa_id": CHECKOUT_KASSA_ID,
        "amount": amount,
        "currency": "UZS",
        "description": description,
        "order_id": str(order_id),
        "return_url": f"{WEBHOOK_BASE_URL}/payment_return/{user_id}",
        "callback_url": f"{WEBHOOK_BASE_URL}/webhook/checkout",
        "user_id": str(user_id),
    }
    params["sign"] = generate_checkout_signature(params, CHECKOUT_SECRET_KEY)

    url = f"{CHECKOUT_BASE_URL}/payment/create"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                result = await resp.json()
                return result
    except Exception as e:
        return {"error": str(e), "success": False}

def verify_checkout_webhook(data: dict, secret: str) -> bool:
    """Checkout.uz webhook imzosini tekshirish"""
    received_sign = data.get("sign", "")
    params_to_check = {k: v for k, v in data.items() if k != "sign"}
    expected_sign = generate_checkout_signature(params_to_check, secret)
    return received_sign == expected_sign

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

class PaymentForm(StatesGroup):
    receipt = State()

class SupportForm(StatesGroup):
    msg = State()

class AdminForm(StatesGroup):
    start_msg = State()
    price = State()
    card = State()
    add_channel_id = State()
    add_channel_url = State()
    reply_msg = State()
    uc_card = State()
    uc_price_amount = State()
    uc_price_value = State()
    main_card = State()
    stars_card = State()
    premium_card = State()
    stars_price_amount = State()
    stars_price_value = State()
    premium_price_duration = State()
    premium_price_value = State()

class UCOrderForm(StatesGroup):
    pubg_id_input = State()     # PUBG ID kiritish
    payment_choice = State()    # To'lov usulini tanlash (inline tugma kutadi)
    receipt = State()           # Manual to'lov cheki

class StarsOrderForm(StatesGroup):
    choose_target = State()
    friend_username = State()
    payment_choice = State()    # To'lov usulini tanlash
    receipt = State()           # Manual to'lov cheki

class PremiumOrderForm(StatesGroup):
    target_username = State()
    payment_choice = State()    # To'lov usulini tanlash
    receipt = State()           # Manual to'lov cheki

# ================== BOT VA ROUTER ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ================== YORDAMCHI FUNKSIYALAR ==================
def get_time_tashkent():
    tz = pytz.timezone('Asia/Tashkent')
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

async def get_setting(key):
    data = await jb_read()
    return data.get("settings", {}).get(key, "")

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

# ================== 2 TA TO'LOV TUGMASI HELPER ==================
def get_payment_choice_keyboard(auto_cb: str, manual_cb: str) -> InlineKeyboardMarkup:
    """Auto to'lov va Admin tasdiqlagan to'lov tugmalarini qaytaradi"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Auto to'lov", callback_data=auto_cb, style="success"),
            InlineKeyboardButton(text="👨‍💼 Admin tasdiqlagan to'lov", callback_data=manual_cb, style="primary"),
        ]
    ])

async def send_auto_payment_link(
    call: CallbackQuery,
    order_id: int,
    amount: int,
    description: str,
    fallback_cb: str,
    data: dict
):
    """Checkout.uz to'lov havolasini yuboradi, muvaffaqiyatsiz bo'lsa manual havolani ko'rsatadi"""
    await call.answer("⏳ To'lov havolasi yaratilmoqda...")

    result = await create_checkout_payment(
        order_id=order_id,
        amount=amount,
        description=description,
        user_id=call.from_user.id
    )

    pay_url = result.get("payment_url") or result.get("url") or result.get("redirect_url", "")
    if pay_url:
        btn = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💳 To'lovni amalga oshirish", url=pay_url, style="success")
        ]])
        try:
            await call.message.edit_text(
                f"💳 <b>Auto to'lov</b>\n\n"
                f"💰 Summa: <b>{amount:,} so'm</b>\n\n".replace(",", " ") +
                f"👇 Tugmani bosib to'lovni amalga oshiring.\n"
                f"To'lov tasdiqlangach bot <b>avtomatik xabar yuboradi</b>.",
                reply_markup=btn,
                parse_mode="HTML"
            )
        except:
            await call.message.answer(
                f"💳 <b>Auto to'lov</b>\n\n"
                f"💰 Summa: <b>{amount:,} so'm</b>\n\n".replace(",", " ") +
                f"👇 Tugmani bosib to'lovni amalga oshiring.\n"
                f"To'lov tasdiqlangach bot <b>avtomatik xabar yuboradi</b>.",
                reply_markup=btn,
                parse_mode="HTML"
            )
        return True
    else:
        # Checkout.uz ishlamasa — manual fallbackga yo'naltir
        card = data.get("settings", {}).get("card", "")
        btn = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📸 Chek yuborish", callback_data=fallback_cb, style="primary")
        ]])
        try:
            await call.message.edit_text(
                f"⚠️ <b>Auto to'lov hozir ishlamayapti.</b>\n\n"
                f"💳 Karta: <code>{card}</code>\n"
                f"💰 Summa: <b>{amount:,} so'm</b>\n\n".replace(",", " ") +
                f"To'lov qilgach chek rasmini yuboring.",
                reply_markup=btn,
                parse_mode="HTML"
            )
        except:
            await call.message.answer(
                f"⚠️ Auto to'lov ishlamayapti. Karta: <code>{card}</code>\nSumma: {amount:,} so'm".replace(",", " "),
                reply_markup=btn,
                parse_mode="HTML"
            )
        return False

# ================== ASOSIY MENU ==================
def get_main_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 E'lon berish"),
                KeyboardButton(text="🆘 Yordam")
            ],
            [
                KeyboardButton(text="🎮 PUBG MOBILE UC OLISH 💎")
            ],
            [
                KeyboardButton(text="⭐ TELEGRAM PREMIUM"),
                KeyboardButton(text="🌟 STARS OLISH")
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Quyidagi tugmalardan birini tanlang 👇"
    )
    return kb

# ================== ADMIN MENYU ==================
def get_admin_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="📝 Start xabar"),
            ],
            [
                KeyboardButton(text="💰 E'lon narxi"),
                KeyboardButton(text="💳 Karta"),
            ],
            [
                KeyboardButton(text="➕ Kanal qo'shish"),
                KeyboardButton(text="➖ Kanal o'chirish"),
            ],
            [
                KeyboardButton(text="💎 UC sozlamalari"),
                KeyboardButton(text="⭐ Stars sozlamalari"),
            ],
            [
                KeyboardButton(text="💜 Premium sozlamalari"),
                KeyboardButton(text="📦 Buyurtmalar"),
            ],
            [
                KeyboardButton(text="🔙 Asosiy menyu"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Admin panel 👇"
    )
    return kb

def get_uc_admin_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ UC narxi qo'shish"),
                KeyboardButton(text="📋 UC narxlari"),
            ],
            [
                KeyboardButton(text="📦 UC buyurtmalar"),
                KeyboardButton(text="🗑 UC narxlarini tozalash"),
            ],
            [KeyboardButton(text="🔙 Admin menyu")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
    return kb

def get_stars_admin_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Stars narxi qo'shish"),
                KeyboardButton(text="📋 Stars narxlari"),
            ],
            [
                KeyboardButton(text="📦 Stars buyurtmalar"),
                KeyboardButton(text="🗑 Stars narxlarini tozalash"),
            ],
            [KeyboardButton(text="🔙 Admin menyu")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
    return kb

def get_premium_admin_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Premium narxi qo'shish"),
                KeyboardButton(text="📋 Premium narxlari"),
            ],
            [
                KeyboardButton(text="📦 Premium buyurtmalar"),
                KeyboardButton(text="🗑 Premium narxlarini tozalash"),
            ],
            [KeyboardButton(text="🔙 Admin menyu")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
    return kb

def get_orders_admin_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📦 UC buyurtmalar"),
                KeyboardButton(text="📦 Stars buyurtmalar"),
            ],
            [
                KeyboardButton(text="📦 Premium buyurtmalar"),
            ],
            [KeyboardButton(text="🔙 Admin menyu")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
    return kb

# ================== UC NARXLARI INLINE KLAVIATURA ==================
def get_uc_prices_keyboard_from_data(prices, page=0):
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Hozircha narxlar kiritilmagan", callback_data="uc_no_prices")]
        ])

    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_prices = prices[start:end]

    rows = []
    for item in current_prices:
        rows.append([
            InlineKeyboardButton(
                text=f"💎 {item['uc_amount']} UC — {item['price']:,} so'm".replace(",", " "),
                callback_data=f"buy_uc_{item['id']}_{item['uc_amount']}_{item['price']}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"uc_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"uc_page_{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="uc_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_stars_prices_keyboard_from_data(prices, page=0):
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Hozircha narxlar kiritilmagan", callback_data="stars_no_prices")]
        ])

    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_prices = prices[start:end]

    rows = []
    for item in current_prices:
        rows.append([
            InlineKeyboardButton(
                text=f"⭐ {item['stars_amount']} Stars — {item['price']:,} so'm".replace(",", " "),
                callback_data=f"buy_stars_{item['id']}_{item['stars_amount']}_{item['price']}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"stars_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"stars_page_{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="stars_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_premium_prices_keyboard_from_data(prices, page=0):
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Hozircha narxlar kiritilmagan", callback_data="premium_no_prices")]
        ])

    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_prices = prices[start:end]

    rows = []
    for item in current_prices:
        rows.append([
            InlineKeyboardButton(
                text=f"⭐ {item['duration']} — {item['price']:,} so'm".replace(",", " "),
                callback_data=f"buy_premium_{item['id']}_{item['price']}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"premium_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"premium_page_{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="premium_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ================== START VA OBUNA ==================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()

    users = data.get("users", [])
    user_exists = any(u["user_id"] == message.from_user.id for u in users)
    if not user_exists:
        users.append({
            "user_id": message.from_user.id,
            "full_name": message.from_user.full_name,
            "username": message.from_user.username or "",
            "join_date": get_time_tashkent(),
            "posted_ads": 0,
            "paid_slots": 0,
            "pending_approval": 0,
            "free_ad_used": False   # Birinchi tekin e'lon ishlatilganmi?
        })
        data["users"] = users
        await jb_write(data)

    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 Kanal {i+1} — Obuna bo'lish", url=url)]
            for i, url in enumerate(unsubbed)
        ] + [[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]])
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=btn)
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
    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        await message.answer("Iltimos, oldin kanallarga obuna bo'ling. /start ni bosing.")
        return

    data = await jb_read()
    users = data.get("users", [])
    user = next((u for u in users if u["user_id"] == message.from_user.id), None)

    if not user:
        await message.answer("Iltimos, /start bosing.")
        return

    # Pending e'lon bormi?
    pending = user.get("pending_approval", 0)
    if pending:
        await message.answer(
            "⏳ Sizning oldingi e'loningiz admin tomonidan ko'rib chiqilmoqda.\n"
            "Admin tasdiqlaganidan so'ng yangi e'lon berishingiz mumkin."
        )
        return

    paid_slots = user.get("paid_slots", 0)
    free_ad_used = user.get("free_ad_used", False)

    # ✅ Agar to'langan slot bor bo'lsa
    if paid_slots > 0:
        await message.answer("✅ E'loningizni boshlaymiz.\nIltimos, akkaunt obzori videosini yuboring:")
        await state.set_state(AdForm.video)
        return

    # 🎁 Birinchi tekin e'lon
    if not free_ad_used:
        # Tekin birinchi e'lonni belgilab qo'yamiz
        for u in users:
            if u["user_id"] == message.from_user.id:
                u["free_ad_used"] = True
                break
        data["users"] = users
        await jb_write(data)

        await message.answer(
            "🎁 <b>Birinchi e'lon BEPUL!</b>\n\n"
            "Tabriklaymiz! Siz birinchi marta e'lon berayapsiz — bu BEPUL.\n"
            "Iltimos, akkaunt obzori videosini yuboring:",
            parse_mode="HTML"
        )
        await state.set_state(AdForm.video)
        return

    # 💰 To'lov kerak (ikkinchi va keyingi e'lonlar)
    price = data.get("settings", {}).get("price", "50000")
    try:
        price_int = int(price)
    except:
        price_int = 50000

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Auto to'lov", callback_data="pay_ad_auto", style="success"),
            InlineKeyboardButton(text="👨‍💼 Admin tasdiqlagan to'lov", callback_data="pay_ad_manual_start", style="primary"),
        ]
    ])
    await message.answer(
        f"📝 <b>E'lon joylash</b>\n\n"
        f"💰 E'lon narxi: <b>{price_int:,} so'm</b>\n\n".replace(",", " ") +
        f"To'lov usulini tanlang:\n\n"
        f"⚡ <b>Auto to'lov</b> — checkout.uz orqali avtomatik to'lov\n"
        f"👨‍💼 <b>Admin tasdiqlagan to'lov</b> — karta orqali to'lab chek yuborish",
        reply_markup=btn,
        parse_mode="HTML"
    )

@router.message(F.text == "🆘 Yordam")
async def menu_help_cb(message: Message, state: FSMContext):
    await message.answer("Adminga xabaringizni yozib qoldiring:")
    await state.set_state(SupportForm.msg)

# ================== AUTO TO'LOV (E'LON UCHUN) ==================
@router.callback_query(F.data == "pay_ad_auto")
async def pay_ad_auto_cb(call: CallbackQuery, state: FSMContext):
    data = await jb_read()
    price = data.get("settings", {}).get("price", "50000")
    try:
        price_int = int(price)
    except:
        price_int = 50000

    order_id = get_next_id(data)

    # Pending payment saqlash
    pending_payments = data.get("pending_payments", [])
    pending_payments.append({
        "id": order_id,
        "user_id": call.from_user.id,
        "full_name": call.from_user.full_name,
        "username": call.from_user.username or "—",
        "amount": price_int,
        "type": "ad",
        "status": "pending",
        "created_at": get_time_tashkent()
    })
    data["pending_payments"] = pending_payments
    await jb_write(data)

    await send_auto_payment_link(
        call=call,
        order_id=order_id,
        amount=price_int,
        description=f"E'lon joylash to'lovi #{order_id}",
        fallback_cb="pay_ad_manual_start",
        data=data
    )

# ================== ADMIN TASDIQLAGAN TO'LOV (E'LON UCHUN) ==================
@router.callback_query(F.data == "pay_ad_manual_start")
async def pay_ad_manual_start_cb(call: CallbackQuery, state: FSMContext):
    data = await jb_read()
    price = data.get("settings", {}).get("price", "50000")
    try:
        price_int = int(price)
    except:
        price_int = 50000
    card = data.get("settings", {}).get("card", "")

    await call.message.edit_text(
        f"👨‍💼 <b>Admin tasdiqlagan to'lov</b>\n\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"💰 Summa: <b>{price_int:,} so'm</b>\n\n".replace(",", " ") +
        f"To'lov qilgach <b>chek rasmini yuboring</b>:",
        parse_mode="HTML"
    )
    await state.set_state(PaymentForm.receipt)
    await call.answer()

@router.message(PaymentForm.receipt, F.photo)
async def get_ad_receipt(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_pay_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_pay_{message.from_user.id}")
    ]])
    await bot.send_photo(ADMIN_ID, photo_id,
        caption=f"💰 Yangi to'lov cheki (E'lon uchun).\n"
                f"Foydalanuvchi: {message.from_user.full_name} (@{message.from_user.username})\n"
                f"ID: {message.from_user.id}",
        reply_markup=btn)
    await message.answer("✅ Chek adminga yuborildi. Tasdiqlanishini kuting.", reply_markup=get_main_menu())
    await state.clear()

@router.message(PaymentForm.receipt)
async def get_ad_receipt_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>to'lov cheki rasmini</b> yuboring!", parse_mode="HTML")

# ================== CHECKOUT.UZ WEBHOOK ==================
async def handle_checkout_webhook(request: web.Request) -> web.Response:
    """Checkout.uz dan kelgan webhook"""
    try:
        body = await request.json()
    except:
        return web.Response(status=400, text="Invalid JSON")

    # Imzoni tekshirish
    if not verify_checkout_webhook(body, CHECKOUT_SECRET_KEY):
        return web.Response(status=403, text="Invalid signature")

    status = body.get("status")
    order_id_str = body.get("order_id", "")
    try:
        order_id = int(order_id_str)
    except:
        return web.Response(status=200, text="OK")

    if status in ("paid", "success", "completed"):
        data = await jb_read()
        pending_payments = data.get("pending_payments", [])
        payment = next((p for p in pending_payments if p["id"] == order_id), None)

        if payment and payment["status"] == "pending":
            user_id = payment["user_id"]
            payment_type = payment.get("type", "ad")
            payment["status"] = "approved"
            data["pending_payments"] = pending_payments
            now = get_time_tashkent()

            # ===== E'LON TO'LOVI =====
            if payment_type == "ad":
                users = data.get("users", [])
                for u in users:
                    if u["user_id"] == user_id:
                        u["paid_slots"] = u.get("paid_slots", 0) + 1
                        break
                data["users"] = users
                await jb_write(data)
                try:
                    await bot.send_message(
                        user_id,
                        "✅ <b>To'lovingiz qabul qilindi!</b>\n\n"
                        "Endi e'lon berishingiz mumkin.\n"
                        "👇 «📝 E'lon berish» tugmasini bosing.",
                        parse_mode="HTML",
                        reply_markup=get_main_menu()
                    )
                except Exception as e:
                    logging.error(f"Xabar yuborishda xato: {e}")

            # ===== UC TO'LOVI =====
            elif payment_type == "uc":
                uc_data = payment.get("order_data", {})
                uc_amount = uc_data.get("uc_amount", 0)
                pubg_id = uc_data.get("pubg_id", "—")
                price = uc_data.get("price", 0)
                full_name = payment.get("full_name", "")
                username = payment.get("username", "—")

                # Buyurtma yaratish
                order_db_id = get_next_id(data)
                orders = data.get("uc_orders", [])
                orders.append({
                    "id": order_db_id,
                    "user_id": user_id,
                    "full_name": full_name,
                    "username": username,
                    "uc_amount": uc_amount,
                    "price": price,
                    "pubg_id": pubg_id,
                    "screenshot_id": None,
                    "status": "payment_confirmed",
                    "payment_method": "auto",
                    "order_date": now
                })
                data["uc_orders"] = orders
                await jb_write(data)

                # Adminga xabar
                admin_text = (
                    f"🛒 <b>UC BUYURTMA — TO'LOV TASDIQLANDI!</b>\n\n"
                    f"👤 Foydalanuvchi: {full_name}\n"
                    f"🔗 Username: @{username}\n"
                    f"🆔 Telegram ID: <code>{user_id}</code>\n\n"
                    f"💎 UC miqdori: <b>{uc_amount} UC</b>\n"
                    f"💰 To'lov: <b>{price:,} so'm (AUTO TO'LOV ✅)</b>\n\n".replace(",", " ") +
                    f"🎮 PUBG ID: <code>{pubg_id}</code>\n"
                    f"📅 Vaqt: <b>{now}</b> (Toshkent)"
                )
                btn = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ UC Yuborildi", callback_data=f"uc_approve_{user_id}_{order_db_id}"),
                    InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"uc_reject_{user_id}_{order_db_id}")
                ]])
                try:
                    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=btn)
                except:
                    pass

                # Foydalanuvchiga xabar
                try:
                    await bot.send_message(
                        user_id,
                        f"✅ <b>To'lovingiz qabul qilindi!</b>\n\n"
                        f"💎 <b>{uc_amount} UC</b> tez orada profilingizga yuboriladi.\n"
                        f"🎮 PUBG ID: <code>{pubg_id}</code>\n\n"
                        f"⏳ Admin UC ni yuborishini kuting.",
                        parse_mode="HTML",
                        reply_markup=get_main_menu()
                    )
                except Exception as e:
                    logging.error(f"UC xabar xato: {e}")

            # ===== STARS TO'LOVI =====
            elif payment_type == "stars":
                stars_data = payment.get("order_data", {})
                stars_amount = stars_data.get("stars_amount", 0)
                stars_price = stars_data.get("price", 0)
                target_type = stars_data.get("target_type", "me")
                target_username = stars_data.get("target_username", "—")
                full_name = payment.get("full_name", "")
                username = payment.get("username", "—")

                order_db_id = get_next_id(data)
                orders = data.get("stars_orders", [])
                orders.append({
                    "id": order_db_id,
                    "user_id": user_id,
                    "full_name": full_name,
                    "username": username,
                    "stars_amount": stars_amount,
                    "price": stars_price,
                    "target_type": target_type,
                    "target_username": target_username,
                    "receipt_id": None,
                    "status": "payment_confirmed",
                    "payment_method": "auto",
                    "order_date": now
                })
                data["stars_orders"] = orders
                await jb_write(data)

                target_text = f"O'ziga (@{target_username})" if target_type == "me" else f"Do'stiga (@{target_username})"
                admin_text = (
                    f"⭐ <b>STARS BUYURTMA — TO'LOV TASDIQLANDI!</b>\n\n"
                    f"👤 Foydalanuvchi: {full_name}\n"
                    f"🔗 Username: @{username}\n"
                    f"🆔 ID: <code>{user_id}</code>\n\n"
                    f"⭐ Stars: <b>{stars_amount} Stars</b>\n"
                    f"💰 To'lov: <b>{stars_price:,} so'm (AUTO ✅)</b>\n\n".replace(",", " ") +
                    f"🎯 Kimga: <b>{target_text}</b>\n"
                    f"📅 Vaqt: <b>{now}</b>"
                )
                btn = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Stars Yuborildi", callback_data=f"stars_approve_{user_id}_{order_db_id}"),
                    InlineKeyboardButton(text="❌ Bekor", callback_data=f"stars_reject_{user_id}_{order_db_id}")
                ]])
                try:
                    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=btn)
                except:
                    pass

                try:
                    await bot.send_message(
                        user_id,
                        f"✅ <b>To'lovingiz qabul qilindi!</b>\n\n"
                        f"⭐ <b>{stars_amount} Stars</b> tez orada yuboriladi.\n"
                        f"🎯 Kimga: {target_text}\n\n"
                        f"⏳ Admin Stars ni yuborishini kuting.",
                        parse_mode="HTML",
                        reply_markup=get_main_menu()
                    )
                except Exception as e:
                    logging.error(f"Stars xabar xato: {e}")

            # ===== PREMIUM TO'LOVI =====
            elif payment_type == "premium":
                prem_data = payment.get("order_data", {})
                duration = prem_data.get("duration", "")
                prem_price = prem_data.get("price", 0)
                target_username = prem_data.get("target_username", "—")
                full_name = payment.get("full_name", "")
                username = payment.get("username", "—")

                order_db_id = get_next_id(data)
                orders = data.get("premium_orders", [])
                orders.append({
                    "id": order_db_id,
                    "user_id": user_id,
                    "full_name": full_name,
                    "username": username,
                    "duration": duration,
                    "price": prem_price,
                    "target_username": target_username,
                    "receipt_id": None,
                    "status": "payment_confirmed",
                    "payment_method": "auto",
                    "order_date": now
                })
                data["premium_orders"] = orders
                await jb_write(data)

                admin_text = (
                    f"⭐ <b>PREMIUM BUYURTMA — TO'LOV TASDIQLANDI!</b>\n\n"
                    f"👤 Foydalanuvchi: {full_name}\n"
                    f"🔗 Username: @{username}\n"
                    f"🆔 ID: <code>{user_id}</code>\n\n"
                    f"⭐ Muddat: <b>{duration}</b>\n"
                    f"💰 To'lov: <b>{prem_price:,} so'm (AUTO ✅)</b>\n\n".replace(",", " ") +
                    f"🎯 Profil: <code>@{target_username}</code>\n"
                    f"📅 Vaqt: <b>{now}</b>"
                )
                btn = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Premium Ulandi", callback_data=f"premium_approve_{user_id}_{order_db_id}"),
                    InlineKeyboardButton(text="❌ Bekor", callback_data=f"premium_reject_{user_id}_{order_db_id}")
                ]])
                try:
                    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=btn)
                except:
                    pass

                try:
                    await bot.send_message(
                        user_id,
                        f"✅ <b>To'lovingiz qabul qilindi!</b>\n\n"
                        f"⭐ <b>{duration}</b> Telegram Premium tez orada ulanadi.\n"
                        f"👤 Profil: <code>@{target_username}</code>\n\n"
                        f"⏳ Admin Premium ni ulashini kuting.",
                        parse_mode="HTML",
                        reply_markup=get_main_menu()
                    )
                except Exception as e:
                    logging.error(f"Premium xabar xato: {e}")

    return web.Response(status=200, text="OK")

async def handle_payment_return(request: web.Request) -> web.Response:
    """To'lov qaytish sahifasi"""
    return web.Response(
        text="<html><body><h2>✅ To'lov muvaffaqiyatli amalga oshirildi!</h2><p>Botga qaytib davom eting.</p></body></html>",
        content_type="text/html"
    )

# ================== E'LON FORMI ==================
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
            u["paid_slots"] = max(0, u.get("paid_slots", 0) - 1)
            break
    data["users"] = users
    await jb_write(data)

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_ad_{ad_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_ad_{ad_id}")
    ]])

    try:
        await bot.send_video(ADMIN_ID, video=st.get('video'),
            caption=f"📢 Yangi e'lon!\nFoydalanuvchi: {message.from_user.full_name} (ID: {message.from_user.id})\n\n{text}",
            reply_markup=btn, parse_mode="HTML")
    except:
        pass

    await message.answer("✅ E'loningiz adminga yuborildi. Tasdiqlanishini kuting.", reply_markup=get_main_menu())
    await state.clear()

# ================== 🎮 PUBG MOBILE UC OLISH ==================
@router.message(F.text == "🎮 PUBG MOBILE UC OLISH 💎")
async def uc_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    prices = sorted(data.get("uc_prices", []), key=lambda x: x.get("position", 0))

    text = (
        "🎮 <b>PUBG MOBILE UC OLISH</b>\n\n"
        "💎 Quyidagi narxlardan birini tanlang!\n"
        "⚡️ To'lov tasdiqlangandan so'ng UC tez yuboriladi.\n\n"
        "👇 UC miqdorini tanlang:"
    )
    await message.answer(text, reply_markup=get_uc_prices_keyboard_from_data(prices, 0), parse_mode="HTML")

@router.callback_query(F.data == "uc_no_prices")
async def uc_no_prices(call: CallbackQuery):
    await call.answer("Admin hali UC narxlarini kiritmagan!", show_alert=True)

@router.callback_query(F.data.startswith("uc_page_"))
async def uc_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    prices = sorted(data.get("uc_prices", []), key=lambda x: x.get("position", 0))
    try:
        await call.message.edit_reply_markup(reply_markup=get_uc_prices_keyboard_from_data(prices, page))
    except:
        pass
    await call.answer()

@router.callback_query(F.data == "uc_back")
async def uc_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_uc_"))
async def buy_uc_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    uc_amount = int(parts[3])
    price = int(parts[4])

    await state.update_data(uc_amount=uc_amount, uc_price=price)

    await call.message.edit_text(
        f"💎 <b>{uc_amount} UC — {price:,} so'm</b>\n\n".replace(",", " ") +
        f"🔢 <b>PUBG Mobile ID raqamingizni kiriting:</b>\n\n"
        f"<i>Profil → o'ng tepadagi ID raqami</i>",
        parse_mode="HTML"
    )
    await state.set_state(UCOrderForm.pubg_id_input)
    await call.answer()

@router.message(UCOrderForm.pubg_id_input, F.text)
async def get_pubg_id(message: Message, state: FSMContext):
    pubg_id = message.text.strip()
    await state.update_data(pubg_id=pubg_id)
    st = await state.get_data()
    uc_amount = st['uc_amount']
    price = st['uc_price']

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Auto to'lov", callback_data="uc_pay_auto"),
            InlineKeyboardButton(text="👨‍💼 Admin tasdiqlagan to'lov", callback_data="uc_pay_manual"),
        ]
    ])
    await message.answer(
        f"✅ <b>PUBG ID: <code>{pubg_id}</code></b>\n\n"
        f"💎 UC: <b>{uc_amount} UC</b>\n"
        f"💰 Summa: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"To'lov usulini tanlang:\n\n"
        f"⚡ <b>Auto to'lov</b> — checkout.uz orqali avtomatik\n"
        f"👨‍💼 <b>Admin tasdiqlagan</b> — karta orqali, chek yuborish",
        reply_markup=btn,
        parse_mode="HTML"
    )
    await state.set_state(UCOrderForm.payment_choice)

@router.message(UCOrderForm.pubg_id_input)
async def get_pubg_id_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>PUBG ID raqamingizni</b> matn ko'rinishida kiriting!", parse_mode="HTML")

# UC AUTO TO'LOV
@router.callback_query(F.data == "uc_pay_auto", UCOrderForm.payment_choice)
async def uc_pay_auto_cb(call: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    uc_amount = st['uc_amount']
    price = st['uc_price']
    pubg_id = st['pubg_id']

    data = await jb_read()
    order_id = get_next_id(data)

    pending_payments = data.get("pending_payments", [])
    pending_payments.append({
        "id": order_id,
        "user_id": call.from_user.id,
        "full_name": call.from_user.full_name,
        "username": call.from_user.username or "—",
        "amount": price,
        "type": "uc",
        "status": "pending",
        "created_at": get_time_tashkent(),
        "order_data": {
            "uc_amount": uc_amount,
            "pubg_id": pubg_id,
            "price": price
        }
    })
    data["pending_payments"] = pending_payments
    await jb_write(data)

    await send_auto_payment_link(
        call=call,
        order_id=order_id,
        amount=price,
        description=f"{uc_amount} UC PUBG ID:{pubg_id} #{order_id}",
        fallback_cb="uc_pay_manual",
        data=data
    )

# UC MANUAL TO'LOV
@router.callback_query(F.data == "uc_pay_manual", UCOrderForm.payment_choice)
async def uc_pay_manual_cb(call: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    uc_amount = st['uc_amount']
    price = st['uc_price']
    pubg_id = st['pubg_id']
    data = await jb_read()
    card = data.get("settings", {}).get("card", "")

    await call.message.edit_text(
        f"👨‍💼 <b>Admin tasdiqlagan to'lov</b>\n\n"
        f"💎 {uc_amount} UC | PUBG ID: <code>{pubg_id}</code>\n\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"💰 Summa: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"To'lov qilgach <b>chek rasmini yuboring</b>:",
        parse_mode="HTML"
    )
    await state.set_state(UCOrderForm.receipt)
    await call.answer()

@router.message(UCOrderForm.receipt, F.photo)
async def get_uc_receipt(message: Message, state: FSMContext):
    st = await state.get_data()
    receipt_id = message.photo[-1].file_id
    pubg_id = st.get('pubg_id', '—')
    uc_amount = st['uc_amount']
    price = st['uc_price']
    now = get_time_tashkent()

    data = await jb_read()
    order_id = get_next_id(data)
    orders = data.get("uc_orders", [])
    orders.append({
        "id": order_id,
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username or "—",
        "uc_amount": uc_amount,
        "price": price,
        "pubg_id": pubg_id,
        "screenshot_id": receipt_id,
        "status": "pending",
        "payment_method": "manual",
        "order_date": now
    })
    data["uc_orders"] = orders
    await jb_write(data)

    admin_text = (
        f"🛒 <b>YANGI UC BUYURTMA!</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🔗 Username: @{message.from_user.username or '—'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"💎 UC miqdori: <b>{uc_amount} UC</b>\n"
        f"💰 To'lov summasi: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"🎮 PUBG ID: <code>{pubg_id}</code>\n"
        f"📅 Vaqt: <b>{now}</b> (Toshkent)"
    )

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"uc_approve_{message.from_user.id}_{order_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"uc_reject_{message.from_user.id}_{order_id}")
    ]])

    await bot.send_photo(ADMIN_ID, photo=receipt_id, caption=admin_text, parse_mode="HTML", reply_markup=btn)
    await message.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"💎 <b>{uc_amount} UC</b> — {price:,} so'm\n\n".replace(",", " ") +
        f"⏳ Admin chekni ko'rib chiqib, UC ni tez orada yuboradi.\n"
        f"📞 Savollar bo'lsa: 🆘 Yordam tugmasini bosing.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    await state.clear()

@router.message(UCOrderForm.receipt)
async def get_uc_receipt_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>to'lov cheki rasmini</b> yuboring!", parse_mode="HTML")

# ================== ADMIN UC TASDIQLASH ==================
@router.callback_query(F.data.startswith("uc_approve_"))
async def uc_approve_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("uc_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "approved"
        data["uc_orders"] = orders
        await jb_write(data)
        await bot.send_message(
            user_id,
            f"🎉 <b>Tabriklaymiz! UC profilingizga tushdi!</b>\n\n"
            f"💎 <b>{order['uc_amount']} UC</b> akkauntingizga yuborildi!\n"
            f"O'yiningizni oching va UC ni tekshiring.\n\n"
            f"🙏 Xarid uchun rahmat!",
            parse_mode="HTML", reply_markup=get_main_menu()
        )

    caption = call.message.caption or call.message.text or ""
    try:
        if call.message.photo:
            await call.message.edit_caption(caption=caption + "\n\n✅ TASDIQLANDI — UC YUBORILDI", reply_markup=None)
        else:
            await call.message.edit_text(caption + "\n\n✅ TASDIQLANDI — UC YUBORILDI", reply_markup=None)
    except:
        pass
    await call.answer("✅ Buyurtma tasdiqlandi!", show_alert=True)

@router.callback_query(F.data.startswith("uc_reject_"))
async def uc_reject_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("uc_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "rejected"
        data["uc_orders"] = orders
        await jb_write(data)

    await bot.send_message(
        user_id,
        "❌ <b>Buyurtmangiz bekor qilindi.</b>\n\n"
        "To'lov cheki tasdiqlanmadi. Iltimos, qayta urinib ko'ring yoki "
        "🆘 Yordam orqali admin bilan bog'laning.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    caption = call.message.caption or call.message.text or ""
    try:
        if call.message.photo:
            await call.message.edit_caption(caption=caption + "\n\n❌ BEKOR QILINDI", reply_markup=None)
        else:
            await call.message.edit_text(caption + "\n\n❌ BEKOR QILINDI", reply_markup=None)
    except:
        pass
    await call.answer("❌ Buyurtma bekor qilindi.", show_alert=True)

# ================== 🌟 STARS OLISH ==================
@router.message(F.text == "🌟 STARS OLISH")
async def stars_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    prices = sorted(data.get("stars_prices", []), key=lambda x: x.get("position", 0))

    text = (
        "🌟 <b>TELEGRAM STARS OLISH</b>\n\n"
        "⭐ Quyidagi miqdorlardan birini tanlang!\n"
        "⚡️ To'lov tasdiqlangandan so'ng Stars tez yuboriladi.\n\n"
        "👇 Stars miqdorini tanlang:"
    )
    await message.answer(text, reply_markup=get_stars_prices_keyboard_from_data(prices, 0), parse_mode="HTML")

@router.callback_query(F.data == "stars_no_prices")
async def stars_no_prices(call: CallbackQuery):
    await call.answer("Admin hali Stars narxlarini kiritmagan!", show_alert=True)

@router.callback_query(F.data.startswith("stars_page_"))
async def stars_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    prices = sorted(data.get("stars_prices", []), key=lambda x: x.get("position", 0))
    try:
        await call.message.edit_reply_markup(reply_markup=get_stars_prices_keyboard_from_data(prices, page))
    except:
        pass
    await call.answer()

@router.callback_query(F.data == "stars_back")
async def stars_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_stars_"))
async def buy_stars_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    stars_amount = int(parts[3])
    price = int(parts[4])

    await state.update_data(stars_amount=stars_amount, stars_price=price)

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👤 O'ZIMGA", callback_data="stars_target_me"),
        InlineKeyboardButton(text="👫 DO'STIMGA", callback_data="stars_target_friend"),
    ]])

    await call.message.edit_text(
        f"⭐ <b>{stars_amount} Stars — {price:,} so'm</b>\n\nStars kimga kerak?".replace(",", " "),
        reply_markup=btn, parse_mode="HTML"
    )
    await state.set_state(StarsOrderForm.choose_target)
    await call.answer()

@router.callback_query(F.data == "stars_target_me", StarsOrderForm.choose_target)
async def stars_target_me(call: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = st['stars_price']
    await state.update_data(target_type="me", target_username=call.from_user.username or str(call.from_user.id))

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Auto to'lov", callback_data="stars_pay_auto"),
            InlineKeyboardButton(text="👨‍💼 Admin tasdiqlagan to'lov", callback_data="stars_pay_manual"),
        ]
    ])
    await call.message.edit_text(
        f"⭐ <b>{stars_amount} Stars — {price:,} so'm</b>\n".replace(",", " ") +
        f"👤 O'zingizga\n\n"
        f"To'lov usulini tanlang:\n\n"
        f"⚡ <b>Auto to'lov</b> — checkout.uz orqali avtomatik\n"
        f"👨‍💼 <b>Admin tasdiqlagan</b> — karta orqali, chek yuborish",
        reply_markup=btn, parse_mode="HTML"
    )
    await state.set_state(StarsOrderForm.payment_choice)
    await call.answer()

@router.callback_query(F.data == "stars_target_friend", StarsOrderForm.choose_target)
async def stars_target_friend(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "👫 <b>Do'stingizning Telegram username'ini kiriting:</b>\n\nMasalan: <code>@username</code>",
        parse_mode="HTML"
    )
    await state.set_state(StarsOrderForm.friend_username)
    await call.answer()

@router.message(StarsOrderForm.friend_username)
async def get_stars_friend_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    await state.update_data(target_type="friend", target_username=username)
    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = st['stars_price']

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Auto to'lov", callback_data="stars_pay_auto"),
            InlineKeyboardButton(text="👨‍💼 Admin tasdiqlagan to'lov", callback_data="stars_pay_manual"),
        ]
    ])
    await message.answer(
        f"⭐ <b>{stars_amount} Stars — {price:,} so'm</b>\n".replace(",", " ") +
        f"👫 Do'st: <code>@{username}</code>\n\n"
        f"To'lov usulini tanlang:\n\n"
        f"⚡ <b>Auto to'lov</b> — checkout.uz orqali avtomatik\n"
        f"👨‍💼 <b>Admin tasdiqlagan</b> — karta orqali, chek yuborish",
        reply_markup=btn, parse_mode="HTML"
    )
    await state.set_state(StarsOrderForm.payment_choice)

# STARS AUTO TO'LOV
@router.callback_query(F.data == "stars_pay_auto", StarsOrderForm.payment_choice)
async def stars_pay_auto_cb(call: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = st['stars_price']
    target_type = st.get('target_type', 'me')
    target_username = st.get('target_username', '—')

    data = await jb_read()
    order_id = get_next_id(data)

    pending_payments = data.get("pending_payments", [])
    pending_payments.append({
        "id": order_id,
        "user_id": call.from_user.id,
        "full_name": call.from_user.full_name,
        "username": call.from_user.username or "—",
        "amount": price,
        "type": "stars",
        "status": "pending",
        "created_at": get_time_tashkent(),
        "order_data": {
            "stars_amount": stars_amount,
            "price": price,
            "target_type": target_type,
            "target_username": target_username
        }
    })
    data["pending_payments"] = pending_payments
    await jb_write(data)

    await send_auto_payment_link(
        call=call,
        order_id=order_id,
        amount=price,
        description=f"{stars_amount} Stars @{target_username} #{order_id}",
        fallback_cb="stars_pay_manual",
        data=data
    )

# STARS MANUAL TO'LOV
@router.callback_query(F.data == "stars_pay_manual", StarsOrderForm.payment_choice)
async def stars_pay_manual_cb(call: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = st['stars_price']
    target_username = st.get('target_username', '—')
    data = await jb_read()
    card = data.get("settings", {}).get("card", "")

    await call.message.edit_text(
        f"👨‍💼 <b>Admin tasdiqlagan to'lov</b>\n\n"
        f"⭐ {stars_amount} Stars → <code>@{target_username}</code>\n\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"💰 Summa: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"To'lov qilgach <b>chek rasmini yuboring</b>:",
        parse_mode="HTML"
    )
    await state.set_state(StarsOrderForm.receipt)
    await call.answer()

@router.message(StarsOrderForm.receipt, F.photo)
async def get_stars_receipt(message: Message, state: FSMContext):
    st = await state.get_data()
    receipt_id = message.photo[-1].file_id
    stars_amount = st['stars_amount']
    price = st['stars_price']
    target_type = st.get('target_type', 'me')
    target_username = st.get('target_username', '—')
    now = get_time_tashkent()

    data = await jb_read()
    order_id = get_next_id(data)
    orders = data.get("stars_orders", [])
    orders.append({
        "id": order_id,
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username or "—",
        "stars_amount": stars_amount,
        "price": price,
        "target_type": target_type,
        "target_username": target_username,
        "receipt_id": receipt_id,
        "status": "pending",
        "payment_method": "manual",
        "order_date": now
    })
    data["stars_orders"] = orders
    await jb_write(data)

    target_text = f"O'ziga (@{target_username})" if target_type == "me" else f"Do'stiga (@{target_username})"
    admin_text = (
        f"⭐ <b>YANGI STARS BUYURTMA!</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🔗 Username: @{message.from_user.username or '—'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"⭐ Stars miqdori: <b>{stars_amount} Stars</b>\n"
        f"💰 To'lov summasi: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"🎯 Kimga: <b>{target_text}</b>\n"
        f"📅 Vaqt: <b>{now}</b> (Toshkent)"
    )

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"stars_approve_{message.from_user.id}_{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"stars_reject_{message.from_user.id}_{order_id}"),
        ],
        [InlineKeyboardButton(text="👤 Foydalanuvchiga o'tish", url=f"tg://user?id={message.from_user.id}")]
    ])

    await bot.send_photo(ADMIN_ID, photo=receipt_id, caption=admin_text, parse_mode="HTML", reply_markup=btn)
    await message.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"⭐ <b>{stars_amount} Stars</b> — {price:,} so'm\n\n".replace(",", " ") +
        f"⏳ Admin chekni ko'rib chiqadi va Stars tez orada yuboriladi.\n"
        f"📞 Savollar bo'lsa: 🆘 Yordam tugmasini bosing.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    await state.clear()

@router.message(StarsOrderForm.receipt)
async def get_stars_receipt_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>to'lov cheki rasmini</b> yuboring!", parse_mode="HTML")

# ================== ADMIN STARS TASDIQLASH ==================
@router.callback_query(F.data.startswith("stars_approve_"))
async def stars_approve_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("stars_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "approved"
        data["stars_orders"] = orders
        await jb_write(data)
        await bot.send_message(
            user_id,
            f"🎉 <b>Tabriklaymiz! Stars profilingizga tushdi!</b>\n\n"
            f"⭐ <b>{order['stars_amount']} Stars</b> yuborildi!\n\n"
            f"🙏 Xarid uchun rahmat!",
            parse_mode="HTML", reply_markup=get_main_menu()
        )

    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n✅ TASDIQLANDI — STARS YUBORILDI", reply_markup=None)
    except:
        pass
    await call.answer("✅ Stars buyurtma tasdiqlandi!", show_alert=True)

@router.callback_query(F.data.startswith("stars_reject_"))
async def stars_reject_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("stars_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "rejected"
        data["stars_orders"] = orders
        await jb_write(data)

    await bot.send_message(
        user_id,
        "❌ <b>Buyurtmangiz bekor qilindi.</b>\n\n"
        "🆘 Yordam orqali admin bilan bog'laning.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n❌ BEKOR QILINDI", reply_markup=None)
    except:
        pass
    await call.answer("❌ Stars buyurtma bekor qilindi.", show_alert=True)

# ================== ⭐ TELEGRAM PREMIUM ==================
@router.message(F.text == "⭐ TELEGRAM PREMIUM")
async def premium_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    prices = sorted(data.get("premium_prices", []), key=lambda x: x.get("price", 0))

    text = (
        "⭐ <b>TELEGRAM PREMIUM OLISH</b>\n\n"
        "🚀 Premium obuna bilan Telegram'ni to'liq imkoniyatlaridan foydalaning!\n"
        "⚡️ To'lov tasdiqlangandan so'ng Premium tez ulanadi.\n\n"
        "👇 Muddat tanlang:"
    )
    await message.answer(text, reply_markup=get_premium_prices_keyboard_from_data(prices, 0), parse_mode="HTML")

@router.callback_query(F.data == "premium_no_prices")
async def premium_no_prices(call: CallbackQuery):
    await call.answer("Admin hali Premium narxlarini kiritmagan!", show_alert=True)

@router.callback_query(F.data.startswith("premium_page_"))
async def premium_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    prices = sorted(data.get("premium_prices", []), key=lambda x: x.get("price", 0))
    try:
        await call.message.edit_reply_markup(reply_markup=get_premium_prices_keyboard_from_data(prices, page))
    except:
        pass
    await call.answer()

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
    prices = data.get("premium_prices", [])
    row = next((p for p in prices if p["id"] == pid), None)
    duration = row["duration"] if row else "Noma'lum"

    await state.update_data(premium_pid=pid, premium_price=price, premium_duration=duration)

    await call.message.edit_text(
        f"⭐ <b>{duration} — {price:,} so'm</b>\n\n".replace(",", " ") +
        f"Premium tushirilsinchi profil username'ini kiriting:\n\nMasalan: <code>@username</code>",
        parse_mode="HTML"
    )
    await state.set_state(PremiumOrderForm.target_username)
    await call.answer()

@router.message(PremiumOrderForm.target_username)
async def get_premium_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    await state.update_data(target_username=username)
    st = await state.get_data()
    price = st['premium_price']
    duration = st['premium_duration']

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Auto to'lov", callback_data="premium_pay_auto"),
            InlineKeyboardButton(text="👨‍💼 Admin tasdiqlagan to'lov", callback_data="premium_pay_manual"),
        ]
    ])
    await message.answer(
        f"⭐ <b>{duration} — {price:,} so'm</b>\n".replace(",", " ") +
        f"👤 Profil: <code>@{username}</code>\n\n"
        f"To'lov usulini tanlang:\n\n"
        f"⚡ <b>Auto to'lov</b> — checkout.uz orqali avtomatik\n"
        f"👨‍💼 <b>Admin tasdiqlagan</b> — karta orqali, chek yuborish",
        reply_markup=btn, parse_mode="HTML"
    )
    await state.set_state(PremiumOrderForm.payment_choice)

# PREMIUM AUTO TO'LOV
@router.callback_query(F.data == "premium_pay_auto", PremiumOrderForm.payment_choice)
async def premium_pay_auto_cb(call: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    price = st['premium_price']
    duration = st['premium_duration']
    target_username = st.get('target_username', '—')

    data = await jb_read()
    order_id = get_next_id(data)

    pending_payments = data.get("pending_payments", [])
    pending_payments.append({
        "id": order_id,
        "user_id": call.from_user.id,
        "full_name": call.from_user.full_name,
        "username": call.from_user.username or "—",
        "amount": price,
        "type": "premium",
        "status": "pending",
        "created_at": get_time_tashkent(),
        "order_data": {
            "duration": duration,
            "price": price,
            "target_username": target_username
        }
    })
    data["pending_payments"] = pending_payments
    await jb_write(data)

    await send_auto_payment_link(
        call=call,
        order_id=order_id,
        amount=price,
        description=f"Premium {duration} @{target_username} #{order_id}",
        fallback_cb="premium_pay_manual",
        data=data
    )

# PREMIUM MANUAL TO'LOV
@router.callback_query(F.data == "premium_pay_manual", PremiumOrderForm.payment_choice)
async def premium_pay_manual_cb(call: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    price = st['premium_price']
    duration = st['premium_duration']
    target_username = st.get('target_username', '—')
    data = await jb_read()
    card = data.get("settings", {}).get("card", "")

    await call.message.edit_text(
        f"👨‍💼 <b>Admin tasdiqlagan to'lov</b>\n\n"
        f"⭐ {duration} → <code>@{target_username}</code>\n\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"💰 Summa: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"To'lov qilgach <b>chek rasmini yuboring</b>:",
        parse_mode="HTML"
    )
    await state.set_state(PremiumOrderForm.receipt)
    await call.answer()

@router.message(PremiumOrderForm.receipt, F.photo)
async def get_premium_receipt(message: Message, state: FSMContext):
    st = await state.get_data()
    receipt_id = message.photo[-1].file_id
    price = st['premium_price']
    duration = st['premium_duration']
    target_username = st.get('target_username', '—')
    now = get_time_tashkent()

    data = await jb_read()
    order_id = get_next_id(data)
    orders = data.get("premium_orders", [])
    orders.append({
        "id": order_id,
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username or "—",
        "duration": duration,
        "price": price,
        "target_username": target_username,
        "receipt_id": receipt_id,
        "status": "pending",
        "payment_method": "manual",
        "order_date": now
    })
    data["premium_orders"] = orders
    await jb_write(data)

    admin_text = (
        f"⭐ <b>YANGI PREMIUM BUYURTMA!</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🔗 Username: @{message.from_user.username or '—'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"⭐ Premium muddati: <b>{duration}</b>\n"
        f"💰 To'lov summasi: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"🎯 Premium tushiriladigan profil: <code>@{target_username}</code>\n"
        f"📅 Vaqt: <b>{now}</b> (Toshkent)"
    )

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"premium_approve_{message.from_user.id}_{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"premium_reject_{message.from_user.id}_{order_id}"),
        ],
        [InlineKeyboardButton(text="👤 Foydalanuvchiga o'tish", url=f"tg://user?id={message.from_user.id}")]
    ])

    await bot.send_photo(ADMIN_ID, photo=receipt_id, caption=admin_text, parse_mode="HTML", reply_markup=btn)
    await message.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"⭐ <b>{duration}</b> Telegram Premium\n"
        f"💰 {price:,} so'm\n\n".replace(",", " ") +
        f"⏳ Admin chekni ko'rib chiqadi va Premium tez orada ulanadi.\n"
        f"📞 Savollar bo'lsa: 🆘 Yordam tugmasini bosing.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    await state.clear()

@router.message(PremiumOrderForm.receipt)
async def get_premium_receipt_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>to'lov cheki rasmini</b> yuboring!", parse_mode="HTML")

# ================== ADMIN PREMIUM TASDIQLASH ==================
@router.callback_query(F.data.startswith("premium_approve_"))
async def premium_approve_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("premium_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "approved"
        data["premium_orders"] = orders
        await jb_write(data)
        await bot.send_message(
            user_id,
            f"🎉 <b>Tabriklaymiz! Telegram Premium ulandi!</b>\n\n"
            f"⭐ <b>{order['duration']}</b> Premium obuna\n"
            f"👤 Profil: <code>@{order['target_username']}</code>\n\n"
            f"🙏 Xarid uchun rahmat!",
            parse_mode="HTML", reply_markup=get_main_menu()
        )

    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n✅ TASDIQLANDI — PREMIUM ULANDI", reply_markup=None)
    except:
        pass
    await call.answer("✅ Premium buyurtma tasdiqlandi!", show_alert=True)

@router.callback_query(F.data.startswith("premium_reject_"))
async def premium_reject_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("premium_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "rejected"
        data["premium_orders"] = orders
        await jb_write(data)

    await bot.send_message(
        user_id,
        "❌ <b>Buyurtmangiz bekor qilindi.</b>\n\n"
        "🆘 Yordam orqali admin bilan bog'laning.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n❌ BEKOR QILINDI", reply_markup=None)
    except:
        pass
    await call.answer("❌ Premium buyurtma bekor qilindi.", show_alert=True)

# ================== SUPPORT ==================
@router.message(SupportForm.msg)
async def get_support_msg(message: Message, state: FSMContext):
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Javob berish", callback_data=f"reply_{message.from_user.id}")
    ]])
    await bot.send_message(ADMIN_ID,
        f"📩 Yangi xabar!\n"
        f"Kimdan: {message.from_user.full_name} (ID: {message.from_user.id})\n\n"
        f"Xabar: {message.text}",
        reply_markup=btn)
    await message.answer("Xabaringiz adminga yetkazildi.", reply_markup=get_main_menu())
    await state.clear()

# ================== ADMIN TO'LOV MANUAL TASDIQLASH (E'LON) ==================
@router.callback_query(F.data.startswith("app_pay_"))
async def approve_pay(call: CallbackQuery):
    user_id = int(call.data.split("_")[2])
    data = await jb_read()
    users = data.get("users", [])
    for u in users:
        if u["user_id"] == user_id:
            u["paid_slots"] = u.get("paid_slots", 0) + 1
            break
    data["users"] = users
    await jb_write(data)
    await bot.send_message(
        user_id,
        "✅ <b>To'lovingiz tasdiqlandi!</b>\n\n"
        "Endi e'lon joylashingiz mumkin.\n"
        "👇 «📝 E'lon berish» tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    try:
        await call.message.edit_caption(caption=call.message.caption + "\n\n✅ TASDIQLANGAN")
    except:
        pass

@router.callback_query(F.data.startswith("rej_pay_"))
async def reject_pay(call: CallbackQuery):
    user_id = int(call.data.split("_")[2])
    await bot.send_message(user_id, "❌ To'lovingiz admin tomonidan bekor qilindi.", reply_markup=get_main_menu())
    try:
        await call.message.edit_caption(caption=call.message.caption + "\n\n❌ BEKOR QILINGAN")
    except:
        pass

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

    colors = ["primary", "success", "danger"]
    c1 = colors[ad_id % 3]
    c2 = colors[(ad_id + 1) % 3]

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Sotuvchi bilan aloqa", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton(text="📢 Reklama berish", url=f"https://t.me/{me.username}?start=ad")]
    ])

    try:
        await bot.send_video(MAIN_CHANNEL_ID, video=ad["video_id"], caption=ad["text"], reply_markup=btn, parse_mode="HTML")
    except Exception as e:
        await call.answer(f"❌ Kanalga yuborishda XATO:\n{e}", show_alert=True)
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

    try:
        await bot.send_message(
            user_id,
            "✅ <b>E'loningiz kanalga joylandi!</b>\n\n"
            "Yana e'lon joylashingiz mumkin.\n"
            "👇 «📝 E'lon berish» tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    except:
        pass

    old_caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=old_caption + "\n\n✅ KANALGA JOYLANDI", reply_markup=None)
    except:
        pass
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

    try:
        await bot.send_message(user_id, "❌ E'loningiz admin tomonidan rad etildi.", reply_markup=get_main_menu())
    except:
        pass

    old_caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=old_caption + "\n\n❌ BEKOR QILINGAN", reply_markup=None)
    except:
        pass
    await call.answer("❌ E'lon bekor qilindi.", show_alert=True)

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

# ================== ADMIN PANEL ==================
@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel_cmd(message: Message):
    await message.answer("⚙️ Admin panelga xush kelibsiz!", reply_markup=get_admin_menu())

@router.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def admin_stats_btn(message: Message):
    data = await jb_read()
    users = data.get("users", [])
    uc_orders = data.get("uc_orders", [])
    stars_orders = data.get("stars_orders", [])
    premium_orders = data.get("premium_orders", [])
    ads = data.get("ads", [])
    uc_approved = sum(1 for o in uc_orders if o.get("status") == "approved")
    ads_approved = sum(1 for a in ads if a.get("status") == "approved")
    text = (
        f"📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: <b>{len(users)} ta</b>\n"
        f"📝 Jami e'lonlar: <b>{len(ads)} ta</b> (tasdiqlangan: {ads_approved})\n"
        f"💎 UC buyurtmalar: <b>{len(uc_orders)} ta</b> (tasdiqlangan: {uc_approved})\n"
        f"⭐ Stars buyurtmalar: <b>{len(stars_orders)} ta</b>\n"
        f"🎖 Premium buyurtmalar: <b>{len(premium_orders)} ta</b>\n"
        f"🕐 Vaqt: {get_time_tashkent()}"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📝 Start xabar", F.from_user.id == ADMIN_ID)
async def admin_startmsg_btn(message: Message, state: FSMContext):
    await message.answer("Yangi start xabarini kiriting. ({name} — foydalanuvchi ismi):")
    await state.set_state(AdminForm.start_msg)

@router.message(AdminForm.start_msg)
async def save_start(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["start_msg"] = message.text
    await jb_write(data)
    await message.answer("✅ Start xabar yangilandi!", reply_markup=get_admin_menu())
    await state.clear()

@router.message(F.text == "💰 E'lon narxi", F.from_user.id == ADMIN_ID)
async def admin_price_btn(message: Message, state: FSMContext):
    await message.answer("Yangi e'lon narxini kiriting (faqat raqam, so'mda):")
    await state.set_state(AdminForm.price)

@router.message(AdminForm.price)
async def save_price(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["price"] = message.text
    await jb_write(data)
    await message.answer(f"✅ E'lon narxi yangilandi: {message.text} so'm", reply_markup=get_admin_menu())
    await state.clear()

@router.message(F.text == "💳 Karta", F.from_user.id == ADMIN_ID)
async def admin_card_btn(message: Message, state: FSMContext):
    await message.answer("Yangi karta raqamini kiriting:")
    await state.set_state(AdminForm.card)

@router.message(AdminForm.card)
async def save_card(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["card"] = message.text
    await jb_write(data)
    await message.answer("✅ Karta yangilandi!", reply_markup=get_admin_menu())
    await state.clear()

@router.message(F.text == "➕ Kanal qo'shish", F.from_user.id == ADMIN_ID)
async def add_ch_btn(message: Message, state: FSMContext):
    await message.answer("Kanal ID sini kiriting (masalan: @kanal_useri yoki -100123...):")
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
    await message.answer("✅ Kanal qo'shildi!", reply_markup=get_admin_menu())
    await state.clear()

@router.message(F.text == "➖ Kanal o'chirish", F.from_user.id == ADMIN_ID)
async def del_ch_btn(message: Message):
    data = await jb_read()
    channels = data.get("channels", [])
    if not channels:
        await message.answer("Kanallar yo'q.")
        return
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 O'chirish: {ch['channel_id']}", callback_data=f"delch_{ch['id']}")]
        for ch in channels
    ])
    await message.answer("Qaysi kanalni o'chirasiz?", reply_markup=btn)

@router.callback_query(F.data.startswith("delch_"))
async def del_ch_action(call: CallbackQuery):
    c_id = int(call.data.split("_")[1])
    data = await jb_read()
    data["channels"] = [c for c in data.get("channels", []) if c["id"] != c_id]
    await jb_write(data)
    await call.message.edit_text("✅ Kanal o'chirildi.")

# ================== UC SOZLAMALARI ==================
@router.message(F.text == "💎 UC sozlamalari", F.from_user.id == ADMIN_ID)
async def uc_settings_btn(message: Message):
    await message.answer("💎 UC sozlamalari:", reply_markup=get_uc_admin_menu())

@router.message(F.text == "➕ UC narxi qo'shish", F.from_user.id == ADMIN_ID)
async def add_uc_price_btn(message: Message, state: FSMContext):
    await message.answer("💎 <b>UC miqdorini kiriting</b>\n\nMasalan: <code>60</code>", parse_mode="HTML")
    await state.set_state(AdminForm.uc_price_amount)

@router.message(AdminForm.uc_price_amount)
async def add_uc_price_step2(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    await state.update_data(uc_amount=int(message.text))
    await message.answer(f"💰 <b>{message.text} UC narxini kiriting (so'mda)</b>", parse_mode="HTML")
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
        await message.answer(f"✅ <b>{uc_amount} UC</b> narxi yangilandi: <b>{price:,} so'm</b>".replace(",", " "), parse_mode="HTML", reply_markup=get_uc_admin_menu())
    else:
        nid = get_next_id(data)
        prices.append({"id": nid, "uc_amount": uc_amount, "price": price, "position": 0})
        await message.answer(f"✅ <b>{uc_amount} UC — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML", reply_markup=get_uc_admin_menu())
    data["uc_prices"] = prices
    await jb_write(data)
    await state.clear()

@router.message(F.text == "📋 UC narxlari", F.from_user.id == ADMIN_ID)
async def admin_uc_list_btn(message: Message):
    data = await jb_read()
    prices = sorted(data.get("uc_prices", []), key=lambda x: x.get("uc_amount", 0))
    if not prices:
        await message.answer("❌ Hozircha UC narxlari kiritilmagan.")
        return
    text = "💎 <b>UC NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
    rows = []
    for item in prices:
        text += f"• {item['uc_amount']} UC — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([
            InlineKeyboardButton(text=f"💎 {item['uc_amount']} UC — {item['price']:,} so'm".replace(",", " "), callback_data="uc_info"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_uc_price_{item['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="close_list")])
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.message(F.text == "📦 UC buyurtmalar", F.from_user.id == ADMIN_ID)
async def admin_uc_orders_btn(message: Message):
    data = await jb_read()
    orders = sorted(data.get("uc_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]
    if not orders:
        await message.answer("📦 Hozircha UC buyurtmalar yo'q.")
        return
    text = "📦 <b>OXIRGI 20 UC BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "approved" else "❌")
        method = "🤖" if o.get("payment_method") == "auto" else "👤"
        text += f"{emoji}{method} #{o['id']} | {o['full_name']} | {o['uc_amount']} UC | {o['price']:,} so'm | {o['order_date']}\n".replace(",", " ")
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🗑 UC narxlarini tozalash", F.from_user.id == ADMIN_ID)
async def admin_clear_uc_btn(message: Message):
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="confirm_clear_uc"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="close_list"),
    ]])
    await message.answer("⚠️ <b>Barcha UC narxlarini o'chirasizmi?</b>", parse_mode="HTML", reply_markup=btn)

# ================== STARS SOZLAMALARI ==================
@router.message(F.text == "⭐ Stars sozlamalari", F.from_user.id == ADMIN_ID)
async def stars_settings_btn(message: Message):
    await message.answer("⭐ Stars sozlamalari:", reply_markup=get_stars_admin_menu())

@router.message(F.text == "➕ Stars narxi qo'shish", F.from_user.id == ADMIN_ID)
async def add_stars_price_btn(message: Message, state: FSMContext):
    await message.answer("⭐ <b>Stars miqdorini kiriting</b>\n\nMasalan: <code>50</code>", parse_mode="HTML")
    await state.set_state(AdminForm.stars_price_amount)

@router.message(AdminForm.stars_price_amount)
async def add_stars_price_step2(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    await state.update_data(stars_amount=int(message.text))
    await message.answer(f"💰 <b>{message.text} Stars narxini kiriting (so'mda)</b>", parse_mode="HTML")
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
        await message.answer(f"✅ <b>{stars_amount} Stars</b> narxi yangilandi: <b>{price:,} so'm</b>".replace(",", " "), parse_mode="HTML", reply_markup=get_stars_admin_menu())
    else:
        nid = get_next_id(data)
        prices.append({"id": nid, "stars_amount": stars_amount, "price": price, "position": 0})
        await message.answer(f"✅ <b>{stars_amount} Stars — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML", reply_markup=get_stars_admin_menu())
    data["stars_prices"] = prices
    await jb_write(data)
    await state.clear()

@router.message(F.text == "📋 Stars narxlari", F.from_user.id == ADMIN_ID)
async def admin_stars_list_btn(message: Message):
    data = await jb_read()
    prices = sorted(data.get("stars_prices", []), key=lambda x: x.get("stars_amount", 0))
    if not prices:
        await message.answer("❌ Hozircha Stars narxlari kiritilmagan.")
        return
    text = "⭐ <b>STARS NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
    rows = []
    for item in prices:
        text += f"• {item['stars_amount']} Stars — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([
            InlineKeyboardButton(text=f"⭐ {item['stars_amount']} Stars — {item['price']:,} so'm".replace(",", " "), callback_data="stars_info"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_stars_price_{item['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="close_list")])
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.message(F.text == "📦 Stars buyurtmalar", F.from_user.id == ADMIN_ID)
async def admin_stars_orders_btn(message: Message):
    data = await jb_read()
    orders = sorted(data.get("stars_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]
    if not orders:
        await message.answer("⭐ Hozircha Stars buyurtmalar yo'q.")
        return
    text = "⭐ <b>OXIRGI 20 STARS BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "approved" else "❌")
        method = "🤖" if o.get("payment_method") == "auto" else "👤"
        text += f"{emoji}{method} #{o['id']} | {o['full_name']} | {o['stars_amount']} Stars | @{o['target_username']} | {o['order_date']}\n"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🗑 Stars narxlarini tozalash", F.from_user.id == ADMIN_ID)
async def admin_clear_stars_btn(message: Message):
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="confirm_clear_stars"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="close_list"),
    ]])
    await message.answer("⚠️ <b>Barcha Stars narxlarini o'chirasizmi?</b>", parse_mode="HTML", reply_markup=btn)

# ================== PREMIUM SOZLAMALARI ==================
@router.message(F.text == "💜 Premium sozlamalari", F.from_user.id == ADMIN_ID)
async def premium_settings_btn(message: Message):
    await message.answer("💜 Premium sozlamalari:", reply_markup=get_premium_admin_menu())

@router.message(F.text == "➕ Premium narxi qo'shish", F.from_user.id == ADMIN_ID)
async def add_premium_price_btn(message: Message, state: FSMContext):
    await message.answer("⭐ <b>Premium muddatini kiriting</b>\n\nMasalan: <code>1 oylik</code>", parse_mode="HTML")
    await state.set_state(AdminForm.premium_price_duration)

@router.message(AdminForm.premium_price_duration)
async def add_premium_price_step2(message: Message, state: FSMContext):
    await state.update_data(premium_duration=message.text)
    await message.answer(f"💰 <b>«{message.text}» narxini kiriting (so'mda)</b>", parse_mode="HTML")
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
    await message.answer(f"✅ <b>{duration} — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML", reply_markup=get_premium_admin_menu())
    await state.clear()

@router.message(F.text == "📋 Premium narxlari", F.from_user.id == ADMIN_ID)
async def admin_premium_list_btn(message: Message):
    data = await jb_read()
    prices = sorted(data.get("premium_prices", []), key=lambda x: x.get("price", 0))
    if not prices:
        await message.answer("❌ Hozircha Premium narxlari kiritilmagan.")
        return
    text = "💜 <b>PREMIUM NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
    rows = []
    for item in prices:
        text += f"• {item['duration']} — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([
            InlineKeyboardButton(text=f"💜 {item['duration']} — {item['price']:,} so'm".replace(",", " "), callback_data="premium_info"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_premium_price_{item['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="close_list")])
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.message(F.text == "📦 Premium buyurtmalar", F.from_user.id == ADMIN_ID)
async def admin_premium_orders_btn(message: Message):
    data = await jb_read()
    orders = sorted(data.get("premium_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]
    if not orders:
        await message.answer("⭐ Hozircha Premium buyurtmalar yo'q.")
        return
    text = "⭐ <b>OXIRGI 20 PREMIUM BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "approved" else "❌")
        method = "🤖" if o.get("payment_method") == "auto" else "👤"
        text += f"{emoji}{method} #{o['id']} | {o['full_name']} | {o['duration']} | @{o['target_username']} | {o['order_date']}\n"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🗑 Premium narxlarini tozalash", F.from_user.id == ADMIN_ID)
async def admin_clear_premium_btn(message: Message):
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="confirm_clear_premium"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="close_list"),
    ]])
    await message.answer("⚠️ <b>Barcha Premium narxlarini o'chirasizmi?</b>", parse_mode="HTML", reply_markup=btn)

@router.message(F.text == "📦 Buyurtmalar", F.from_user.id == ADMIN_ID)
async def admin_orders_btn(message: Message):
    await message.answer("📦 Buyurtmalar bo'limi:", reply_markup=get_orders_admin_menu())

@router.message(F.text == "🔙 Admin menyu", F.from_user.id == ADMIN_ID)
async def back_to_admin_menu(message: Message):
    await message.answer("⚙️ Admin panel:", reply_markup=get_admin_menu())

@router.message(F.text == "🔙 Asosiy menyu", F.from_user.id == ADMIN_ID)
async def back_to_main_menu(message: Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu())

# ================== INLINE CALLBACK HANDLERLAR ==================
@router.callback_query(F.data == "close_list")
async def close_list_cb(call: CallbackQuery):
    try:
        await call.message.delete()
    except:
        pass
    await call.answer()

@router.callback_query(F.data == "uc_info")
async def uc_info_cb(call: CallbackQuery):
    await call.answer()

@router.callback_query(F.data == "stars_info")
async def stars_info_cb(call: CallbackQuery):
    await call.answer()

@router.callback_query(F.data == "premium_info")
async def premium_info_cb(call: CallbackQuery):
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
        new_prices = sorted(data["uc_prices"], key=lambda x: x.get("uc_amount", 0))
        if not new_prices:
            try:
                await call.message.edit_text("❌ Barcha UC narxlari o'chirildi.")
            except:
                pass
            return
        text = "💎 <b>UC NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
        rows = []
        for p in new_prices:
            text += f"• {p['uc_amount']} UC — {p['price']:,} so'm\n".replace(",", " ")
            rows.append([
                InlineKeyboardButton(text=f"💎 {p['uc_amount']} UC — {p['price']:,} so'm".replace(",", " "), callback_data="uc_info"),
                InlineKeyboardButton(text="🗑", callback_data=f"del_uc_price_{p['id']}"),
            ])
        rows.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="close_list")])
        try:
            await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        except:
            pass
    else:
        await call.answer("Topilmadi!", show_alert=True)

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
        new_prices = sorted(data["stars_prices"], key=lambda x: x.get("stars_amount", 0))
        if not new_prices:
            try:
                await call.message.edit_text("❌ Barcha Stars narxlari o'chirildi.")
            except:
                pass
            return
        text = "⭐ <b>STARS NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
        rows = []
        for p in new_prices:
            text += f"• {p['stars_amount']} Stars — {p['price']:,} so'm\n".replace(",", " ")
            rows.append([
                InlineKeyboardButton(text=f"⭐ {p['stars_amount']} Stars — {p['price']:,} so'm".replace(",", " "), callback_data="stars_info"),
                InlineKeyboardButton(text="🗑", callback_data=f"del_stars_price_{p['id']}"),
            ])
        rows.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="close_list")])
        try:
            await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        except:
            pass
    else:
        await call.answer("Topilmadi!", show_alert=True)

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
        new_prices = sorted(data["premium_prices"], key=lambda x: x.get("price", 0))
        if not new_prices:
            try:
                await call.message.edit_text("❌ Barcha Premium narxlari o'chirildi.")
            except:
                pass
            return
        text = "💜 <b>PREMIUM NARXLARI RO'YXATI:</b>\n\nO'chirish uchun tugmani bosing 👇\n\n"
        rows = []
        for p in new_prices:
            text += f"• {p['duration']} — {p['price']:,} so'm\n".replace(",", " ")
            rows.append([
                InlineKeyboardButton(text=f"💜 {p['duration']} — {p['price']:,} so'm".replace(",", " "), callback_data="premium_info"),
                InlineKeyboardButton(text="🗑", callback_data=f"del_premium_price_{p['id']}"),
            ])
        rows.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="close_list")])
        try:
            await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        except:
            pass
    else:
        await call.answer("Topilmadi!", show_alert=True)

@router.callback_query(F.data == "confirm_clear_uc")
async def confirm_clear_uc(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    data = await jb_read()
    data["uc_prices"] = []
    await jb_write(data)
    await call.answer("✅ Barcha UC narxlari o'chirildi!", show_alert=True)
    try:
        await call.message.delete()
    except:
        pass

@router.callback_query(F.data == "confirm_clear_stars")
async def confirm_clear_stars(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    data = await jb_read()
    data["stars_prices"] = []
    await jb_write(data)
    await call.answer("✅ Barcha Stars narxlari o'chirildi!", show_alert=True)
    try:
        await call.message.delete()
    except:
        pass

@router.callback_query(F.data == "confirm_clear_premium")
async def confirm_clear_premium(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    data = await jb_read()
    data["premium_prices"] = []
    await jb_write(data)
    await call.answer("✅ Barcha Premium narxlari o'chirildi!", show_alert=True)
    try:
        await call.message.delete()
    except:
        pass

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

# ================== AIOHTTP WEB SERVER ==================
async def create_web_app():
    app = web.Application()
    app.router.add_post("/webhook/checkout", handle_checkout_webhook)
    app.router.add_get("/payment_return/{user_id}", handle_payment_return)
    app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
    return app

# ================== ASOSIY ISHGA TUSHIRISH ==================
async def main():
    print("⏳ Jsonbin.io baza tekshirilmoqda...")
    await init_db()
    print("✅ Baza tayyor!")

    dp.include_router(router)

    web_app = await create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("✅ Web server port 8080 da ishga tushdi!")
    print("✅ Bot ishga tushdi...")

    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
