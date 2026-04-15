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
    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()

    kb = []
    if message.from_user.id == ADMIN_ID:
        kb.append([KeyboardButton(text="🌸 Mening gullarim")])
        kb.append([KeyboardButton(text="➕ Gul qo'shish", web_app=WebAppInfo(url=ADD_URL))])
        kb.append([KeyboardButton(text="📋 Barcha gullar"), KeyboardButton(text="🔍 Skaner", web_app=WebAppInfo(url=SCAN_URL))])
    elif user:
        kb.append([KeyboardButton(text="🌸 Mening gullarim")])
        kb.append([KeyboardButton(text="🔍 Skaner", web_app=WebAppInfo(url=SCAN_URL))])
    else:
        kb.append([KeyboardButton(text="📱 Ro'yxatdan o'tish", request_contact=True)])
    
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Mirzacho'l tuman 2-son texnikumi botiga xush kelibsiz!", reply_markup=markup)

# --- RO'YXATDAN O'TISH ---
@dp.message(F.contact)
async def get_contact(message: types.Message):
    phone = message.contact.phone_number.replace("+", "") # Plyusni olib tashlaymiz
    cursor.execute("INSERT OR REPLACE INTO users (user_id, phone, name) VALUES (?, ?, ?)",
                   (message.from_user.id, phone, message.from_user.full_name))
    conn.commit()
    await message.answer("✅ Ro'yxatdan o'tdingiz! Endi menyudan foydalanishingiz mumkin.")

# --- MENING GULLARIM (Xatolik tuzatilgan qismi) ---
@dp.message(F.text == "🌸 Mening gullarim")
async def my_flowers(message: types.Message):
    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user: return await message.answer("Avval ro'yxatdan o'ting!")

    # Foydalanuvchi raqamining oxirgi 9 tasini olamiz (masalan: 943552023)
    user_phone = str(user[0])[-9:]
    
    # Bazadan mas'ul raqami oxiri shu 9 ta raqam bilan tugaydigan gullarni qidiramiz
    cursor.execute("SELECT name, days FROM flowers WHERE r_phone LIKE ?", (f"%{user_phone}",))
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Sizga biriktirilgan gullar topilmadi. (Raqam: " + user[0] + ")")
    else:
        text = "📋 <b>Sizga biriktirilgan gullar:</b>\n\n"
        for i, r in enumerate(rows, 1):
            text += f"{i}. 🌸 {r[0]} | 📅 Sug'orish: {r[1]}\n"
        await message.answer(text)

# --- GUL QO'SHISH VA HABAR YUBORISH ---
@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    await state.update_data(temp_data=data)
    await state.set_state(Form.waiting_for_photo)
    await message.answer(f"✅ Ma'lumot olindi.\n🌸 Gul: {data['flower']}\n👤 Mas'ul: {data['resp_name']}\n\nEndi rasm yuboring:")

@dp.message(Form.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    s = await state.get_data()
    g = s['temp_data']
    photo_id = message.photo[-1].file_id
    
    # Raqamni plyussiz saqlaymiz
    resp_phone = str(g['resp_phone']).replace("+", "")

    cursor.execute("INSERT INTO flowers (name, r_name, r_phone, days, photo_id) VALUES (?, ?, ?, ?, ?)",
                   (g['flower'], g['resp_name'], resp_phone, g['days'], photo_id))
    new_id = cursor.lastrowid
    conn.commit()

    # --- MAS'ULGA HABAR YUBORISH (Tuzatilgan qism) ---
    search_phone = resp_phone[-9:] # Oxirgi 9 ta raqam
    cursor.execute("SELECT user_id FROM users WHERE phone LIKE ?", (f"%{search_phone}",))
    target = cursor.fetchone()
    
    if target:
        try:
            await bot.send_photo(target[0], photo_id, 
                                 caption=f"🔔 <b>Sizga yangi gul biriktirildi!</b>\n\n🌸 Nomi: {g['flower']}\n📅 Kunlar: {g['days']}")
        except:
            pass # Agar foydalanuvchi botni bloklagan bo'lsa

    await message.answer(f"✅ Gul saqlandi! ID: {new_id}")
    await state.clear()

# --- BARCHA GULLAR ---
@dp.message(F.text == "📋 Barcha gullar")
async def list_all_flowers(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT id, name, r_name, days FROM flowers")
    rows = cursor.fetchall()
    if not rows: return await message.answer("Bazada gullar yo'q.")
    
    for r in rows:
        await message.answer(f"🆔 ID: {r[0]}\n🌸 Gul: {r[1]}\n👤 Mas'ul: {r[2]}\n📅 Kunlar: {r[3]}")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
