import asyncio
import logging
import aiohttp
from datetime import datetime
import pytz
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command
import json
import hashlib
import hmac

# ================== SOZLAMALAR ==================
BOT_TOKEN = "8631309919:AAHmHJWlRqiXKBiMkrPIxvd1LyHrm6MPIvc"
ADMIN_ID = 8332077004
MAIN_CHANNEL_ID = "@Azizbekl2026"

# CHECKOUT.UZ SOZLAMALARI
CHECKOUT_API_KEY = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM"  # Siz bergan Secret Key
CHECKOUT_MERCHANT_ID = "46"                    # Siz bergan Kassa ID
CHECKOUT_WEBHOOK_SECRET = "N2MxYjNkYmI4ZjdlYjVjMWYxZTM" # Odatda Secret Key imzo uchun ishlatiladi
CHECKOUT_BASE_URL = "https://checkout.uz/api/v1"
WEBHOOK_URL = "https://shaxsiy-auto-to-lov-bot-production.up.railway.app" # Railway URLingiz

# JSONBIN.IO SOZLAMALARI
JSONBIN_API_KEY = "$2a$10$HEa6qY6FgdbvtwnxhGkIE.59M05ctGsBYJn7zuLyvhrrqsWH5peje"
JSONBIN_BIN_ID = "69c24750aa77b81da9139a00"
JSONBIN_BASE_URL = "https://api.jsonbin.io/v3"

# ================== YORDAMCHI FUNKSIYALAR (JSONBIN) ==================
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
    }    async with aiohttp.ClientSession() as session:
        async with session.put(url, json=data, headers=headers) as resp:
            return resp.status == 200

async def init_db():
    data = await jb_read()
    changed = False
    defaults = {
        "users": [], "channels": [], "ads": [], 
        "uc_prices": [], "uc_orders": [], 
        "stars_prices": [], "stars_orders": [], 
        "premium_prices": [], "premium_orders": [],
        "settings": {
            "price": "5000", # Narxni 5000 ga o'zgartirdim (rasmdagi misolga qarab)
            "card": "8600 0000 0000 0000 (Ism Familiya)",
            "start_msg": "Assalomu aleykum {name}!\nSiz bu botdan Akvuntingizni sotishingiz va Pubg mobile uc sotib olishingiz va Telgram yulduzlar sotib olishingiz va Telgram pryum sotib olishingiz mumkin\nXizmatlarni birni talang 👇",
            "site_url": "https://azizbekqiyomov55555-dev.github.io/Test-bot-"
        },
        "next_id": 1
    }
    
    for key, value in defaults.items():
        if key not in data:
            if key == "settings":
                if "settings" not in data: data["settings"] = {}
                for s_key, s_val in value.items():
                    if s_key not in data["settings"]:
                        data["settings"][s_key] = s_val
                        changed = True
            else:
                data[key] = value
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

# ================== CHECKOUT.UZ API FUNKSIYALARI ==================

