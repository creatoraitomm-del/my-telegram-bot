import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# 1. Заглушка для Render
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# 2. Настройки бота
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = 479939884

bot = telebot.TeleBot(TOKEN)

# Временное хранилище выбранного времени пользователей: {chat_id: {"day": ..., "time": ...}}
user_booking = {}

# Главное меню (кнопки под полем ввода)
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_book = types.KeyboardButton("📅 Выбрать время и записаться")
    btn_info = types.KeyboardButton("ℹ️ Контакты и инфо")
    btn_ask = types.KeyboardButton("💬 Задать вопрос")
    markup.add(btn_book, btn_info, btn_ask)
    return markup

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        f"Здравствуйте, {message.from_user.first_name}! 👋\n\n"
        f"Добро пожаловать! Я бот для онлайн-записи.\n"
        f"Выберите нужное действие в меню ниже 👇"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

# --- ШАГ 1: Выбор дня недели ---
@bot.message_handler(func=lambda message: message.text in ["📅 Выбрать время и записаться", "📝 Записаться"])
def choose_day(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Доступные дни
    btn_mon = types.InlineKeyboardButton("🗓 Понедельник", callback_data="day_Понедельник")
    btn_wed = types.InlineKeyboardButton("🗓 Среда", callback_data="day_Среда")
    btn_fri = types.InlineKeyboardButton("🗓 Пятница", callback_data="day_Пятница")
    
    markup.add(btn_mon, btn_wed, btn_fri)
    
    bot.send_message(
        message.chat.id, 
        "Выберите удобный день для записи:", 
        reply_markup=markup
    )

# --- ШАГ 2: Выбор времени (обработка нажатия на день) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("day_"))
def choose_time(call):
    selected_day = call.data.split("_")[1]
    
    # Сохраняем выбранный день
    user_booking[call.message.chat.id] = {"day": selected_day}
    
    # Формируем список слотов в зависимости от дня
    markup = types.InlineKeyboardMarkup(row_width=2)
    if selected_day == "Понедельник":
        times = ["12:00", "15:00", "18:00"]
    elif selected_day == "Среда":
        times = ["10:00", "14:00", "16:30"]
    else: # Пятница
        times = ["11:00", "13:00", "17:00"]
    
    buttons = [types.InlineKeyboardButton(f"⏰ {t}", callback_data=f"time_{t}") for t in times]
    markup.add(*buttons)
    
    # Редактируем текущее сообщение
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Вы выбрали: **{selected_day}**.\n\nТеперь выберите удобное время:",
        parse_mode='Markdown',
        reply_markup=markup
    )

# --- ШАГ 3: Подтверждение и запрос контакта ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("time_"))
def confirm_slot(call):
    selected_time = call.data.split("_")[1]
    
    chat_id = call.message.chat.id
    if chat_id in user_booking:
        user_booking[chat_id]["time"] = selected_time
    else:
        user_booking[chat_id] = {"day": "Ближайший день", "time": selected_time}
    
    day = user_booking[chat_id].get("day", "")
    
    # Убираем инлайн-кнопки и подтверждаем выбор
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"✅ Время выбрано: **{day}, {selected_time}**\n\nОстался последний шаг!",
        parse_mode='Markdown'
    )
    
    # Запрашиваем номер телефона через отдельную кнопку
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_phone = types.KeyboardButton(text="📱 Забронировать (отправить номер)", request_contact=True)
    markup.add(btn_phone)
    
    bot.send_message(
        chat_id, 
        "Нажмите кнопку ниже, чтобы закрепить бронь за вашим номером телефона 👇", 
        reply_markup=markup
    )

# --- ШАГ 4: Получение контакта и отправка готовой брони админу ---
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    user = message.from_user
    chat_id = message.chat.id
    
    # Достаем выбранный день и время
    booking_info = user_booking.get(chat_id, {"day": "Не указан", "time": "Не указано"})
    day = booking_info.get("day", "Не указан")
    time_slot = booking_info.get("time", "Не указано")
    
    lead_info = (
        f"🎯 **ПОДТВЕРЖДЕННАЯ БРОНЬ В БОТЕ!**\n\n"
        f"📅 **Дата/День:** {day}\n"
        f"⏰ **Время:** {time_slot}\n\n"
        f"👤 **Клиент:** {contact.first_name} {contact.last_name or ''}\n"
        f"📞 **Телефон:** +{contact.phone_number}\n"
        f"🔗 **Юзернейм:** @{user.username if user.username else 'не указан'}\n"
        f"🆔 **ID:** `{user.id}`"
    )
    
    try:
        bot.send_message(ADMIN_ID, lead_info, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка отправки администратору: {e}")

    bot.send_message(
        chat_id, 
        f"🎉 **Запись успешно подтверждена!**\n\n"
        f"Ждем вас в **{day} в {time_slot}**.\n"
        f"Мы забронировали это время за вами!", 
        reply_markup=main_keyboard(),
        parse_mode='Markdown'
    )

# Плашка: Контактная информация
@bot.message_handler(func=lambda message: message.text == "ℹ️ Контакты и инфо")
def show_info(message):
    info_text = (
        "📍 **Наша контактная информация:**\n\n"
        "🏢 **Адрес:** г. Москва, ул. Примерная, д. 10, офис 404\n"
        "⏰ **Режим работы:** Пн-Пт с 09:00 до 20:00\n"
        "📞 **Телефон:** +7 (999) 000-00-00\n"
        "🌐 **Наш сайт:** https://example.com"
    )
    bot.send_message(message.chat.id, info_text, parse_mode='Markdown')

# Плашка: Задать вопрос
@bot.message_handler(func=lambda message: message.text == "💬 Задать вопрос")
def ask_question(message):
    ask_text = (
        "❓ **У вас есть вопрос?**\n\n"
        "Просто напишите ваш вопрос прямо в этот чат, и мы перешлем его администратору!"
    )
    bot.send_message(message.chat.id, ask_text, parse_mode='Markdown')

# Пересылка вопросов администратору
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user = message.from_user
    bot.send_message(
        ADMIN_ID, 
        f"📩 **Вопрос от пользователя @{user.username or user.first_name} (ID: {user.id}):**\n\n{message.text}"
    )
    bot.send_message(message.chat.id, "Ваше сообщение передано администратору! Мы ответим вам в ближайшее время.")

bot.polling(none_stop=True)
