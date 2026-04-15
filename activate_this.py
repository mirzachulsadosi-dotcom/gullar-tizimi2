import asyncio
import logging
import sqlite3
import json
import io
import qrcode
import os
from aiohttp import web
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

# --- RENDER UCHUN VEB-SERVER ---
async def handle(request):
    return web.Response(text="Bot ishlayapti! 🌸")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- BOT ---
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

# --- START ---
@dp.message(F.text.startswith('/start'))
async def cmd_start(message: types.Message):
    parts = message.text.split()
    if len(parts) > 1:
        f_id = parts[1]
        cursor.execute("SELECT name, r_name, r_phone, days, photo_id FROM flowers WHERE id=?", (f_id,))
        res = cursor.fetchone()
        if res:
            caption = (f"🌸 <b>GUL MA'LUMOTI</b>\n\n📌 Nomi: {res[0]}\n👤 Mas'ul: {res[1]}\n📞 Tel: {res[2]}\n💧 Sug'orish kunlari: {res[3]}")
            return await message.answer_photo(res[4], caption=caption)

    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()

    kb = []
    if message.from_user.id == ADMIN_ID or user:
        kb.append([KeyboardButton(text="🌸 Mening gullarim")])
        if message.from_user.id == ADMIN_ID:
            kb.append([KeyboardButton(text="➕ Gul qo'shish", web_app=WebAppInfo(url=ADD_URL))])
            kb.append([KeyboardButton(text="📋 Barcha gullar")])
        kb.append([KeyboardButton(text="🔍 Skaner", web_app=WebAppInfo(url=SCAN_URL))])
    else:
        kb.append([KeyboardButton(text="📱 Ro'yxatdan o'tish", request_contact=True)])
    
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Xush kelibsiz!", reply_markup=markup)

# --- RO'YXATDAN O'TISH ---
@dp.message(F.contact)
async def get_contact(message: types.Message):
    phone = str(message.contact.phone_number).replace("+", "")
    cursor.execute("INSERT OR REPLACE INTO users (user_id, phone, name) VALUES (?, ?, ?)",
                   (message.from_user.id, phone, message.from_user.full_name))
    conn.commit()
    await message.answer("✅ Ro'yxatdan o'tdingiz!")
    await cmd_start(message)

# --- GUL QO'SHISH ---
@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    await state.update_data(temp_data=data)
    await state.set_state(Form.waiting_for_photo)
    await message.answer(f"🌸 Gul: {data['flower']}\n👤 Mas'ul: {data['resp_name']}\n\nEndi rasm yuboring:")

@dp.message(Form.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    s = await state.get_data()
    g = s['temp_data']
    photo_id = message.photo[-1].file_id
    resp_phone = str(g['resp_phone']).replace("+", "")

    cursor.execute("INSERT INTO flowers (name, r_name, r_phone, days, photo_id) VALUES (?, ?, ?, ?, ?)",
                   (g['flower'], g['resp_name'], resp_phone, g['days'], photo_id))
    new_id = cursor.lastrowid
    conn.commit()

    # --- QR KOD (Eng xavfsiz usul) ---
    try:
        qr_link = f"https://t.me/{(await bot.get_me()).username}?start={new_id}"
        qr_img = qrcode.make(qr_link)
        
        bio = io.BytesIO()
        qr_img.save(bio)
        bio.seek(0)
        
        await message.answer_photo(
            BufferedInputFile(bio.read(), filename="qr.png"), 
            caption=f"✅ Gul saqlandi! ID: {new_id}\n💧 Sug'orish kunlari: {g['days']}"
        )
    except Exception as e:
        await message.answer(f"✅ Saqlandi, lekin QR xatosi: {e}")

    # Mas'ulga xabarnoma
    search_phone = resp_phone[-9:]
    cursor.execute("SELECT user_id FROM users WHERE phone LIKE ?", (f"%{search_phone}",))
    target = cursor.fetchone()
    if target:
        try:
            await bot.send_photo(target[0], photo_id, 
                                 caption=f"🔔 <b>Sizga yangi gul biriktirildi!</b>\n\n🌸 Nomi: {g['flower']}\n💧 Sug'orish kunlari: {g['days']}")
        except: pass

    await state.clear()

# --- MENING GULLARIM ---
@dp.message(F.text == "🌸 Mening gullarim")
async def my_flowers(message: types.Message):
    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()
    search_phone = str(user[0])[-9:] if user else "000"
    
    cursor.execute("SELECT name, days FROM flowers WHERE r_phone LIKE ?", (f"%{search_phone}",))
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Sizga biriktirilgan gullar topilmadi.")
    else:
        text = "📋 <b>Sizga biriktirilgan gullar:</b>\n\n"
        for i, r in enumerate(rows, 1):
            text += f"{i}. 🌸 {r[0]} | 💧 Sug'orish kunlari: {r[1]}\n"
        await message.answer(text)

# --- BARCHA GULLAR ---
@dp.message(F.text == "📋 Barcha gullar")
async def list_all_flowers(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT id, name, r_name, days FROM flowers")
    rows = cursor.fetchall()
    if not rows: return await message.answer("Bazada gullar yo'q.")
    for r in rows:
        await message.answer(f"🆔 ID: {r[0]}\n🌸 Gul: {r[1]}\n👤 Mas'ul: {r[2]}\n💧 Sug'orish kunlari: {r[3]}")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