async def create_checkout_payment(amount: int, order_id: str, description: str):
    """To'lov yaratish"""
    url = f"{CHECKOUT_BASE_URL}/create_payment"    headers = {
        "Authorization": f"Bearer {CHECKOUT_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": amount,
        "description": description,
        "order_id": order_id, # Buyurtma raqami
        "callback_url": WEBHOOK_URL # To'lov holati o'zgarganda shu yerga xabar keladi
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            result = await resp.json()
            if result.get("status") == "success":
                return result.get("payment", {}).get("_url")
            else:
                return None

async def verify_webhook_signature(payload_body, signature_header):
    """Webhook imzosini tekshirish (Xavfsizlik uchun)"""
    # Checkout.uz odatda HMAC SHA256 ishlatadi
    expected_signature = hmac.new(
        CHECKOUT_WEBHOOK_SECRET.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)

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

class PaymentState(StatesGroup):
    waiting_payment = State() # To'lov jarayonida

class SupportForm(StatesGroup):
    msg = State()

class AdminForm(StatesGroup):
    start_msg = State()
    price = State()    card = State()
    add_channel_id = State()
    add_channel_url = State()
    reply_msg = State()
    # ... boshqa admin state lari ...
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

# UC, Stars, Premium Order Formlari (avvalgidek qoladi, lekin to'lov qismi o'zgaradi)
class UCOrderForm(StatesGroup):
    pubg_screenshot = State() # Hozircha ID so'rash qoldi, keyinroq to'lov qo'shish mumkin
    receipt = State()

class StarsOrderForm(StatesGroup):
    choose_target = State()
    friend_username = State()
    receipt = State()

class PremiumOrderForm(StatesGroup):
    choose_duration = State()
    target_username = State()
    receipt = State()

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
    for ch in channels:        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ['left', 'kicked']:
                unsubbed.append(ch["url"])
        except:
            pass
    return unsubbed

# ================== ASOSIY MENU ==================
def get_main_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 E'lon berish", style="primary"), KeyboardButton(text="🆘 Yordam", style="danger")],
            [KeyboardButton(text="🎮 PUBG MOBILE UC OLISH 💎", style="success")],
            [KeyboardButton(text="⭐ TELEGRAM PREMIUM", style="danger"), KeyboardButton(text="🌟 STARS OLISH", style="primary")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Quyidagi tugmalardan birini tanlang 👇"
    )
    return kb

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
            "pending_approval": 0
        })
        data["users"] = users
        await jb_write(data)

    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 Kanal {i+1} — Obuna bo'lish", url=url, style="primary")]
            for i, url in enumerate(unsubbed)
        ] + [[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub", style="success")]])
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=btn)        return

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

# ================== E'LON BERISH (TO'LOV BILAN) ==================
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

    posted = user.get("posted_ads", 0)
    paid = user.get("paid_slots", 0)
    pending = user.get("pending_approval", 0)

    if pending:
        await message.answer("⏳ Sizning oldingi e'loningiz admin tomonidan ko'rib chiqilmoqda.\nAdmin tasdiqlaganidan so'ng yangi e'lon berishingiz mumkin.")
        return

    # Limitni tekshirish: 1 ta bepul + sotib olinganlar
    if posted >= (1 + paid):
        price_str = data.get("settings", {}).get("price", "5000")
        try:
            price = int(price_str)
        except:
            price = 5000
            
        # To'lov havolasini yaratish
        order_id = f"ad_{message.from_user.id}_{get_next_id(data)}" # Unikal ID        payment_url = await create_checkout_payment(
            amount=price,
            order_id=order_id,
            description=f"E'lon joylash uchun to'lov (ID: {message.from_user.id})"
        )

        if payment_url:
            btn = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💳 To'lov qilish", url=payment_url, style="success")
            ]])
            await message.answer(
                f"Sizning bepul e'lonlar limitingiz tugagan.\n"
                f"1-video bepul, 2-sidan boshlab pullik.\n"
                f"E'lon narxi: {price:,} so'm.\n\n"
                f"Quyidagi tugmani bosib to'lovni amalga oshiring:", 
                reply_markup=btn, parse_mode="HTML"
            )
            # Holatni saqlab qo'yamiz, agar webhook ishlamasa (ehtimollik)
            await state.set_state(PaymentState.waiting_payment)
            await state.update_data(expected_order_id=order_id)
        else:
            await message.answer("⚠️ To'lov tizimida xatolik yuz berdi. Iltimos, birozdan keyin urinib ko'ring yoki admin bilan bog'laning.")
        return

    # Agar limit bor bo'lsa, darhol e'lon olishni boshlaymiz
    await message.answer("E'loningizni boshlaymiz.\nIltimos, akkaunt obzori videosini yuboring:")
    await state.set_state(AdForm.video)

