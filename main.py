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

# Главное меню (4 кнопки)
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_slots = types.KeyboardButton("📅 Свободное время")
    btn_book = types.KeyboardButton("📝 Записаться")
    btn_info = types.KeyboardButton("ℹ️ Контакты и инфо")
    btn_ask = types.KeyboardButton("💬 Задать вопрос")
    markup.add(btn_slots, btn_book, btn_info, btn_ask)
    return markup

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        f"Здравствуйте, {message.from_user.first_name}! 👋\n\n"
        f"Добро пожаловать! Я бот-помощник.\n"
        f"Выберите нужное действие с помощью меню ниже 👇"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

# 1. Плашка: Свободное время
@bot.message_handler(func=lambda message: message.text == "📅 Свободное время")
def show_slots(message):
    slots_text = (
        "🗓 **Свободные слоты для записи на эту неделю:**\n\n"
        "🔹 **Понедельник:** 12:00, 15:00, 18:00\n"
        "🔹 **Среда:** 10:00, 14:00, 16:30\n"
        "🔹 **Пятница:** 11:00, 13:00, 17:00\n\n"
        "Чтобы забронировать время, нажмите кнопку **«📝 Записаться»** ниже!"
    )
    bot.send_message(message.chat.id, slots_text, parse_mode='Markdown')

# 2. Процесс записи (Запрос контакта)
@bot.message_handler(func=lambda message: message.text == "📝 Записаться")
def request_phone(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_phone = types.KeyboardButton(text="📱 Отправить свой номер телефона", request_contact=True)
    markup.add(btn_phone)
    
    bot.send_message(
        message.chat.id, 
        "Нажмите кнопку ниже, чтобы передать ваш контакт. Менеджер свяжется с вами для подтверждения времени! 👇", 
        reply_markup=markup
    )

# 3. Плашка: Контактная информация
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

# 4. Плашка: Задать вопрос
@bot.message_handler(func=lambda message: message.text == "💬 Задать вопрос")
def ask_question(message):
    ask_text = (
        "❓ **У вас есть вопрос?**\n\n"
        "Вы можете написать прямо нашему администратору в личные сообщения: @your_username\n\n"
        "Или просто напишите ваш вопрос прямо в этот чат, и мы перешлем его менеджеру!"
    )
    bot.send_message(message.chat.id, ask_text, parse_mode='Markdown')

# Обработка полученного контакта при записи
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    user = message.from_user
    
    lead_info = (
        f"🚨 **НОВАЯ ЗАПИСЬ В БОТЕ!**\n\n"
        f"👤 **Имя:** {contact.first_name} {contact.last_name or ''}\n"
        f"📞 **Телефон:** +{contact.phone_number}\n"
        f"🔗 **Юзернейм:** @{user.username if user.username else 'не указан'}\n"
        f"🆔 **ID:** `{user.id}`"
    )
    
    try:
        bot.send_message(ADMIN_ID, lead_info, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка отправки администратору: {e}")

    bot.send_message(
        message.chat.id, 
        "Спасибо! Ваша заявка успешно отправлена. Мы перезвоним вам в ближайшее время для уточнения деталей! 🚀", 
        reply_markup=main_keyboard()
    )

# Пересылка любого текстового сообщения от пользователя администратору
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user = message.from_user
    bot.send_message(
        ADMIN_ID, 
        f"📩 **Вопрос от пользователя @{user.username or user.first_name} (ID: {user.id}):**\n\n{message.text}"
    )
    bot.send_message(message.chat.id, "Ваше сообщение передано менеджеру! Мы ответим вам в ближайшее время.")

bot.polling(none_stop=True)
