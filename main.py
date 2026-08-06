import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# 1. Заглушка для Render (чтобы открылся порт)
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Запускаем веб-сервер в отдельном потоке
threading.Thread(target=run_health_check_server, daemon=True).start()

# 2. Логика Telegram-бота
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🎁 Получить подарок")
    btn2 = types.KeyboardButton("📞 Связаться с нами")
    markup.add(btn1, btn2)
    
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}! 👋\n\nЯ бот-помощник. Выберите нужное действие в меню ниже:", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text == "🎁 Получить подарок":
        bot.send_message(message.chat.id, "Забирай свой чек-лист: '5 шагов к первому клиенту'! 🚀")
    elif message.text == "📞 Связаться с нами":
        bot.send_message(message.chat.id, "Напишите нашему менеджеру: @your_username")
    else:
        bot.send_message(message.chat.id, "Нажмите на одну из кнопок в меню ниже 👇")

print("Бот успешно запущен!")
bot.polling(none_stop=True)
