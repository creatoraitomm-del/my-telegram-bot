import os
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# 1. Заглушка для Render
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"SuperBot 2.0 is running!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# 2. Инициализация бота и БД
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = 479939884

bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price TEXT NOT NULL,
            duration TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS masters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            service_name TEXT NOT NULL,
            master_name TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM services')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO services (name, price, duration) VALUES (?, ?, ?)', [
            ('Мужская / Женская стрижка', '1 500 ₽', '45 мин'),
            ('Комплексный уход / Окрашивание', '3 500 ₽', '90 мин'),
            ('Консультация специалиста', 'Бесплатно', '30 мин')
        ])
        
    cursor.execute('SELECT COUNT(*) FROM masters')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO masters (name, specialty) VALUES (?, ?)', [
            ('Анна', 'Топ-стилист'),
            ('Дмитрий', 'Мастер широкого профиля'),
            ('Любой свободный мастер', 'Быстрая запись')
        ])
        
    conn.commit()
    conn.close()

init_db()

user_drafts = {}

available_schedule = {
    "10 Августа (Пн)": ["10:00", "12:00", "15:00", "18:00"],
    "12 Августа (Ср)": ["11:00", "14:00", "16:30"],
    "15 Августа (Сб)": ["12:00", "15:00", "17:00"]
}

# --- КЛАВИАТУРЫ ---

def client_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_book = types.KeyboardButton("🚀 Записаться онлайн")
    btn_my_bookings = types.KeyboardButton("👤 Мои записи")
    btn_info = types.KeyboardButton("ℹ️ О нас / Контакты")
    btn_ask = types.KeyboardButton("💬 Задать вопрос")
    markup.add(btn_book, btn_my_bookings, btn_info, btn_ask)
    return markup

def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_list = types.KeyboardButton("📋 Все активные записи")
    btn_stats = types.KeyboardButton("📊 Статистика")
    btn_switch = types.KeyboardButton("👁 Режим клиента")
    markup.add(btn_list, btn_stats, btn_switch)
    return markup

# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ОТОБРАЖЕНИЯ С шагами

def render_services_markup():
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, duration FROM services')
    services = cursor.fetchall()
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for s_id, name, price, duration in services:
        btn_text = f"✂️ {name} — {price} ({duration})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"service_{s_id}"))
    return markup

def render_masters_markup(service_id):
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, specialty FROM masters')
    masters = cursor.fetchall()
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for m_id, name, spec in masters:
        markup.add(types.InlineKeyboardButton(f"👤 {name} ({spec})", callback_data=f"master_{m_id}"))
    
    # Кнопка НАЗАД к услугам
    btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору услуги", callback_data="back_to_services")
    markup.add(btn_back)
    return markup

def render_dates_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for date_str in available_schedule.keys():
        markup.add(types.InlineKeyboardButton(f"🗓 {date_str}", callback_data=f"bdate_{date_str}"))
        
    btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору мастера", callback_data="back_to_masters")
    markup.add(btn_back)
    return markup

# --- КОМАНДА /START ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        bot.send_message(
            message.chat.id, 
            "👑 **Панель Администратора (Супер-Бот 2.0)**\n\nВыберите нужный раздел:", 
            reply_markup=admin_keyboard(),
            parse_mode='Markdown'
        )
    else:
        welcome_text = (
            f"Здравствуйте, {message.from_user.first_name}! 👋\n\n"
            f"Добро пожаловать в нашу систему онлайн-записи.\n"
            f"Выберите нужное действие в меню ниже 👇"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=client_keyboard())

# --- ШАГ 1: ВЫБОР УСЛУГИ ---
@bot.message_handler(func=lambda message: message.text in ["🚀 Записаться онлайн", "📝 Записаться"])
def start_booking(message):
    bot.send_message(
        message.chat.id, 
        "Шаг 1 из 4: **Выберите нужную услугу:**", 
        reply_markup=render_services_markup(), 
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_services")
def back_to_services(call):
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Шаг 1 из 4: **Выберите нужную услугу:**",
        parse_mode='Markdown',
        reply_markup=render_services_markup()
    )

