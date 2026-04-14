import asyncio
import logging
import sqlite3
import json
import io
import qrcode
import os
from aiohttp import web # Render uchun veb-server
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

# --- SOZLAMALAR ---
API_TOKEN = '8735925686:AAHnUxY2me2v7bO_NfJST_2jAIeSuNHKT3Y'
ADMIN_ID = 1379794856
ADD_URL = "https://mirzachulsadosi-dotcom.github.io/gullar-tizimi2/index.html?v=2"
SCAN_URL = "https://mirzachulsadosi-dotcom.github.io/gullar-tizimi2/scanner.html"

# --- RENDER UCHUN VEB-SERVER (PORT MUAMMOSINI HAL QILISH) ---
async def handle(request):
    return web.Response(text="Bot is running! 🌸")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render odatda 10000 portni ishlatadi, lekin PORT o'zgaruvchisini olish xavfsizroq
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server started on port {port}")

# --- LOGGING VA BOT ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=MemoryStorage())

# --- DATABASE ---
conn = sqlite3.connect('texnikum_gullar.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, phone TEXT, name TEXT)')
cursor.execute('CREATE TABLE IF NOT EXISTS flowers (id INTEGER PRIMARY KEY, name TEXT, r_name TEXT, r_phone TEXT, days TEXT, photo_id TEXT)')
conn.commit()

class Form(StatesGroup):
    waiting_for_photo = State()

# --- HANDLERS ---

@dp.message(F.text.startswith('/start'))
async def cmd_start(message: types.Message):
    parts = message.text.split()
    if len(parts) > 1:
        f_id = parts[1]
        cursor.execute("SELECT name, r_name, r_phone, days, photo_id FROM flowers WHERE id=?", (f_id,))
        res = cursor.fetchone()
        if res:
            caption = (f"🌸 <b>GUL MA'LUMOTI</b>\n\n📌 Nomi: {res[0]}\n👤 Mas'ul: {res[1]}\n📞 Tel: {res[2]}\n📅 Kunlar: {res[3]}")
            return await message.answer_photo(res[4], caption=caption)

    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()

    kb = []
    if not user:
        kb.append([KeyboardButton(text="📱 Ro'yxatdan o'tish", request_contact=True)])
    else:
        kb.append([KeyboardButton(text="🌸 Mening gullarim")])
        if message.from_user.id == ADMIN_ID:
            kb.append([KeyboardButton(text="➕ Gul qo'shish", web_app=WebAppInfo(url=ADD_URL))])
            kb.append([KeyboardButton(text="📋 Barcha gullar")])
        kb.append([KeyboardButton(text="🔍 Skaner", web_app=WebAppInfo(url=SCAN_URL))])
    
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=markup)

@dp.message(F.contact)
async def get_contact(message: types.Message):
    phone = message.contact.phone_number
    cursor.execute("INSERT OR REPLACE INTO users (user_id, phone, name) VALUES (?, ?, ?)",
                   (message.from_user.id, phone, message.from_user.full_name))
    conn.commit()
    await message.answer("✅ Ro'yxatdan o'tdingiz! Botdan foydalanishingiz mumkin.Qaytadan /start ni bosing")

@dp.message(F.text == "🌸 Mening gullarim")
async def my_flowers(message: types.Message):
    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user: return await message.answer("Avval ro'yxatdan o'ting!")

    cursor.execute("SELECT name, r_name, days FROM flowers WHERE r_phone=?", (user[0],))
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Sizga biriktirilgan gullar hozircha yo'q.")
    else:
        text = "📋 <b>Sizning vazifalaringiz:</b>\n\n"
        for i, r in enumerate(rows, 1):
            text += f"{i}. 🌸 {r[0]}\n   📅 Kunlar: {r[2]}\n\n"
        await message.answer(text)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
        await state.update_data(temp_data=data)
        await state.set_state(Form.waiting_for_photo)
        await message.answer(f"✅ Gul: {data['flower']}\n👤 Mas'ul: {data['resp_name']}\n\nEndi rasm yuboring:")
    except:
        await message.answer("⚠️ Ma'lumotda xatolik!")

@dp.message(Form.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    s = await state.get_data()
    g = s['temp_data']
    photo_id = message.photo[-1].file_id

    cursor.execute("INSERT INTO flowers (name, r_name, r_phone, days, photo_id) VALUES (?, ?, ?, ?, ?)",
                   (g['flower'], g['resp_name'], g['resp_phone'], g['days'], photo_id))
    new_id = cursor.lastrowid
    conn.commit()

    qr_link = f"https://t.me/{(await bot.get_me()).username}?start={new_id}"
    qr = qrcode.make(qr_link)
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    buf.seek(0)
    
    file_input = BufferedInputFile(buf.read(), filename="qr.png")
    await message.answer_photo(file_input, caption=f"✅ Saqlandi! ID: {new_id}\nQR-kodni skanerlab tekshirishingiz mumkin.")
    await state.clear()

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    # 1. Veb-serverni ishga tushirish (Render port xatosini olmaslik uchun)
    await start_web_server()
    # 2. Botni ishga tushirish
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
        # Bazada bormi yoki Adminmi tekshirish
    if message.from_user.id == ADMIN_ID:
        kb.append([KeyboardButton(text="🌸 Mening gullarim")])
        kb.append([KeyboardButton(text="➕ Gul qo'shish", web_app=WebAppInfo(url=ADD_URL))])
        kb.append([KeyboardButton(text="📋 Barcha gullar")])
        kb.append([KeyboardButton(text="🔍 Skaner", web_app=WebAppInfo(url=SCAN_URL))])
    elif user:
        kb.append([KeyboardButton(text="🌸 Mening gullarim")])
        kb.append([KeyboardButton(text="🔍 Skaner", web_app=WebAppInfo(url=SCAN_URL))])
    else:
        kb.append([KeyboardButton(text="📱 Ro'yxatdan o'tish", request_contact=True)])
