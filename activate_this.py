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
ADMIN_ID = 1379794856  # O'zingizning ID raqamingiz ekanligini yana bir bor tekshiring
ADD_URL = "https://mirzachulsadosi-dotcom.github.io/gullar-tizimi2/index.html?v=2"
SCAN_URL = "https://mirzachulsadosi-dotcom.github.io/gullar-tizimi2/scanner.html"

# --- RENDER UCHUN VEB-SERVER ---
async def handle(request):
    return web.Response(text="Bot is running! 🌸")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- BOT VA DISPATCHER ---
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

# --- START VA MENYU ---
@dp.message(F.text.startswith('/start'))
async def cmd_start(message: types.Message):
    # QR orqali kelganda tekshirish
    parts = message.text.split()
    if len(parts) > 1:
        f_id = parts[1]
        cursor.execute("SELECT name, r_name, r_phone, days, photo_id FROM flowers WHERE id=?", (f_id,))
        res = cursor.fetchone()
        if res:
            caption = (f"🌸 <b>GUL MA'LUMOTI</b>\n\n📌 Nomi: {res[0]}\n👤 Mas'ul: {res[1]}\n📞 Tel: {res[2]}\n📅 Kunlar: {res[3]}")
            return await message.answer_photo(res[4], caption=caption)

    # Foydalanuvchini bazadan qidirish
    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()

    kb = []
    # Agar Admin bo'lsa barcha tugmalar chiqadi
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
    await message.answer("Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=markup)

# --- RO'YXATDAN O'TISH ---
@dp.message(F.contact)
async def get_contact(message: types.Message):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    
    cursor.execute("INSERT OR REPLACE INTO users (user_id, phone, name) VALUES (?, ?, ?)",
                   (message.from_user.id, phone, message.from_user.full_name))
    conn.commit()
    await message.answer("✅ Ro'yxatdan o'tdingiz! Endi /start bosing va menyudan foydalaning.")

# --- MENING GULLARIM (XODIM UCHUN) ---
@dp.message(F.text == "🌸 Mening gullarim")
async def my_flowers(message: types.Message):
    cursor.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user: return await message.answer("Avval ro'yxatdan o'ting!")

    # Raqam formatini to'g'rilab qidirish
    phone = user[0]
    cursor.execute("SELECT name, days FROM flowers WHERE r_phone LIKE ?", (f"%{phone[-9:]}",))
    rows = cursor.fetchall()

    if not rows:
        await message.answer(f"Sizning raqamingiz ({phone}) bo'yicha biriktirilgan gullar topilmadi.")
    else:
        text = "📋 <b>Sizga biriktirilgan gullar:</b>\n\n"
        for i, r in enumerate(rows, 1):
            text += f"{i}. 🌸 {r[0]} | 📅 Kunlar: {r[1]}\n"
        await message.answer(text)

# --- WEB APP VA RASM (GUL QO'SHISH) ---
@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
        await state.update_data(temp_data=data)
        await state.set_state(Form.waiting_for_photo)
        await message.answer(f"✅ Ma'lumot olindi.\n🌸 Gul: {data['flower']}\n👤 Mas'ul: {data['resp_name']}\n📞 Tel: {data['resp_phone']}\n\nEndi rasm yuboring:")
    except:
        await message.answer("⚠️ Ma'lumotda xatolik!")

@dp.message(Form.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    s = await state.get_data()
    g = s['temp_data']
    photo_id = message.photo[-1].file_id

    # Bazaga saqlash
    cursor.execute("INSERT INTO flowers (name, r_name, r_phone, days, photo_id) VALUES (?, ?, ?, ?, ?)",
                   (g['flower'], g['resp_name'], g['resp_phone'], g['days'], photo_id))
    new_id = cursor.lastrowid
    conn.commit()

    # --- MAS'ULGA HABAR YUBORISH ---
    target_phone = g['resp_phone']
    # Oxirgi 9 ta raqam bo'yicha bazadan user_id qidiramiz
    cursor.execute("SELECT user_id FROM users WHERE phone LIKE ?", (f"%{target_phone[-9:]}",))
    target = cursor.fetchone()
    
    if target:
        try:
            msg_text = f"🔔 <b>Yangi gul biriktirildi!</b>\n\n🌸 Nomi: {g['flower']}\n📅 Kunlar: {g['days']}\n\nIltimos, o'z vaqtida parvarish qiling."
            await bot.send_photo(target[0], photo_id, caption=msg_text)
        except Exception as e:
            logging.error(f"Xabar yuborishda xato: {e}")

    # QR kod yaratish
    qr_link = f"https://t.me/{(await bot.get_me()).username}?start={new_id}"
    qr = qrcode.make(qr_link)
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    buf.seek(0)
    
    await message.answer_photo(BufferedInputFile(buf.read(), filename="qr.png"), caption=f"✅ Saqlandi! ID: {new_id}")
    await state.clear()

# --- ADMIN: BARCHA GULLAR ---
@dp.message(F.text == "📋 Barcha gullar")
async def list_all_flowers(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    cursor.execute("SELECT id, name, r_name, r_phone, days FROM flowers")
    rows = cursor.fetchall()
    
    if not rows:
        return await message.answer("Hozircha bazada gullar yo'q.")

    await message.answer(f"📊 Bazada jami {len(rows)} ta gul bor:")
    for r in rows:
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{r[0]}")]
        ])
        text = f"🆔 ID: {r[0]}\n🌸 Gul: <b>{r[1]}</b>\n👤 Mas'ul: {r[2]}\n📞 Tel: {r[3]}\n📅 Kunlar: {r[4]}"
        await message.answer(text, reply_markup=markup)

@dp.callback_query(F.data.startswith('del_'))
async def delete_callback(callback: types.CallbackQuery):
    f_id = callback.data.split('_')[1]
    cursor.execute("DELETE FROM flowers WHERE id = ?", (f_id,))
    conn.commit()
    await callback.answer("O'chirildi ✅")
    await callback.message.edit_text(text=f"❌ Gul o'chirildi (ID: {f_id})")

# --- ASOSIY ---
async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