# --- ШАГ 2: ВЫБОР МАСТЕРА ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def select_service(call):
    service_id = int(call.data.split("_")[1])
    
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, price FROM services WHERE id = ?', (service_id,))
    service = cursor.fetchone()
    conn.close()
    
    user_drafts[call.message.chat.id] = {
        "service_id": service_id,
        "service_name": service[0], 
        "service_price": service[1]
    }
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Выбрана услуга: **{service[0]}**\n\nШаг 2 из 4: **Выберите мастера:**",
        parse_mode='Markdown',
        reply_markup=render_masters_markup(service_id)
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_masters")
def back_to_masters(call):
    chat_id = call.message.chat.id
    draft = user_drafts.get(chat_id, {})
    service_id = draft.get("service_id", 1)
    service_name = draft.get("service_name", "Услуга")
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"Выбрана услуга: **{service_name}**\n\nШаг 2 из 4: **Выберите мастера:**",
        parse_mode='Markdown',
        reply_markup=render_masters_markup(service_id)
    )

# --- ШАГ 3: ВЫБОР ДАТЫ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("master_"))
def select_master(call):
    master_id = int(call.data.split("_")[1])
    
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM masters WHERE id = ?', (master_id,))
    master_name = cursor.fetchone()[0]
    conn.close()
    
    chat_id = call.message.chat.id
    if chat_id in user_drafts:
        user_drafts[chat_id]["master_name"] = master_name
        
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"Мастер: **{master_name}**\n\nШаг 3 из 4: **Выберите удобную дату:**",
        parse_mode='Markdown',
        reply_markup=render_dates_markup()
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_dates")
def back_to_dates(call):
    chat_id = call.message.chat.id
    master_name = user_drafts.get(chat_id, {}).get("master_name", "Мастер")
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"Мастер: **{master_name}**\n\nШаг 3 из 4: **Выберите удобную дату:**",
        parse_mode='Markdown',
        reply_markup=render_dates_markup()
    )

# --- ШАГ 4: ВЫБОР ВРЕМЕНИ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("bdate_"))
def select_date(call):
    selected_date = call.data.split("bdate_")[1]
    chat_id = call.message.chat.id
    
    if chat_id in user_drafts:
        user_drafts[chat_id]["date"] = selected_date
        
    times = available_schedule.get(selected_date, [])
    
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT booking_time FROM bookings WHERE booking_date = ? AND status = "active"', (selected_date,))
    booked_times = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    free_times = [t for t in times if t not in booked_times]
    
    if not free_times:
        bot.answer_callback_query(call.id, "К сожалению, на эту дату все слоты забронированы!", show_alert=True)
        return
        
    markup = types.InlineKeyboardMarkup(row_width=2)
    time_buttons = [types.InlineKeyboardButton(f"⏰ {t}", callback_data=f"btime_{t}") for t in free_times]
    markup.add(*time_buttons)
    
    btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору даты", callback_data="back_to_dates")
    markup.add(btn_back)
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"Дата: **{selected_date}**\n\nШаг 4 из 4: **Выберите время:**",
        parse_mode='Markdown',
        reply_markup=markup
    )

