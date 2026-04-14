import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
# Agar kodingizda boshqa maxsus importlar bo'lsa, ularni ham tekshiring
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ContentType

API_TOKEN = '8735925686:AAHnUxY2me2v7bO_NfJST_2jAIeSuNHKT3Y'
ADMIN_ID = 1379794856
ADD_URL = "https://mirzachulsadosi-dotcom.github.io/gullar-tizimi2/index.html?v=2"
SCAN_URL = "https://mirzachulsadosi-dotcom.github.io/gullar-tizimi2/scanner.html"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

# --- DATABASE ---
conn = sqlite3.connect('texnikum_gullar.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, phone TEXT, name TEXT)')
cursor.execute(
    'CREATE TABLE IF NOT EXISTS flowers (id INTEGER PRIMARY KEY, name TEXT, r_name TEXT, r_phone TEXT, days TEXT, photo_id TEXT)')
conn.commit()


class Form(StatesGroup):
    waiting_for_photo = State()


# --- START ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    args = message.get_args()
    if args: # QR Skanerlanganda
        cursor.execute("SELECT name, r_name, r_phone, days, photo_id FROM flowers WHERE id=?", (args,))
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

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    if not user:
        markup.add(KeyboardButton("📱 Ro'yxatdan o'tish", request_contact=True))
        await message.answer("Xush kelibsiz! Botdan foydalanish uchun raqamingizni yuboring:", reply_markup=markup)
    else:
        markup.add(KeyboardButton("🌸 Mening gullarim"))
        if message.from_user.id == ADMIN_ID:
            markup.add(KeyboardButton("➕ Gul qo'shish", web_app=WebAppInfo(url=ADD_URL)))
            markup.add(KeyboardButton("📋 Barcha gullar"))
        markup.add(KeyboardButton("🔍 Skaner", web_app=WebAppInfo(url=SCAN_URL)))
        await message.answer("Asosiy menyu:", reply_markup=markup)


# --- RO'YXATDAN O'TISH ---
@dp.message_handler(content_types=ContentType.CONTACT)
async def get_contact(message: types.Message):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    cursor.execute("INSERT OR REPLACE INTO users (user_id, phone, name) VALUES (?, ?, ?)",
                   (message.from_user.id, phone, message.from_user.full_name))
    conn.commit()
    await message.answer("✅ Ro'yxatdan o'tdingiz! /start bosing.")


# --- MENING GULLARIM (Xodim uchun) ---
@dp.message_handler(lambda m: m.text == "🌸 Mening gullarim")
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
                     f"   📞 Tel: {r[2]}\n"
                     f"   📅 Kunlar: {r[3]}\n\n")
        await message.answer(text)


# --- WEB APP DATA (Gul qo'shish) ---
@dp.message_handler(content_types=['web_app_data'])
async def handle_webapp_data(message: types.Message, state: FSMContext):
    raw_data = message.web_app_data.data

    # 1. Skaner natijasini tekshirish (Agar ma'lumot JSON bo'lmasa)
    if "start=" in raw_data:
        f_id = raw_data.split("start=")[1]
        cursor.execute("SELECT name, r_name, days, photo_id FROM flowers WHERE id=?", (f_id,))
        res = cursor.fetchone()
        if res:
            await message.answer_photo(res[3],
                                       caption=f"🌸 <b>Gul:</b> {res[0]}\n👤 <b>Mas'ul:</b> {res[1]}\n📅 <b>Kunlar:</b> {res[2]}")
        else:
            await message.answer("❌ Gul topilmadi.")
        return

    # 2. Yangi gul ma'lumotlarini tekshirish (JSON)
    try:
        data = json.loads(raw_data)
        await state.update_data(temp_data=data)
        await Form.waiting_for_photo.set()
        await message.answer(
            f"✅ Ma'lumot olindi.\n🌸 Gul: {data['flower']}\n👤 Mas'ul: {data['resp_name']}\n\nEndi gulning <b>rasmini</b> yuboring:")
    except json.JSONDecodeError:
        await message.answer("⚠️ Mini App'dan noto'g'ri ma'lumot keldi.")


# --- PHOTO VA MAS'ULGA HABAR ---
@dp.message_handler(content_types=['photo'], state=Form.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    s = await state.get_data()
    g = s['temp_data']
    photo_id = message.photo[-1].file_id

    cursor.execute("INSERT INTO flowers (name, r_name, r_phone, days, photo_id) VALUES (?, ?, ?, ?, ?)",
                   (g['flower'], g['resp_name'], g['resp_phone'], g['days'], photo_id))
    new_id = cursor.lastrowid
    conn.commit()

    # Mas'ulga habar yuborish
    cursor.execute("SELECT user_id FROM users WHERE phone=?", (g['resp_phone'],))
    target = cursor.fetchone()
    if target:
        try:
            await bot.send_photo(target[0], photo_id,
                                 caption=f"🔔 <b>Sizga yangi gul biriktirildi!</b>\n🌸 Nomi: {g['flower']}\n📅 Sug'orish kunlari: {g['days']}")
        except:
            pass

    # QR kod
    qr_link = f"https://t.me/{(await bot.get_me()).username}?start={new_id}"
    qr = qrcode.make(qr_link)
    buf = io.BytesIO();
    qr.save(buf, format='PNG');
    buf.seek(0)
    await message.answer_photo(buf, caption=f"✅ Saqlandi! ID: {new_id}")
    await state.finish()


# Barcha gullarni tugmalar bilan chiqarish
@dp.message_handler(lambda m: m.text == "📋 Barcha gullar")
async def list_all_flowers(message: types.Message):
    if message.from_user.id != ADMIN_ID: return

    cursor.execute("SELECT id, name, r_name, r_phone, days FROM flowers")
    rows = cursor.fetchall()

    if not rows:
        return await message.answer("Bazada gullar yo'q.")

    await message.answer("📋 <b>Barcha biriktirilgan gullar:</b>")

    for r in rows:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text=f"🗑 O'chirish", callback_data=f"del_{r[0]}"))

        text = (f"🆔 ID: {r[0]}\n"
                f"🌸 Gul: <b>{r[1]}</b>\n"
                f"👤 Mas'ul: {r[2]}\n"
                f"📞 Tel: {r[3]}\n"
                f"📅 Kunlar: {r[4]}")

        await message.answer(text, reply_markup=markup)


# O'chirish tugmasi bosilganda
@dp.callback_query_handler(lambda c: c.data.startswith('del_'))
async def delete_callback(callback_query: types.CallbackQuery):
    f_id = callback_query.data.split('_')[1]
    cursor.execute("DELETE FROM flowers WHERE id = ?", (f_id,))
    conn.commit()

    await bot.answer_callback_query(callback_query.id, text="O'chirildi ✅")
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"❌ Gul o'chirildi (ID: {f_id})"
    )


import asyncio

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