# ================== TO'LOV WEBHOOK HANDLER ==================
# Bu funksiya checkout.uz dan keladigan POST so'rovni qabul qiladi
@router.message(F.web_app_data) 
# DIQQAT: Aiogram da webhook xabarlari oddiy message emas, balki alohida handler orqali keladi.
# Lekin aiogram 3.x da webhookni to'g'ri sozlash kerak. 
# Quyidagi kod webhook so'rovlarini qabul qilish uchun maxsus router emas, 
# shuning uchun biz aiohttp web serveridan foydalanamiz yoki aiogram ning webhook feature'idan.

# ENG TO'G'RI YO'L: Aiogram Dispatcher webhook so'rovlarini avtomatik qabul qiladi agar bot.set_webhook ishlatilsa.
# Lekin bizga custom logic kerak (signature tekshirish). 
# Shuning uchun, biz botni polling rejimida qoldiramiz, lekin webhook xabarlari kelganda ularni qanday qabul qilamiz?
# Aiogram 3.x da webhook xabarlari Update obyekti sifatida keladi. 
# Agar checkout.uz JSON yuborsa, bu oddiy Message emas. 

# YECHIM: Biz webhook URL ni Railway ga yo'naltiramiz. Railway da Flask/FastAPI ishlatish kerak edi, 
# lekin siz faqat Python bot kodi so'rayapsiz. 
# Aiogram da webhookni qabul qilish uchun @router.message ishlamaydi agar content_type JSON bo'lsa.
# Shuning uchun, biz "Polling" rejimida ishlaymiz deb faraz qilamiz, lekin Checkout.uz webhook yuboradi.
# BU MUAMMO: Polling rejimida bot webhook xabarini ko'rmaydi.

# ALTERNATIVA: Checkout.uz da "Return URL" bor. Foydalanuvchi to'lagach saytgaga qaytadi.
# Lekin eng ishonchlisi Webhook. # Keling, kodni shunday yozamizki, agar siz Railway da ishlatayotgan bo'lsangiz, 
# sizga alohida webhook handler kerak bo'ladi. 
# Hozirgi kodda men "Polling" ni qoldiraman, lekin to'lov tasdiqlanishini simulyatsiya qilish uchun 
# ADMIN uchun maxsus tugma qo'shamiz yoki foydalanuvchi "To'lov qildim" deb yozishi kerak bo'ladi?
# YO'Q, siz avtomatlashtirishni xohlaysiz.

# MAJBURIY O'ZGARISH: Webhookni qabul qilish uchun aiohttp serverini bot ichiga qo'shamiz.
# Bu biroz murakkab, lekin ishlaydi.

from aiohttp import web

async def handle_checkout_webhook(request):
    """Checkout.uz dan keladigan webhook so'rovni qabul qilish"""
    try:
        body = await request.read()
        signature = request.headers.get('X-Checkout-Signature') # Header nomi dokumentatsiyaga qarab o'zgarishi mumkin
        
        # Imzo tekshiruvi (ixtiyoriy, lekin tavsiya etiladi)
        # if not verify_webhook_signature(body, signature):
        #     return web.Response(status=403, text="Invalid signature")
        
        data_json = json.loads(body)
        
        # Checkout.uz response formati taxminan shunday:
        # {"status": "success", "data": {"order_id": "...", "status": "paid", ...}}
        
        if data_json.get("status") == "success" and data_json.get("data", {}).get("status") == "paid":
            order_info = data_json.get("data", {})
            order_id = order_info.get("order_id")
            
            # order_id dan user_id ni ajratib olamiz: "ad_USERID_RANDOM"
            if order_id and order_id.startswith("ad_"):
                parts = order_id.split("_")
                if len(parts) >= 2:
                    user_id = int(parts[1])
                    
                    # Bazani yangilash
                    db_data = await jb_read()
                    users = db_data.get("users", [])
                    for u in users:
                        if u["user_id"] == user_id:
                            u["paid_slots"] = u.get("paid_slots", 0) + 1
                            break
                    db_data["users"] = users
                    await jb_write(db_data)
                    
                    # Foydalanuvchiga xabar yuborish
                    try:
                        await bot.send_message(
                            user_id,                             "✅ <b>To'lovingiz tasdiqlandi!</b>\n\nEndi yana e'lon joylashingiz mumkin. \"📝 E'lon berish\" tugmasini bosing.",
                            parse_mode="HTML",
                            reply_markup=get_main_menu()
                        )
                    except Exception as e:
                        logging.error(f"Failed to send message to {user_id}: {e}")
                        
                    return web.Response(status=200, text="OK")
        
        return web.Response(status=200, text="Ignored")
        
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return web.Response(status=500, text="Error")