# --- ШАГ 5: ПОДТВЕРЖДЕНИЕ И ТЕЛЕФОН ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("btime_"))
def select_time(call):
    selected_time = call.data.split("btime_")[1]
    chat_id = call.message.chat.id
    
    if chat_id in user_drafts:
        user_drafts[chat_id]["time"] = selected_time
        
    draft = user_drafts.get(chat_id, {})
    
    summary = (
        f"📋 **ПРОВЕРЬТЕ ДАННЫЕ ЗАПИСИ:**\n\n"
        f"✂️ **Услуга:** {draft.get('service_name')}\n"
        f"👤 **Мастер:** {draft.get('master_name')}\n"
        f"📅 **Дата:** {draft.get('date')}\n"
        f"⏰ **Время:** {selected_time}\n"
        f"💰 **Стоимость:** {draft.get('service_price')}\n\n"
        f"Для завершения нажмите кнопку **«📱 Подтвердить запись»** ниже 👇"
    )
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=summary,
        parse_mode='Markdown'
    )
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_phone = types.KeyboardButton(text="📱 Подтвердить запись (отправить номер)", request_contact=True)
    markup.add(btn_phone)
    
    bot.send_message(chat_id, "Осталось подтвердить контакт:", reply_markup=markup)

# --- ПРИЕМ КОНТАКТА И СОХРАНЕНИЕ В БАЗУ ---
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    user = message.from_user
    chat_id = message.chat.id
    
    draft = user_drafts.get(chat_id, {})
    client_name = f"{contact.first_name} {contact.last_name or ''}".strip()
    phone = f"+{contact.phone_number}"
    
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bookings (user_id, client_name, phone, service_name, master_name, booking_date, booking_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user.id, client_name, phone, draft.get('service_name', 'Не указана'), draft.get('master_name', 'Любой'), draft.get('date', ''), draft.get('time', '')))
    
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    lead_info = (
        f"🎯 **НОВАЯ ПОДТВЕРЖДЕННАЯ БРОНЬ #{booking_id}**\n\n"
        f"✂️ **Услуга:** {draft.get('service_name')}\n"
        f"👤 **Мастер:** {draft.get('master_name')}\n"
        f"📅 **Дата:** {draft.get('date')} в {draft.get('time')}\n\n"
        f"👤 **Клиент:** {client_name}\n"
        f"📞 **Телефон:** {phone}\n"
        f"🔗 **Юзернейм:** @{user.username if user.username else 'нет'}\n"
        f"🆔 **ID:** `{user.id}`"
    )
    
    try:
        bot.send_message(ADMIN_ID, lead_info, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")

    bot.send_message(
        chat_id, 
        f"🎉 **Вы успешно записаны!**\n\n"
        f"Ждем вас **{draft.get('date')} в {draft.get('time')}**.\n"
        f"Вы всегда можете просмотреть или отменить запись в разделе **«👤 Мои записи»**.", 
        reply_markup=client_keyboard(),
        parse_mode='Markdown'
    )

# --- ЛИЧНЫЙ КАБИНЕТ КЛИЕНТА (МОИ ЗАПИСИ И ОТМЕНА) ---
@bot.message_handler(func=lambda message: message.text == "👤 Мои записи")
def my_bookings(message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, service_name, master_name, booking_date, booking_time 
        FROM bookings 
        WHERE user_id = ? AND status = 'active'
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(message.chat.id, "У вас пока нет активных записей. Нажмите **«🚀 Записаться онлайн»**, чтобы выбрать время!", parse_mode='Markdown')
        return
        
    text = "👤 **ВАШИ АКТИВНЫЕ ЗАПИСИ:**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for b_id, s_name, m_name, b_date, b_time in rows:
        text += f"🔹 **Запись #{b_id}:** {s_name}\n🗓 {b_date} в {b_time} (Мастер: {m_name})\n\n"
        markup.add(types.InlineKeyboardButton(f"❌ Отменить запись #{b_id}", callback_data=f"cancel_{b_id}"))
        
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def cancel_booking(call):
    booking_id = int(call.data.split("_")[1])
    
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE bookings SET status = "cancelled" WHERE id = ?', (booking_id,))
    conn.commit()
    conn.close()
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ **Запись #{booking_id} успешно отменена.** Выбранное время снова свободно для бронирования.",
        parse_mode='Markdown'
    )
    
    bot.send_message(ADMIN_ID, f"🔔 **ОТМЕНА БРОНИ:** Клиент отменил запись #{booking_id}.")

# --- АДМИН-ПАНЕЛЬ ---
@bot.message_handler(func=lambda message: message.text == "📋 Все активные записи" and message.chat.id == ADMIN_ID)
def admin_all_bookings(message):
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, client_name, phone, service_name, master_name, booking_date, booking_time 
        FROM bookings 
        WHERE status = 'active'
        ORDER BY id DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(ADMIN_ID, "📭 Активных записей в базе нет.")
        return
        
    text = "📋 **ВСЕ АКТИВНЫЕ БРОНИ В БАЗЕ:**\n\n"
    for b_id, name, phone, s_name, m_name, b_date, b_time in rows:
        text += f"🆔 **#{b_id}** — {name} ({phone})\n✂️ {s_name} | 👤 {m_name}\n🗓 **{b_date} в {b_time}**\n───────────────\n"
        
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "📊 Статистика" and message.chat.id == ADMIN_ID)
def admin_stats(message):
    conn = sqlite3.connect('booking_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE status = 'active'")
    active_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE status = 'cancelled'")
    cancelled_count = cursor.fetchone()[0]
    conn.close()
    
    bot.send_message(
        ADMIN_ID, 
        f"📈 **СТАТИСТИКА СИСТЕМЫ:**\n\n✅ Активных броней: **{active_count}**\n❌ Отмененных: **{cancelled_count}**", 
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == "👁 Режим клиента" and message.chat.id == ADMIN_ID)
def switch_to_client(message):
    bot.send_message(
        ADMIN_ID, 
        "Вы переключились в вид клиента. Чтобы вернуться в Админ-панель, введите `/start`.", 
        reply_markup=client_keyboard(),
        parse_mode='Markdown'
    )

# Обычные клиентские блоки
@bot.message_handler(func=lambda message: message.text == "ℹ️ О нас / Контакты")
def show_info(message):
    info_text = (
        "📍 **Наша контактная информация:**\n\n"
        "🏢 **Адрес:** г. Москва, ул. Примерная, д. 10, офис 404\n"
        "⏰ **Режим работы:** Пн-Пт с 09:00 до 20:00\n"
        "📞 **Телефон:** +7 (999) 000-00-00\n"
        "🌐 **Наш сайт:** https://example.com"
    )
    bot.send_message(message.chat.id, info_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "💬 Задать вопрос")
def ask_question(message):
    ask_text = (
        "❓ **У вас есть вопрос?**\n\n"
        "Просто напишите ваш вопрос прямо в этот чат, и мы перешлем его администратору!"
    )
    bot.send_message(message.chat.id, ask_text, parse_mode='Markdown')

# Обработка сообщений / вопросов
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user = message.from_user
    
    if message.chat.id == ADMIN_ID:
        if message.reply_to_message:
            try:
                msg_text = message.reply_to_message.text
                if "ID:" in msg_text:
                    target_id_str = msg_text.split("ID:")[1].split(")")[0].strip()
                    target_user_id = int(target_id_str)
                    
                    bot.send_message(target_user_id, f"💬 **Ответ от администратора:**\n\n{message.text}", parse_mode='Markdown')
                    bot.send_message(ADMIN_ID, "✅ Ответ успешно переслан клиенту!")
                    return
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ Ошибка отправки ответа: {e}")
                return
        else:
            bot.send_message(ADMIN_ID, "💡 Нажмите «Ответить» (Reply) на сообщение с вопросом клиента, чтобы отправить ему ответ.")
            return

    bot.send_message(
        ADMIN_ID, 
        f"📩 **Вопрос от пользователя (ID: {user.id}):**\n"
        f"👤 **Имя:** {user.first_name} (@{user.username if user.username else 'нет'})\n\n"
        f"💬 **Текст:** {message.text}"
    )
    bot.send_message(message.chat.id, "Ваше сообщение передано администратору! Мы ответим вам в ближайшее время.")

bot.polling(none_stop=True)
