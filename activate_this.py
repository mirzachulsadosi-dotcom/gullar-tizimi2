import asyncio
import logging
import sqlite3
import json
import io
import qrcode
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ContentType

# --- SOZLAMALAR ---
API_TOKEN = '8735925686:AAHnUxY2me2v7bO_NfJST_2jAIeSuNHKT3Y'
ADMIN_ID = 1379794856
ADD_URL = "https://mirzachulsadosi-dotcom.github.io/gullar-tizimi2/index.html?v=2"
SCAN_URL = "https://mirzachulsadosi-dotcom.github.io/gullar-tizimi2/scanner.html"

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

# START buyrug'i
@dp.message(F.text.startswith('/start'))
async def cmd_start(message: types.Message):
    # QR koddan kelgan ID ni tekshirish
    parts = message.text.split()
    if len(parts) > 1:
        f_id = parts[1]
        cursor.execute("SELECT name, r_name, r_phone, days, photo_id FROM flowers WHERE id=?", (f_id,))
        res = cursor.fetchone()
        if res:
            caption = (f"🌸 <b>GUL MA'LUMOTI</b>\n\n"
                       f"📌 Nomi: {res[0]}\n"
                       f"👤 Mas'ul: {res[1]}\n"
                       f"📞 Tel: {res[2]}\n"
                       f"📅 Kunlar: {res[3]}")
            return await message.answer_photo(res[4], caption=caption)

    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()

    # Tugmalarni aiogram 3.x uslubida yaratish
    kb = []
    if not user:
        kb.append([KeyboardButton(text="📱 Ro'yxatdan o'tish", request_contact=True)])
        markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Xush kelibsiz! Botdan foydalanish uchun raqamingizni yuboring:", reply_markup=markup)
    else:
        kb.append([KeyboardButton(text="🌸 Mening gullarim")])
        if message.from_user.id == ADMIN_ID:
            kb.append([KeyboardButton(text="➕ Gul qo'shish", web_app=WebAppInfo(url=ADD_URL))])
            kb.append([KeyboardButton(text="📋 Barcha gullar")])
        kb.append([KeyboardButton(text="🔍 Skaner", web_app=WebAppInfo(url=SCAN_URL))])
        markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Asosiy menyu:", reply_markup=markup)

# Kontaktni qabul qilish
@dp.message(F.contact)
async def get_contact(message: types.Message):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    cursor.execute("INSERT OR REPLACE INTO users (user_id, phone, name) VALUES (?, ?, ?)",
                   (message.from_user.id, phone, message.from_user.full_name))
    conn.commit()
    await message.answer("✅ Ro'yxatdan o'tdingiz! /start bosing.")

# Xodimga biriktirilgan gullar
@dp.message(F.text == "🌸 Mening gullarim")
async def my_flowers(message: types.Message):
    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user: return await message.answer("Avval ro'yxatdan o'ting!")

    cursor.execute("SELECT name, r_name, r_phone, days FROM flowers WHERE r_phone=?", (user[0],))
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Sizga biriktirilgan gullar yo'q.")
    else:
        text = "📋 <b>Sizning vazifalaringiz:</b>\n\n"
        for i, r in enumerate(rows, 1):
            text += (f"{i}. 🌸 <b>{r[0]}</b>\n"
                     f"   👤 Mas'ul: {r[1]}\n"
                     f"   📅 Kunlar: {r[3]}\n\n")
        await message.answer(text)

# Web App ma'lumotlarini qabul qilish
@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message, state: FSMContext):
    raw_data = message.web_app_data.data
    try:
        data = json.loads(raw_data)
        await state.update_data(temp_data=data)
        await state.set_state(Form.waiting_for_photo)
        await message.answer(f"✅ Ma'lumot olindi.\n🌸 Gul: {data['flower']}\n👤 Mas'ul: {data['resp_name']}\n\nEndi rasm yuboring:")
    except:
        await message.answer("⚠️ Ma'lumotda xatolik!")

# Rasmni qabul qilish va saqlash
@dp.message(Form.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    s = await state.get_data()
    g = s['temp_data']
    photo_id = message.photo[-1].file_id

    cursor.execute("INSERT INTO flowers (name, r_name, r_phone, days, photo_id) VALUES (?, ?, ?, ?, ?)",
                   (g['flower'], g['resp_name'], g['resp_phone'], g['days'], photo_id))
    new_id = cursor.lastrowid
    conn.commit()

    # QR kod yaratish
    qr_link = f"https://t.me/{(await bot.get_me()).username}?start={new_id}"
    qr = qrcode.make(qr_link)
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    buf.seek(0)
    
    file_input = types.BufferedInputFile(buf.read(), filename="qr.png")
    await message.answer_photo(file_input, caption=f"✅ Saqlandi! ID: {new_id}\n\nQR-kodni chop etishingiz mumkin.")
    await state.clear()

# Admin uchun barcha gullar
@dp.message(F.text == "📋 Barcha gullar")
async def list_all_flowers(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT id, name, r_name, r_phone, days FROM flowers")
    rows = cursor.fetchall()
    if not rows: return await message.answer("Bazada gullar yo'q.")

    for r in rows:
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{r[0]}")]
        ])
        text = f"🆔 ID: {r[0]}\n🌸 Gul: {r[1]}\n👤 Mas'ul: {r[2]}\n📞 Tel: {r[3]}\n📅 Kunlar: {r[4]}"
        await message.answer(text, reply_markup=markup)

# O'chirish (Callback)
@dp.callback_query(F.data.startswith('del_'))
async def delete_callback(callback: types.CallbackQuery):
    f_id = callback.data.split('_')[1]
    cursor.execute("DELETE FROM flowers WHERE id = ?", (f_id,))
    conn.commit()
    await callback.answer("O'chirildi ✅")
    await callback.message.edit_text(text=f"❌ Gul o'chirildi (ID: {f_id})")

# BOTNI YURGIZISH
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