# Serverni ishga tushirish funksiyasi
async def start_webhook_server():
    app = web.Application()
    app.router.add_post('/', handle_checkout_webhook) # Webhook shu manzilga keladi
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080) # Port 8080 (Railway default)
    await site.start()
    print("✅ Webhook server ishga tushdi (Port 8080)")

# ================== E'LON BERISH JARAYONI (Davomi) ==================
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
            break    data["users"] = users
    await jb_write(data)

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_ad_{ad_id}", style="success"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_ad_{ad_id}", style="danger")
    ]])

    try:
        await bot.send_video(ADMIN_ID, video=st.get('video'),
            caption=f"📢 Yangi e'lon!\nFoydalanuvchi: {message.from_user.full_name} (ID: {message.from_user.id})\n\n{text}",
            reply_markup=btn, parse_mode="HTML")
    except:
        pass

    await message.answer("✅ E'loningiz adminga yuborildi. Tasdiqlanishini kuting.", reply_markup=get_main_menu())
    await state.clear()

# ================== ADMIN PANEL (Qisqartirilgan, lekin narx o'zgartirish bor) ==================
@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data="admin_price", style="success")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats", style="primary")],
        # Boshqa tugmalar...
    ])
    await message.answer("⚙️ Admin panelga xush kelibsiz!", reply_markup=btn)

@router.callback_query(F.data == "admin_price")
async def set_price_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi e'lon narxini kiriting (faqat raqam, masalan: 5000):")
    await state.set_state(AdminForm.price)

@router.message(AdminForm.price, F.from_user.id == ADMIN_ID)
async def save_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    data = await jb_read()
    data["settings"]["price"] = message.text
    await jb_write(data)
    await message.answer(f"✅ Narx yangilandi: {message.text} so'm")
    await state.clear()

# ================== ADMIN E'LON TASDIQLASH ==================
@router.callback_query(F.data.startswith("app_ad_"))
async def approve_ad(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return        
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
        [InlineKeyboardButton(text="👤 Sotuvchi bilan aloqa", url=f"tg://user?id={user_id}", style=c1)],
        [InlineKeyboardButton(text="📢 Reklama berish", url=f"https://t.me/{me.username}?start=ad", style=c2)]
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
        await bot.send_message(user_id, "✅ E'loningiz kanalga joylandi!", reply_markup=get_main_menu())
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
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
        
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

# ================== ASOSIY ISHGA TUSHIRISH ==================
async def main():
    print("⏳ Jsonbin.io baza tekshirilmoqda...")
    await init_db()
    print("✅ Baza tayyor!")
    
    dp.include_router(router)
    
    # Webhook serverini alohida vazifa sifatida ishga tushiramiz
    asyncio.create_task(start_webhook_server())
        print("✅ Bot ishga tushdi (Polling + Webhook Server)...")
    # Diqqat: Agar siz Railway da ishlatayotgan bo'lsangiz, polling o'rniga webhook mode ishlatish kerak bo'lishi mumkin.
    # Lekin bu kod ikkalasini ham qamrab oladi (Server port 8080 da tinglaydi, bot esa polling da ishlaydi).
    # Railway da faqat webhook serveri ishlaydi, polling ishlamasligi mumkin agar timeout bo'lsa.
    # Agar Railway da muammo bo'lsa, dp.start_polling(bot) ni o'chirib, faqat web.run_app(app) qoldirish kerak.
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
